"""Limpeza automática do disco do Chroma: legado, rotação e diretórios órfãos.

Chroma real em pasta temporária (fixture ``chroma_temporario``) e vetores
falsos. Os diretórios ficam "antigos" com ``os.utime``.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

import chromadb
import pytest
from fastapi.testclient import TestClient
from ulid import ULID

from app.models import JobResposta
from app.rag import armazenamento, config
from app.services import limpeza_disco_chroma as disco
from app.services import limpeza_indice, repositorio

pytestmark = pytest.mark.usefixtures("chroma_temporario")

DUAS_HORAS = 2 * 3600


# ── Ajudantes ─────────────────────────────────────────────────────────────────


def _cliente() -> chromadb.ClientAPI:
    return armazenamento.obter_cliente()


def _pasta() -> Path:
    return Path(_cliente().get_settings().persist_directory).resolve()


def _diretorios_uuid() -> set[str]:
    return {d.name for d in _pasta().iterdir() if d.is_dir() and disco._nome_uuid(d.name)}


def _envelhecer(*caminhos: Path) -> None:
    antigo = time.time() - DUAS_HORAS
    for caminho in caminhos or [d for d in _pasta().iterdir() if d.is_dir()]:
        for item in [caminho, *caminho.iterdir()]:
            os.utime(item, (antigo, antigo), follow_symlinks=False)


def _vetores(n: int) -> list[list[float]]:
    return [[float(i + 1), 1.0, 0.5, 0.25] for i in range(n)]


def _criar_legada(documento_id: str | None = None, nome: str | None = None, linhas: int = 3):
    """Collection no formato antigo: uma por documento, prefixo doc_."""
    documento_id = documento_id or f"doc_{ULID()}"
    colecao = _cliente().create_collection(
        nome or f"doc_{documento_id}_abc123def456",
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"documento_id": documento_id, "titulo": "Antigo"},
        embedding_function=None,
    )
    colecao.add(ids=[f"{i:05d}" for i in range(linhas)], documents=["t"] * linhas, embeddings=_vetores(linhas))
    return colecao


def _segmento_vetorial(colecao) -> str:
    vivos = sqlite3.connect(f"file:{_pasta() / disco.ARQUIVO_CATALOGO}?mode=ro", uri=True)
    try:
        (segmento,) = vivos.execute(
            "SELECT id FROM segments WHERE collection = ? AND scope = 'VECTOR'", (str(colecao.id),)
        ).fetchone()
    finally:
        vivos.close()
    return segmento


def _diretorio_orfao(nome: str | None = None, arquivos=("header.bin", "data_level0.bin")) -> Path:
    diretorio = _pasta() / (nome or str(uuid.uuid4()))
    diretorio.mkdir()
    for arquivo in arquivos:
        (diretorio / arquivo).write_bytes(b"\0" * 1000)
    return diretorio


def _indexar(documento_id: str, linhas: int = 2) -> None:
    armazenamento.salvar_trechos(documento_id, "T", [f"t{i}" for i in range(linhas)], _vetores(linhas))


# ── Canário de versão ─────────────────────────────────────────────────────────


def test_canario_formato_do_catalogo_do_chroma():
    """Se falhar, o formato interno do Chroma mudou: revise limpeza_disco_chroma.py.

    A coleta de diretórios órfãos supõe (chromadb 1.5.9) que o catálogo é
    ``chroma.sqlite3`` na raiz da pasta, que a tabela ``segments`` tem as
    colunas ``id``, ``scope`` e ``collection``, que o diretório do segmento
    vetorial tem o nome do seu id e que ele só tem os arquivos de ARQUIVOS_HNSW.
    """
    aviso = "O formato interno do Chroma mudou; revise a coleta de órfãos ao atualizar o chromadb"
    _indexar("doc-canario")
    catalogo = _pasta() / disco.ARQUIVO_CATALOGO
    assert catalogo.is_file(), f"{aviso}: {disco.ARQUIVO_CATALOGO} não está na raiz da pasta."
    conexao = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
    try:
        colunas = {linha[1] for linha in conexao.execute(f"PRAGMA table_info({disco.TABELA_SEGMENTOS})")}
    finally:
        conexao.close()
    assert {disco.COLUNA_ID_SEGMENTO, "scope", "collection"} <= colunas, (
        f"{aviso}: a tabela {disco.TABELA_SEGMENTOS} tem as colunas {sorted(colunas)}."
    )
    compartilhada = _cliente().get_collection(config.NOME_COLLECTION)
    segmento = _segmento_vetorial(compartilhada)
    assert segmento in disco.segmentos_vivos(_pasta())
    diretorio = _pasta() / segmento
    assert diretorio.is_dir(), f"{aviso}: o diretório do segmento vetorial não tem o nome do id."
    arquivos = {f.name for f in diretorio.iterdir()}
    assert arquivos <= disco.ARQUIVOS_HNSW, f"{aviso}: arquivos novos no segmento HNSW: {sorted(arquivos)}."


def test_delete_collection_deixa_o_diretorio_no_disco():
    """O motivo de existir a coleta: neste Chroma o diretório fica para trás."""
    colecao = _criar_legada()
    segmento = _segmento_vetorial(colecao)
    _cliente().delete_collection(colecao.name)
    assert segmento not in disco.segmentos_vivos(_pasta())
    assert (_pasta() / segmento).is_dir()


# ── Legado ────────────────────────────────────────────────────────────────────


def test_legado_sai_do_catalogo_e_do_disco(caplog):
    legadas = [_criar_legada() for _ in range(3)]
    segmentos = {_segmento_vetorial(c) for c in legadas}
    intactas = [
        _criar_legada(nome="doc_manual", documento_id="doc-manual"),
        _criar_legada(nome="outra_colecao"),  # documento_id do pipeline, mas sem o prefixo
        _cliente().create_collection("doc_sem_metadados", embedding_function=None),
    ]
    intactas[2].add(ids=["1"], embeddings=_vetores(1))
    segmentos_intactos = {_segmento_vetorial(c) for c in intactas}
    _envelhecer()
    with caplog.at_level(logging.INFO, logger="app.services.limpeza_indice"):
        limpeza_indice.varrer_indices_orfaos()
    nomes = {c.name for c in _cliente().list_collections()}
    assert not nomes & {c.name for c in legadas}
    assert {c.name for c in intactas} <= nomes
    assert not segmentos & _diretorios_uuid()
    assert segmentos_intactos <= _diretorios_uuid()
    assert "3 collections legadas removidas" in caplog.text
    assert "3 diretórios órfãos removidos" in caplog.text


@pytest.mark.parametrize(
    "nome,metadados,esperado",
    [
        (f"doc_doc_{'0' * 26}_abc", {"documento_id": f"doc_{'0' * 26}"}, True),
        (config.NOME_COLLECTION, {"documento_id": f"doc_{'0' * 26}"}, False),
        (f"doc_doc_{'0' * 26}_abc", {"documento_id": "doc-manual"}, False),
        (f"doc_doc_{'0' * 26}_abc", None, False),
        (f"doc_doc_{'0' * 26}_abc", {"documento_id": 42}, False),
        (f"x_doc_{'0' * 26}", {"documento_id": f"doc_{'0' * 26}"}, False),
    ],
)
def test_reconhece_so_collections_legadas_do_pipeline(nome, metadados, esperado):
    assert disco.collection_legada(nome, metadados) is esperado


# ── Coleta de diretórios órfãos ───────────────────────────────────────────────


def test_orfao_antigo_so_com_arquivos_hnsw_e_removido():
    _indexar("doc-manual")
    orfao = _diretorio_orfao(arquivos=sorted(disco.ARQUIVOS_HNSW))
    _envelhecer(orfao)
    resultado = disco.coletar_diretorios_orfaos(_pasta())
    assert resultado.diretorios == 1
    assert resultado.bytes_liberados == 1000 * len(disco.ARQUIVOS_HNSW)
    assert not orfao.exists()


def test_segmento_vivo_nunca_e_removido():
    _indexar("doc-manual")
    vivo = _pasta() / _segmento_vetorial(_cliente().get_collection(config.NOME_COLLECTION))
    _envelhecer()
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert vivo.is_dir()
    assert armazenamento.buscar("doc-manual", _vetores(1)[0])[0].documento_id == "doc-manual"


def test_orfao_recente_nao_e_removido():
    orfao = _diretorio_orfao()
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert orfao.is_dir()


def test_orfao_com_um_arquivo_recente_nao_e_removido():
    orfao = _diretorio_orfao()
    _envelhecer(orfao)
    os.utime(orfao / "header.bin")  # um arquivo foi escrito agora
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert orfao.is_dir()


@pytest.mark.parametrize(
    "arquivos,subpasta",
    [(("header.bin", "anotacoes.txt"), False), (("header.bin",), True)],
    ids=["arquivo-estranho", "subpasta"],
)
def test_orfao_com_conteudo_estranho_nao_e_removido(arquivos, subpasta):
    orfao = _diretorio_orfao(arquivos=arquivos)
    if subpasta:
        (orfao / "dentro").mkdir()
    _envelhecer(orfao)
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert orfao.is_dir()


@pytest.mark.parametrize(
    "nome", ["backup", "123", str(uuid.uuid4()).upper(), str(uuid.uuid4()).replace("-", "")]
)
def test_nome_que_nao_e_uuid_canonico_nao_e_removido(nome):
    orfao = _diretorio_orfao(nome=nome)
    _envelhecer(orfao)
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert orfao.is_dir()


def test_link_simbolico_nao_e_seguido_nem_removido(tmp_path):
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "header.bin").write_bytes(b"\0")
    link = _pasta() / str(uuid.uuid4())
    link.symlink_to(fora, target_is_directory=True)
    _envelhecer(fora)
    os.utime(link, (time.time() - DUAS_HORAS,) * 2, follow_symlinks=False)
    assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert link.is_symlink()
    assert (fora / "header.bin").is_file()


def test_link_simbolico_dentro_da_pasta_nao_e_seguido(caplog):
    """Link com nome de UUID apontando para o segmento vivo, dentro da própria pasta."""
    _indexar("doc-manual")
    vivo = _pasta() / _segmento_vetorial(_cliente().get_collection(config.NOME_COLLECTION))
    link = _pasta() / str(uuid.uuid4())
    link.symlink_to(vivo, target_is_directory=True)
    _envelhecer(vivo)
    os.utime(link, (time.time() - DUAS_HORAS,) * 2, follow_symlinks=False)
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_disco_chroma"):
        assert disco.coletar_diretorios_orfaos(_pasta()).diretorios == 0
    assert link.is_symlink() and vivo.is_dir()
    assert caplog.records == []  # nem chegou a tentar apagar


@pytest.mark.parametrize("caso", ["vazio", "ponto", "raiz", "home", "acima-do-home"])
def test_pasta_suspeita_nao_apaga_nada(caso, tmp_path, monkeypatch, caplog):
    casa = tmp_path / "casa" / "usuario"
    casa.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(casa))
    pasta = {"vazio": Path(""), "ponto": Path("."), "raiz": Path("/"), "home": casa,
             "acima-do-home": casa.parent}[caso]
    orfao = casa / str(uuid.uuid4())
    orfao.mkdir()
    (orfao / "header.bin").write_bytes(b"\0")
    _envelhecer(orfao)
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_disco_chroma"):
        resultado = disco.coletar_diretorios_orfaos(pasta)
    assert resultado.diretorios == 0
    assert orfao.is_dir()
    assert "Coleta de diretórios do Chroma recusada" in caplog.text


# ── Catálogo ilegível ─────────────────────────────────────────────────────────


def _pasta_com_catalogo(tmp_path: Path, preparar) -> tuple[Path, Path]:
    pasta = tmp_path / "chroma-falso"
    pasta.mkdir()
    preparar(pasta / disco.ARQUIVO_CATALOGO)
    orfao = pasta / str(uuid.uuid4())
    orfao.mkdir()
    (orfao / "header.bin").write_bytes(b"\0")
    antigo = time.time() - DUAS_HORAS
    os.utime(orfao / "header.bin", (antigo, antigo))
    os.utime(orfao, (antigo, antigo))
    return pasta, orfao


def _sem_tabela(caminho: Path) -> None:
    conexao = sqlite3.connect(caminho)
    conexao.execute("CREATE TABLE outra (id TEXT)")
    conexao.commit()
    conexao.close()


def _sem_coluna(caminho: Path) -> None:
    conexao = sqlite3.connect(caminho)
    conexao.execute("CREATE TABLE segments (segment_uuid TEXT)")
    conexao.commit()
    conexao.close()


@pytest.mark.parametrize(
    "preparar,motivo",
    [
        (lambda c: None, "chroma.sqlite3 não encontrado"),
        (lambda c: c.write_bytes(b"isto nao e um banco sqlite" * 100), "DatabaseError"),
        (_sem_tabela, "tabela segments.id ausente no catálogo"),
        (_sem_coluna, "tabela segments.id ausente no catálogo"),
    ],
    ids=["ausente", "corrompido", "sem-tabela", "sem-coluna"],
)
def test_catalogo_ilegivel_nao_apaga_nada(tmp_path, caplog, preparar, motivo):
    pasta, orfao = _pasta_com_catalogo(tmp_path, preparar)
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_disco_chroma"):
        assert disco.coletar_diretorios_orfaos(pasta).diretorios == 0
    assert orfao.is_dir()
    assert f"catálogo ilegível ({motivo})" in caplog.text


def test_catalogo_travado_nao_apaga_nada(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(disco, "ESPERA_CATALOGO_SEGUNDOS", 0.1)
    pasta, orfao = _pasta_com_catalogo(tmp_path, _sem_coluna)
    conexao = sqlite3.connect(pasta / disco.ARQUIVO_CATALOGO)
    conexao.execute("DROP TABLE segments")
    conexao.execute("CREATE TABLE segments (id TEXT)")
    conexao.commit()
    conexao.execute("BEGIN EXCLUSIVE")
    try:
        with caplog.at_level(logging.WARNING, logger="app.services.limpeza_disco_chroma"):
            assert disco.coletar_diretorios_orfaos(pasta).diretorios == 0
    finally:
        conexao.rollback()
        conexao.close()
    assert orfao.is_dir()
    assert "catálogo ilegível (OperationalError)" in caplog.text


def test_subida_continua_com_catalogo_ilegivel(monkeypatch, caplog):
    from app.main import app

    def quebra(_pasta):
        raise disco.CatalogoIlegivel("teste")

    monkeypatch.setattr(disco, "segmentos_vivos", quebra)
    orfao = _diretorio_orfao()
    _envelhecer(orfao)
    with caplog.at_level(logging.WARNING, logger="app.services.limpeza_disco_chroma"):
        with TestClient(app) as client:
            assert client.get("/api/v1/health").status_code == 200
    assert orfao.is_dir()
    assert "catálogo ilegível (teste)" in caplog.text


# ── Rotação ───────────────────────────────────────────────────────────────────


def _id_compartilhada() -> str:
    return str(_cliente().get_collection(config.NOME_COLLECTION).id)


def test_rotaciona_collection_vazia_e_coleta_o_diretorio_antigo(caplog):
    orfao_doc = f"doc_{ULID()}"
    _indexar(orfao_doc)  # linha órfã: o job não existe mais
    antiga = _id_compartilhada()
    diretorio_antigo = _segmento_vetorial(_cliente().get_collection(config.NOME_COLLECTION))
    _envelhecer()
    with caplog.at_level(logging.INFO, logger="app.services.limpeza_indice"):
        assert limpeza_indice.varrer_indices_orfaos() == 2
    assert _id_compartilhada() != antiga
    assert diretorio_antigo not in _diretorios_uuid()
    assert "rotação feita" in caplog.text
    _indexar("doc-depois", 3)
    assert len(armazenamento.buscar("doc-depois", _vetores(1)[0], k=10)) == 3


def test_nao_rotaciona_com_linhas_vivas():
    _indexar("doc-manual")
    antiga = _id_compartilhada()
    _envelhecer()
    limpeza_indice.varrer_indices_orfaos()
    assert _id_compartilhada() == antiga
    assert armazenamento.documentos_indexados() == {"doc-manual": 2}


def test_nao_rotaciona_com_job_em_andamento():
    _indexar("doc-manual")
    armazenamento.remover_documento("doc-manual")  # vazia, mas com HNSW no disco
    agora = "2026-11-17T12:00:00+00:00"
    repositorio.salvar_job(JobResposta(job_id=str(ULID()), status="running", iniciado_em=agora, atualizado_em=agora))
    antiga = _id_compartilhada()
    limpeza_indice.varrer_indices_orfaos()
    assert _id_compartilhada() == antiga


def test_nao_rotaciona_collection_que_nunca_gravou_no_disco():
    armazenamento.documentos_indexados()  # cria a collection compartilhada, sem vetores
    antiga = _id_compartilhada()
    limpeza_indice.varrer_indices_orfaos()
    assert _id_compartilhada() == antiga


def test_falha_no_meio_da_rotacao_recria_na_proxima_chamada(monkeypatch):
    _indexar("doc-manual")
    armazenamento.remover_documento("doc-manual")
    cliente = _cliente()
    get_or_create_real = cliente.get_or_create_collection
    chamadas = {"n": 0}

    def get_or_create_falha_depois_de_apagar(*args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 2:  # a recriação, logo depois do delete
            raise RuntimeError("falhou ao recriar")
        return get_or_create_real(*args, **kwargs)

    monkeypatch.setattr(cliente, "get_or_create_collection", get_or_create_falha_depois_de_apagar)
    with pytest.raises(RuntimeError):
        armazenamento.recriar_colecao_se_vazia(lambda _id: True)
    assert config.NOME_COLLECTION not in {c.name for c in cliente.list_collections()}
    _indexar("doc-novo")  # a próxima chamada recria com get_or_create
    assert armazenamento.existe_documento("doc-novo")


def test_indexacao_concorrente_depois_da_rotacao():
    _indexar(f"doc_{ULID()}")
    _envelhecer()
    limpeza_indice.varrer_indices_orfaos()
    erros = []

    def trabalhar(t):
        try:
            for k in range(5):
                documento = f"doc-{t}-{k}"
                _indexar(documento, 3)
                assert {a.documento_id for a in armazenamento.buscar(documento, _vetores(1)[0], k=10)} == {documento}
                armazenamento.remover_documento(documento)
        except Exception as exc:  # pragma: no cover - aparece na asserção
            erros.append(repr(exc))

    threads = [threading.Thread(target=trabalhar, args=(t,)) for t in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert erros == []
    assert armazenamento.documentos_indexados() == {}


# ── Idempotência e resumo ─────────────────────────────────────────────────────


def test_segunda_execucao_nao_faz_nada(caplog):
    for _ in range(2):
        _criar_legada()
    _indexar(f"doc_{ULID()}")
    _envelhecer()
    limpeza_indice.varrer_indices_orfaos()
    antes = (_id_compartilhada(), _diretorios_uuid(), {c.name for c in _cliente().list_collections()})
    _envelhecer()
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.services.limpeza_indice"):
        assert limpeza_indice.varrer_indices_orfaos() == 0
    depois = (_id_compartilhada(), _diretorios_uuid(), {c.name for c in _cliente().list_collections()})
    assert depois == antes
    assert (
        "0 linhas órfãs removidas (0 documentos), 0 collections legadas removidas, "
        "rotação não feita, 0 diretórios órfãos removidos (0.0 MB liberados)"
    ) in caplog.text


def test_ambiente_com_legado_fica_com_a_pasta_minima():
    for _ in range(10):
        _criar_legada()
    _envelhecer()
    tamanho = lambda: sum(f.stat().st_size for f in _pasta().rglob("*") if f.is_file())  # noqa: E731
    antes, diretorios_antes = tamanho(), len(_diretorios_uuid())
    limpeza_indice.varrer_indices_orfaos()
    assert diretorios_antes == 10
    assert _diretorios_uuid() == set()
    assert tamanho() < antes  # sobra só o catálogo
