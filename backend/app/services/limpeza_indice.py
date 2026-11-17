"""Limpeza do índice do Chroma, que é descartável depois da geração.

O pipeline só lê os trechos de um documento durante o job que o gerou. Por
isso:

- ``remover_indice`` apaga as linhas do documento ao fim de cada job (sucesso,
  falha, cancelamento ou prazo excedido);
- ``varrer_indices_orfaos`` roda na subida e apaga as linhas que jobs
  interrompidos (por exemplo, por reinício) deixaram para trás.

As duas são best-effort: uma falha vira ``logger.warning`` e nunca muda o
resultado do job nem impede a subida. Nenhuma cria a pasta do Chroma: se ela
não existe e nenhum cliente foi injetado, não há nada a limpar.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import chromadb

from app.rag import armazenamento, config
from app.services import repositorio

logger = logging.getLogger(__name__)

# documento_id criado pelo worker: "doc_" + ULID (26 caracteres, Crockford maiúsculo).
_DOCUMENTO_DO_PIPELINE = re.compile(r"doc_[0-9A-HJKMNP-TV-Z]{26}")


def _cliente_disponivel() -> chromadb.ClientAPI | None:
    """Cliente já em uso, ou um novo só se a pasta do Chroma já existir."""
    cliente = armazenamento.cliente_atual()
    if cliente is not None:
        return cliente
    if Path(config.CHROMA_DIR).is_dir():
        return armazenamento.obter_cliente()
    return None


def documento_do_pipeline(documento_id: str) -> bool:
    """True se o id tem a forma que o worker cria (``doc_<ULID>``)."""
    return _DOCUMENTO_DO_PIPELINE.fullmatch(documento_id) is not None


def remover_indice(documento_id: str) -> bool:
    """Apaga as linhas do documento; devolve se havia alguma. Nunca levanta."""
    try:
        if _cliente_disponivel() is None:
            return False
        return armazenamento.remover_documento(documento_id)
    except Exception as exc:  # best-effort: o job já terminou
        logger.warning(
            "Não foi possível remover o índice do documento %s (%s).",
            documento_id,
            type(exc).__name__,
        )
        return False


def varrer_indices_orfaos() -> int:
    """Apaga as linhas de documentos do pipeline sem job em andamento.

    Só considera ``documento_id`` no formato ``doc_<ULID>``; o resto não é
    tocado. Preserva os documentos de jobs ``queued`` ou ``running`` no banco.
    Devolve quantas linhas removeu. Nunca levanta.
    """
    try:
        if _cliente_disponivel() is None:
            return 0
        em_andamento = {f"doc_{job_id}" for job_id in repositorio.jobs_em_andamento()}
        orfaos = {
            documento_id: linhas
            for documento_id, linhas in armazenamento.documentos_indexados().items()
            if documento_do_pipeline(documento_id) and documento_id not in em_andamento
        }
    except Exception as exc:
        logger.warning("Varredura do índice do Chroma não executada (%s).", type(exc).__name__)
        return 0

    removidas = 0
    for documento_id, linhas in sorted(orfaos.items()):
        try:
            if armazenamento.remover_documento(documento_id):
                removidas += linhas
        except Exception as exc:
            logger.warning(
                "Não foi possível remover o índice órfão %s (%s).", documento_id, type(exc).__name__
            )
    logger.info(
        "Varredura do índice do Chroma: %d linhas órfãs removidas (%d documentos).",
        removidas,
        len(orfaos),
    )
    return removidas
