"""scripts/gerar_hash_senha.py: lê a senha sem eco e imprime só o hash."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.auth.senhas import verificar_senha

_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "gerar_hash_senha.py"
_spec = importlib.util.spec_from_file_location("gerar_hash_senha", _CAMINHO)
gerar_hash_senha = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gerar_hash_senha)


def _leitor(*respostas):
    fila = list(respostas)
    return lambda _prompt: fila.pop(0)


def test_imprime_so_o_hash(capsys):
    assert gerar_hash_senha.main([], ler_senha=_leitor("Empresa@2026", "Empresa@2026")) == 0
    saida = capsys.readouterr()
    linha = saida.out.strip()
    assert saida.out.count("\n") == 1 and linha.startswith("scrypt$")
    assert verificar_senha("Empresa@2026", linha)
    assert "Empresa@2026" not in saida.out + saida.err


def test_recusa_senha_fraca(capsys):
    assert gerar_hash_senha.main([], ler_senha=_leitor("fraca")) == 1
    saida = capsys.readouterr()
    assert saida.out == "" and "A senha precisa ter" in saida.err


def test_recusa_confirmacao_diferente(capsys):
    assert gerar_hash_senha.main([], ler_senha=_leitor("Empresa@2026", "Empresa@2027")) == 1
    assert capsys.readouterr().out == ""


def test_nao_aceita_senha_por_argumento(capsys):
    assert gerar_hash_senha.main(["Empresa@2026"], ler_senha=_leitor()) == 2
    saida = capsys.readouterr()
    assert saida.out == "" and "Empresa@2026" not in saida.err
