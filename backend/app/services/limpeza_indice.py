"""Limpeza do índice do Chroma, que é descartável depois da geração.

O pipeline só lê os trechos de um documento durante o job que o gerou. Por
isso:

- ``remover_indice`` apaga as linhas do documento ao fim de cada job (sucesso,
  falha, cancelamento ou prazo excedido);
- ``varrer_indices_orfaos`` roda na subida e, em etapas independentes, apaga
  as linhas que jobs interrompidos (por exemplo, por reinício) deixaram para
  trás, remove as collections legadas (uma por documento), recria a
  collection compartilhada quando ela está vazia e sem jobs em andamento, e
  coleta os diretórios de segmento que o Chroma 1.5.9 não remove do disco
  (``limpeza_disco_chroma``).

Tudo é best-effort: uma falha vira ``logger.warning`` e nunca muda o
resultado do job nem impede a subida. Nada cria a pasta do Chroma: se ela
não existe e nenhum cliente foi injetado, não há nada a limpar.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

from app.rag import armazenamento, config
from app.services import limpeza_disco_chroma, repositorio
from app.services.limpeza_disco_chroma import documento_do_pipeline

logger = logging.getLogger(__name__)


def _cliente_disponivel() -> chromadb.ClientAPI | None:
    """Cliente já em uso, ou um novo só se a pasta do Chroma já existir."""
    cliente = armazenamento.cliente_atual()
    if cliente is not None:
        return cliente
    if Path(config.CHROMA_DIR).is_dir():
        return armazenamento.obter_cliente()
    return None


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


def _remover_linhas_orfas() -> tuple[int, int]:
    """Etapa 1: linhas de documentos do pipeline sem job em andamento.

    Só considera ``documento_id`` no formato ``doc_<ULID>``; o resto não é
    tocado. Preserva os documentos de jobs ``queued`` ou ``running`` no banco.
    Devolve (linhas removidas, documentos órfãos).
    """
    try:
        em_andamento = {f"doc_{job_id}" for job_id in repositorio.jobs_em_andamento()}
        orfaos = {
            documento_id: linhas
            for documento_id, linhas in armazenamento.documentos_indexados().items()
            if documento_do_pipeline(documento_id) and documento_id not in em_andamento
        }
    except Exception as exc:
        logger.warning("Varredura do índice do Chroma não executada (%s).", type(exc).__name__)
        return 0, 0

    removidas = 0
    for documento_id, linhas in sorted(orfaos.items()):
        try:
            if armazenamento.remover_documento(documento_id):
                removidas += linhas
        except Exception as exc:
            logger.warning(
                "Não foi possível remover o índice órfão %s (%s).", documento_id, type(exc).__name__
            )
    return removidas, len(orfaos)


def _etapa(nome: str, funcao, padrao):
    """Executa uma etapa da varredura; uma exceção vira aviso e o valor padrão."""
    try:
        return funcao()
    except Exception as exc:
        logger.warning("Varredura do índice do Chroma: etapa %s não executada (%s).", nome, type(exc).__name__)
        return padrao


def varrer_indices_orfaos() -> int:
    """Limpa o índice na subida, em quatro etapas independentes e best-effort.

    1. Linhas órfãs da collection compartilhada (``_remover_linhas_orfas``).
    2. Collections legadas, uma por documento, das versões antigas.
    3. Rotação: sem linhas vivas, sem jobs ``queued``/``running`` no banco e
       com o índice HNSW já gravado no disco, a collection compartilhada é
       recriada para o HNSW começar vazio.
    4. Coleta dos diretórios de segmento que o Chroma deixou no disco.

    Devolve quantas linhas órfãs removeu. Nunca levanta.
    """
    try:
        cliente = _cliente_disponivel()
    except Exception as exc:
        logger.warning("Varredura do índice do Chroma não executada (%s).", type(exc).__name__)
        return 0
    if cliente is None:
        return 0

    linhas, documentos = _remover_linhas_orfas()
    legadas = _etapa(
        "collections legadas",
        lambda: limpeza_disco_chroma.remover_collections_legadas(cliente),
        0,
    )
    rotacionou = _etapa(
        "rotação",
        lambda: armazenamento.recriar_colecao_se_vazia(
            lambda id_collection: not repositorio.jobs_em_andamento()
            and limpeza_disco_chroma.tem_diretorio_vetorial(
                limpeza_disco_chroma.pasta_do_cliente(cliente).resolve(), id_collection
            )
        ),
        False,
    )
    coleta = _etapa(
        "coleta de diretórios",
        lambda: limpeza_disco_chroma.coletar_diretorios_orfaos(
            limpeza_disco_chroma.pasta_do_cliente(cliente)
        ),
        limpeza_disco_chroma.ResultadoColeta(),
    )
    logger.info(
        "Varredura do índice do Chroma: %d linhas órfãs removidas (%d documentos), "
        "%d collections legadas removidas, rotação %s, %d diretórios órfãos removidos "
        "(%.1f MB liberados).",
        linhas,
        documentos,
        legadas,
        "feita" if rotacionou else "não feita",
        coleta.diretorios,
        coleta.bytes_liberados / 1e6,
    )
    return linhas
