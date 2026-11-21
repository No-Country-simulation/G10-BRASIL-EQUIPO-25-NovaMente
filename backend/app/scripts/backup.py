"""Gera um backup do SQLite: ``python -m app.scripts.backup``.

Lê ``DB_PATH``, ``BACKUP_DIR`` e ``BACKUP_RETENCAO`` (ambiente ou ``.env``).
Saída em português; código 0 em sucesso, 1 em falha do backup ou da configuração
e 2 se o backup foi gerado mas a retenção não conseguiu limpar os antigos.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

from app.services.backup import ErroBackup, ErroRetencao, aplicar_retencao, gerar_backup


def _erro(mensagem: str) -> None:
    print(f"Erro: {mensagem}", file=sys.stderr)


def main() -> int:
    try:
        from app.core.config import settings
    except ValidationError as exc:
        campos = ", ".join(str(e["loc"][0]).upper() for e in exc.errors() if e["loc"])
        _erro(f"Configuração inválida ({campos}). Corrija o .env ou o ambiente; BACKUP_RETENCAO deve ser 1 ou mais.")
        return 1

    from app.core.preparo_banco import caminhos_do_banco

    origem = Path(settings.db_path).expanduser()
    pasta = Path(settings.backup_dir).expanduser()

    # O catálogo (materiais, alunos, vínculos) mora em DATABASE_URL; só entra no backup
    # se for o mesmo arquivo de DB_PATH, que é o padrão.
    if len(caminhos_do_banco(settings.db_path, settings.database_url)) > 1:
        print(
            "Aviso: DATABASE_URL aponta para um arquivo diferente de DB_PATH. O backup copia "
            "apenas o arquivo de DB_PATH; o catálogo não está incluído.",
            file=sys.stderr,
        )

    try:
        resultado = gerar_backup(origem, pasta)
    except ErroBackup as exc:
        _erro(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - a mensagem original pode conter caminhos
        _erro(f"Falha inesperada ao gerar o backup ({type(exc).__name__}).")
        return 1

    print(f"Backup gerado: {resultado.arquivo}")
    print(
        f"Tamanho: {resultado.tamanho_bytes} bytes; tabelas: {resultado.tabelas}; "
        "integridade: ok."
    )

    try:
        removidos = aplicar_retencao(pasta, settings.backup_retencao)
    except ErroRetencao as exc:
        _erro(str(exc))
        return 2
    print(f"Retenção: mantidos os {settings.backup_retencao} mais recentes; removidos {len(removidos)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
