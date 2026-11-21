"""Testes do backup do SQLite, da retenção e do script (issue #70)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.scripts import backup as script
from app.services.backup import (
    PADRAO_NOME,
    ErroBackup,
    ErroRetencao,
    aplicar_retencao,
    gerar_backup,
    listar_backups,
    nome_do_backup,
)

BACKEND = Path(__file__).resolve().parents[1]
MOMENTO = datetime(2026, 11, 20, 15, 30, 45, tzinfo=timezone.utc)


def _criar_banco(caminho: Path, linhas: int = 0, *, wal: bool = True) -> Path:
    with closing(sqlite3.connect(caminho)) as conexao:
        if wal:
            conexao.execute("PRAGMA journal_mode=WAL")
        conexao.execute("CREATE TABLE dados (id INTEGER PRIMARY KEY, valor TEXT NOT NULL)")
        conexao.executemany("INSERT INTO dados (valor) VALUES (?)", [(f"linha-{i}",) for i in range(linhas)])
        conexao.commit()
    return caminho


def _contar(caminho: Path) -> int:
    with closing(sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)) as conexao:
        return conexao.execute("SELECT COUNT(*) FROM dados").fetchone()[0]


def _arquivos_de_backup(pasta: Path, quantidade: int, *, a_partir_de: datetime = MOMENTO) -> list[Path]:
    """Cria arquivos com nome de backup em datas distintas (do mais antigo ao mais novo)."""
    pasta.mkdir(parents=True, exist_ok=True)
    criados = []
    for i in range(quantidade):
        arquivo = pasta / nome_do_backup(a_partir_de - timedelta(days=quantidade - i))
        arquivo.write_bytes(b"x")
        criados.append(arquivo)
    return criados


# ── Geração ───────────────────────────────────────────────────────────────────


def test_backup_nomeia_em_utc_e_gera_arquivo_unico(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 5)
    fuso = timezone(timedelta(hours=-4))  # Mato Grosso; o nome sempre sai em UTC
    momento = datetime(2026, 11, 20, 11, 30, 45, tzinfo=fuso)

    resultado = gerar_backup(origem, tmp_path / "bk", momento=momento)

    assert resultado.arquivo.name == "novamente-20261120-153045.db"
    assert PADRAO_NOME.match(resultado.arquivo.name)
    assert resultado.tabelas == 1
    assert resultado.tamanho_bytes == resultado.arquivo.stat().st_size > 0
    assert _contar(resultado.arquivo) == 5
    # só o backup na pasta: nada de temporário, -wal ou -shm sobrando
    assert [p.name for p in (tmp_path / "bk").iterdir()] == [resultado.arquivo.name]
    if os.name == "posix":
        assert resultado.arquivo.stat().st_mode & 0o777 == 0o600


def test_backup_nao_altera_a_origem(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 20, wal=False)
    antes = origem.read_bytes()

    gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)

    assert origem.read_bytes() == antes


def test_backup_cria_a_pasta_de_destino_com_parents(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 1)

    resultado = gerar_backup(origem, tmp_path / "a" / "b" / "bk", momento=MOMENTO)

    assert resultado.arquivo.parent == tmp_path / "a" / "b" / "bk"


def test_backup_consistente_com_gravacao_concorrente(tmp_path):
    """Uma thread grava sem parar enquanto o backup roda; a cópia abre, passa no
    integrity_check e traz todas as linhas anteriores ao início do backup."""
    anteriores = 2000
    origem = _criar_banco(tmp_path / "origem.db", anteriores)
    parar = threading.Event()
    gravando = threading.Event()
    gravadas = []
    erros = []

    def escritor():
        try:
            with closing(sqlite3.connect(origem, timeout=30)) as conexao:
                while not parar.is_set():
                    with conexao:
                        conexao.execute("INSERT INTO dados (valor) VALUES (?)", ("durante-o-backup",))
                    gravadas.append(1)
                    gravando.set()
        except Exception as exc:  # noqa: BLE001
            erros.append(exc)
            gravando.set()

    thread = threading.Thread(target=escritor)
    thread.start()
    try:
        assert gravando.wait(timeout=10)
        resultado = gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)
    finally:
        parar.set()
        thread.join(timeout=10)

    assert not erros
    assert len(gravadas) > 0
    with closing(sqlite3.connect(resultado.arquivo)) as copia:
        assert copia.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        ids = {linha[0] for linha in copia.execute("SELECT id FROM dados")}
        assert set(range(1, anteriores + 1)) <= ids
        # o retrato é consistente: sem buracos na sequência de ids
        assert ids == set(range(1, max(ids) + 1))
    assert _contar(origem) >= _contar(resultado.arquivo)


def test_backup_com_banco_em_wal_e_arquivo_wal_pendente(tmp_path):
    """Dados que ainda estão só no -wal da origem entram no backup."""
    origem = _criar_banco(tmp_path / "origem.db", 3)
    conexao = sqlite3.connect(origem)  # mantida aberta: o -wal não é consolidado
    try:
        conexao.execute("PRAGMA wal_autocheckpoint=0")
        conexao.executemany("INSERT INTO dados (valor) VALUES (?)", [("no-wal",)] * 10)
        conexao.commit()
        assert (tmp_path / "origem.db-wal").stat().st_size > 0

        resultado = gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)
    finally:
        conexao.close()

    assert _contar(resultado.arquivo) == 13


def test_backup_nao_sobrescreve_backup_do_mesmo_segundo(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 1)
    primeiro = gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)
    conteudo = primeiro.arquivo.read_bytes()

    with pytest.raises(ErroBackup, match="Já existe um backup"):
        gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)

    assert primeiro.arquivo.read_bytes() == conteudo


# ── Falhas ────────────────────────────────────────────────────────────────────


def test_backup_de_origem_inexistente_falha_sem_criar_nada(tmp_path):
    with pytest.raises(ErroBackup, match="Banco de dados não encontrado"):
        gerar_backup(tmp_path / "nao-existe.db", tmp_path / "bk", momento=MOMENTO)

    assert not (tmp_path / "nao-existe.db").exists()
    assert not (tmp_path / "bk").exists()


def test_backup_de_arquivo_que_nao_e_banco_falha_e_limpa_o_temporario(tmp_path):
    origem = tmp_path / "texto.db"
    origem.write_text("isto não é um banco SQLite " * 100)

    with pytest.raises(ErroBackup, match="SQLite recusou"):
        gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)

    assert list((tmp_path / "bk").iterdir()) == []


def test_backup_de_banco_sem_tabelas_falha_e_descarta(tmp_path):
    origem = tmp_path / "vazio.db"
    with closing(sqlite3.connect(origem)) as conexao:
        conexao.execute("PRAGMA user_version = 1")

    with pytest.raises(ErroBackup, match="não tem tabelas"):
        gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)

    assert list((tmp_path / "bk").iterdir()) == []


def test_backup_com_pasta_de_destino_invalida_falha_com_mensagem_clara(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 1)
    arquivo_comum = tmp_path / "arquivo-comum"
    arquivo_comum.write_text("x")

    with pytest.raises(ErroBackup, match="BACKUP_DIR"):
        gerar_backup(origem, arquivo_comum / "bk", momento=MOMENTO)


def test_backup_com_integridade_ruim_e_descartado(tmp_path, monkeypatch):
    origem = _criar_banco(tmp_path / "origem.db", 1)
    real = sqlite3.connect

    class _Conexao:
        def __init__(self, conexao):
            self._conexao = conexao

        def execute(self, sql, *args):
            if sql == "PRAGMA integrity_check":
                return self._conexao.execute("SELECT 'pagina corrompida'")
            return self._conexao.execute(sql, *args)

        def close(self):
            self._conexao.close()

    def conectar(destino, *args, **kwargs):
        conexao = real(destino, *args, **kwargs)
        # só a verificação do arquivo temporário (aberto em leitura) é adulterada
        return _Conexao(conexao) if "mode=ro" in str(destino) and ".tmp" in str(destino) else conexao

    monkeypatch.setattr("app.services.backup.sqlite3.connect", conectar)

    with pytest.raises(ErroBackup, match="integridade"):
        gerar_backup(origem, tmp_path / "bk", momento=MOMENTO)

    assert list((tmp_path / "bk").iterdir()) == []


# ── Retenção ──────────────────────────────────────────────────────────────────


def test_retencao_mantem_os_mais_recentes_e_nao_toca_em_outros_arquivos(tmp_path):
    pasta = tmp_path / "bk"
    backups = _arquivos_de_backup(pasta, 10)
    estranhos = [
        pasta / "notas.txt",
        pasta / "novamente.db",  # banco de verdade, sem data no nome
        pasta / "novamente-20260101-000000.db.bak",
        pasta / "novamente-2026-01-01.db",
        pasta / "outro-20260101-000000.db",
        pasta / "novamente-20260101-000000.db.tmp",
        pasta / ".novamente-20260101-000000.db.1.tmp",
    ]
    for estranho in estranhos:
        estranho.write_text("não mexer")
    (pasta / "novamente-20250101-000000.db").mkdir()  # pasta com nome de backup

    removidos = aplicar_retencao(pasta, 3)

    assert sorted(removidos) == backups[:7]
    assert listar_backups(pasta) == backups[7:]
    for estranho in estranhos:
        assert estranho.read_text() == "não mexer"
    assert (pasta / "novamente-20250101-000000.db").is_dir()


def test_retencao_nao_apaga_nada_quando_ha_menos_que_o_limite(tmp_path):
    pasta = tmp_path / "bk"
    backups = _arquivos_de_backup(pasta, 3)

    assert aplicar_retencao(pasta, 7) == []
    assert aplicar_retencao(pasta, 3) == []
    assert listar_backups(pasta) == backups


def test_retencao_usa_a_data_do_nome_e_nao_a_do_arquivo(tmp_path):
    pasta = tmp_path / "bk"
    backups = _arquivos_de_backup(pasta, 4)
    # mtime invertido: o arquivo mais antigo pelo nome é o mais novo no disco
    for posicao, arquivo in enumerate(backups):
        os.utime(arquivo, (1_000_000 - posicao, 1_000_000 - posicao))

    aplicar_retencao(pasta, 2)

    assert listar_backups(pasta) == backups[2:]


def test_retencao_em_pasta_inexistente_nao_faz_nada(tmp_path):
    assert aplicar_retencao(tmp_path / "nao-existe", 3) == []


def test_retencao_minima_e_um(tmp_path):
    with pytest.raises(ValueError):
        aplicar_retencao(tmp_path, 0)


def test_retencao_nunca_remove_o_backup_recem_gerado(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 1)
    pasta = tmp_path / "bk"
    antigos = _arquivos_de_backup(pasta, 3, a_partir_de=MOMENTO - timedelta(days=30))

    novo = gerar_backup(origem, pasta, momento=MOMENTO)
    removidos = aplicar_retencao(pasta, 1)

    assert removidos == antigos
    assert listar_backups(pasta) == [novo.arquivo]


def test_retencao_continua_e_avisa_quando_nao_consegue_apagar(tmp_path, monkeypatch):
    pasta = tmp_path / "bk"
    backups = _arquivos_de_backup(pasta, 4)
    real = Path.unlink

    def unlink(self, *args, **kwargs):
        if self == backups[0]:
            raise PermissionError("negado")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)

    with pytest.raises(ErroRetencao, match="1 backup"):
        aplicar_retencao(pasta, 1)

    assert listar_backups(pasta) == [backups[0], backups[3]]


# ── Configuração ──────────────────────────────────────────────────────────────


def test_padroes_do_backup(monkeypatch):
    monkeypatch.delenv("BACKUP_DIR", raising=False)
    monkeypatch.delenv("BACKUP_RETENCAO", raising=False)
    config = Settings(_env_file=None)

    assert config.backup_dir == "./data/backups"
    assert config.backup_retencao == 7


def test_configuracao_valida_do_backup(monkeypatch):
    monkeypatch.setenv("BACKUP_DIR", "/volume/backups")
    monkeypatch.setenv("BACKUP_RETENCAO", "1")
    config = Settings(_env_file=None)

    assert config.backup_dir == "/volume/backups"
    assert config.backup_retencao == 1


@pytest.mark.parametrize(
    "variavel,valor",
    [
        ("BACKUP_RETENCAO", "0"),
        ("BACKUP_RETENCAO", "-3"),
        ("BACKUP_RETENCAO", "muitos"),
        ("BACKUP_DIR", ""),
    ],
)
def test_configuracao_invalida_do_backup_impede_a_subida(monkeypatch, variavel, valor):
    monkeypatch.setenv(variavel, valor)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


# ── Script ────────────────────────────────────────────────────────────────────


@pytest.fixture
def ambiente_do_script(tmp_path, monkeypatch):
    origem = _criar_banco(tmp_path / "origem.db", 4)
    monkeypatch.setattr(settings, "db_path", str(origem))
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "bk"))
    monkeypatch.setattr(settings, "backup_retencao", 2)
    return origem


def test_script_gera_backup_aplica_retencao_e_sai_com_zero(ambiente_do_script, tmp_path, capsys):
    _arquivos_de_backup(tmp_path / "bk", 3)

    codigo = script.main()

    saida = capsys.readouterr()
    assert codigo == 0
    gerados = listar_backups(tmp_path / "bk")
    assert len(gerados) == 2
    assert f"Backup gerado: {gerados[-1]}" in saida.out
    assert "tabelas: 1" in saida.out
    assert "removidos 2" in saida.out
    assert _contar(gerados[-1]) == 4


def test_script_avisa_quando_o_catalogo_esta_em_outro_arquivo(ambiente_do_script, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path}/outro.db")

    assert script.main() == 0

    assert "DATABASE_URL aponta para um arquivo diferente de DB_PATH" in capsys.readouterr().err


def test_script_nao_avisa_quando_db_path_e_database_url_sao_o_mesmo_arquivo(
    ambiente_do_script, monkeypatch, capsys
):
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{ambiente_do_script}")

    assert script.main() == 0

    assert capsys.readouterr().err == ""


def test_script_falha_com_codigo_diferente_de_zero_e_sem_expor_o_caminho(
    ambiente_do_script, monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "segredo" / "nao-existe.db"))

    codigo = script.main()

    saida = capsys.readouterr()
    assert codigo == 1
    assert "Banco de dados não encontrado" in saida.err
    assert "segredo" not in saida.err + saida.out
    assert not (tmp_path / "bk").exists()


def test_script_nao_aplica_retencao_quando_o_backup_falha(ambiente_do_script, monkeypatch, tmp_path):
    antigos = _arquivos_de_backup(tmp_path / "bk", 5)
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "nao-existe.db"))

    assert script.main() == 1

    assert listar_backups(tmp_path / "bk") == antigos


def test_script_sai_com_dois_quando_a_retencao_falha(ambiente_do_script, monkeypatch, capsys):
    def falha(*_args, **_kwargs):
        raise ErroRetencao("1 backup(s) antigo(s) não puderam ser apagados.")

    monkeypatch.setattr(script, "aplicar_retencao", falha)

    assert script.main() == 2
    assert "não puderam ser apagados" in capsys.readouterr().err


def _rodar_script(tmp_path: Path, **ambiente: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("BACKUP_DIR", "BACKUP_RETENCAO", "DB_PATH")}
    env.update(PYTHONDONTWRITEBYTECODE="1", GOOGLE_API_KEY="fake_key_for_ci_testing", **ambiente)
    return subprocess.run(
        [sys.executable, "-m", "app.scripts.backup"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_python_m_app_scripts_backup_gera_o_arquivo(tmp_path):
    origem = _criar_banco(tmp_path / "origem.db", 6)

    proc = _rodar_script(
        tmp_path,
        DB_PATH=str(origem),
        BACKUP_DIR=str(tmp_path / "bk"),
        BACKUP_RETENCAO="3",
        DATABASE_URL=f"sqlite:///{origem}",
    )

    assert proc.returncode == 0, proc.stderr
    gerados = listar_backups(tmp_path / "bk")
    assert len(gerados) == 1
    assert _contar(gerados[0]) == 6
    assert "Backup gerado:" in proc.stdout


@pytest.mark.parametrize("retencao", ["0", "-1"])
def test_python_m_app_scripts_backup_com_retencao_invalida_falha(tmp_path, retencao):
    origem = _criar_banco(tmp_path / "origem.db", 1)

    proc = _rodar_script(
        tmp_path,
        DB_PATH=str(origem),
        BACKUP_DIR=str(tmp_path / "bk"),
        BACKUP_RETENCAO=retencao,
        DATABASE_URL=f"sqlite:///{origem}",
    )

    assert proc.returncode == 1
    assert "BACKUP_RETENCAO" in proc.stderr
    assert "Traceback" not in proc.stderr
    assert not (tmp_path / "bk").exists()
