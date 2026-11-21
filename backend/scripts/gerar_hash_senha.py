"""Gera o hash da senha da empresa para ``EMPRESA_SENHA_HASH``.

Uso (a partir de ``backend/``)::

    python scripts/gerar_hash_senha.py

A senha é lida sem eco, duas vezes, e precisa atender à política (a mesma
das rotas). A saída padrão recebe só o hash; avisos vão para a saída de erro.
A senha não é aceita como argumento para não ficar no histórico do shell.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.senhas import gerar_hash, mensagem_da_politica  # noqa: E402


def main(argv: list[str] | None = None, ler_senha=getpass.getpass) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if argumentos:
        print("Este script não aceita argumentos: a senha é pedida sem eco.", file=sys.stderr)
        return 2
    senha = ler_senha("Senha da empresa: ")
    problema = mensagem_da_politica(senha)
    if problema:
        print(problema, file=sys.stderr)
        return 1
    if ler_senha("Repita a senha: ") != senha:
        print("As senhas não conferem.", file=sys.stderr)
        return 1
    print(gerar_hash(senha))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
