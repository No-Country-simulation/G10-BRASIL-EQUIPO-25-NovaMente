"""Módulo RAG do NovaMente: divide, indexa e recupera trechos de um documento.

Uso pelo endpoint:

    from app.rag import indexar_documento, recuperar

Detalhes do que fica para quem integra estão em `servico.py`.
"""

from app.rag.modelos import ResultadoIndexacao, Trecho
from app.rag.servico import indexar_documento, recuperar

__all__ = ["indexar_documento", "recuperar", "Trecho", "ResultadoIndexacao"]
