"""Libera o disco que o Chroma deixa para trás (chromadb 1.5.9).

Neste Chroma, ``delete_collection`` tira a collection do catálogo mas não
remove do disco o diretório do seu segmento HNSW (``<CHROMA_DIR>/<uuid>/``),
nem ao reabrir. Este módulo:

- remove as collections legadas (uma por documento, de versões anteriores);
- coleta os diretórios de segmento que nenhum segmento vivo do catálogo
  referencia.

A coleta depende do formato interno do Chroma: o catálogo é o SQLite
``chroma.sqlite3`` na raiz da pasta, a tabela ``segments`` tem a coluna
``id``, e o diretório de cada segmento vetorial tem o nome desse id. O teste
canário em tests/services/test_limpeza_disco_chroma.py falha se isso mudar;
revise este módulo ao atualizar o ``chromadb``.

Na dúvida, nada é apagado: cada trava abaixo precisa passar.
"""

from __future__ import annotations

import logging
import re
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import chromadb

from app.rag import config

logger = logging.getLogger(__name__)

PREFIXO_COLLECTION_LEGADA = "doc_"  # nome das collections por documento das versões antigas
IDADE_MINIMA_ORFAO_SEGUNDOS = 3600  # nunca competir com um segmento recém-criado
ARQUIVO_CATALOGO = "chroma.sqlite3"
ESPERA_CATALOGO_SEGUNDOS = 2.0  # se o catálogo estiver travado, desiste e não apaga nada
TABELA_SEGMENTOS = "segments"
COLUNA_ID_SEGMENTO = "id"
# Arquivos que o Chroma 1.5.9 grava num diretório de segmento HNSW.
ARQUIVOS_HNSW = frozenset(
    {"data_level0.bin", "header.bin", "length.bin", "link_lists.bin", "index_metadata.pickle"}
)
# documento_id criado pelo worker: "doc_" + ULID (26 caracteres, Crockford maiúsculo).
_DOCUMENTO_DO_PIPELINE = re.compile(r"doc_[0-9A-HJKMNP-TV-Z]{26}")


class CatalogoIlegivel(Exception):
    """O catálogo do Chroma não existe, não abre ou não tem o formato esperado."""


@dataclass
class ResultadoColeta:
    diretorios: int = 0
    bytes_liberados: int = 0


def documento_do_pipeline(documento_id: str) -> bool:
    """True se o id tem a forma que o worker cria (``doc_<ULID>``)."""
    return _DOCUMENTO_DO_PIPELINE.fullmatch(documento_id) is not None


# ── Collections legadas ───────────────────────────────────────────────────────


def collection_legada(nome: str, metadados: dict | None) -> bool:
    """True para a collection por documento que o pipeline antigo criava."""
    documento_id = (metadados or {}).get("documento_id")
    return (
        nome.startswith(PREFIXO_COLLECTION_LEGADA)
        and nome != config.NOME_COLLECTION
        and isinstance(documento_id, str)
        and documento_do_pipeline(documento_id)
    )


def remover_collections_legadas(cliente: chromadb.ClientAPI) -> int:
    """Apaga do catálogo as collections legadas; devolve quantas apagou."""
    removidas = 0
    for colecao in cliente.list_collections():
        if not collection_legada(colecao.name, colecao.metadata):
            continue
        try:
            cliente.delete_collection(colecao.name)
            removidas += 1
        except Exception as exc:
            logger.warning(
                "Não foi possível remover a collection legada %s (%s).",
                colecao.name,
                type(exc).__name__,
            )
    return removidas


# ── Coleta de diretórios órfãos ───────────────────────────────────────────────


def pasta_do_cliente(cliente: chromadb.ClientAPI) -> Path:
    """Pasta que o cliente realmente usa (a de ``CHROMA_DIR``, salvo nos testes)."""
    return Path(cliente.get_settings().persist_directory or "")


def pasta_suspeita(pasta: Path) -> str | None:
    """Motivo para recusar a pasta, ou None se ela pode ser varrida."""
    if not str(pasta).strip() or str(pasta) == ".":
        return "caminho vazio"
    resolvida = pasta.resolve()
    if resolvida == Path(resolvida.anchor):
        return "raiz do sistema"
    try:
        casa = Path.home().resolve()
    except (RuntimeError, KeyError):
        casa = None
    if casa is not None and (resolvida == casa or casa.is_relative_to(resolvida)):
        return "pasta pessoal do usuário ou acima dela"
    if not resolvida.is_dir():
        return "não é uma pasta"
    return None


def segmentos_vivos(pasta: Path) -> set[str]:
    """Ids de todos os segmentos do catálogo, lido em modo somente leitura.

    Confere a tabela e a coluna antes de ler; levanta ``CatalogoIlegivel``
    se algo não estiver como no Chroma 1.5.9.
    """
    catalogo = pasta / ARQUIVO_CATALOGO
    if not catalogo.is_file():
        raise CatalogoIlegivel(f"{ARQUIVO_CATALOGO} não encontrado")
    try:
        conexao = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True, timeout=ESPERA_CATALOGO_SEGUNDOS)
        try:
            colunas = {linha[1] for linha in conexao.execute(f"PRAGMA table_info({TABELA_SEGMENTOS})")}
            if COLUNA_ID_SEGMENTO not in colunas:
                raise CatalogoIlegivel(
                    f"tabela {TABELA_SEGMENTOS}.{COLUNA_ID_SEGMENTO} ausente no catálogo"
                )
            linhas = conexao.execute(
                f"SELECT {COLUNA_ID_SEGMENTO} FROM {TABELA_SEGMENTOS}"
            ).fetchall()
        finally:
            conexao.close()
    except sqlite3.Error as exc:
        raise CatalogoIlegivel(type(exc).__name__) from exc
    return {str(valor) for (valor,) in linhas}


def tem_diretorio_vetorial(pasta: Path, id_collection: str) -> bool:
    """True se o segmento vetorial da collection já tem diretório no disco.

    Uma collection recém-criada só ganha diretório no primeiro ``add``; é o
    que torna a rotação idempotente. Catálogo ilegível => False.
    """
    catalogo = pasta / ARQUIVO_CATALOGO
    try:
        conexao = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True, timeout=ESPERA_CATALOGO_SEGUNDOS)
        try:
            linhas = conexao.execute(
                f"SELECT {COLUNA_ID_SEGMENTO} FROM {TABELA_SEGMENTOS} "
                "WHERE collection = ? AND scope = 'VECTOR'",
                (id_collection,),
            ).fetchall()
        finally:
            conexao.close()
    except sqlite3.Error:
        return False
    return any((pasta / str(segmento)).is_dir() for (segmento,) in linhas)


def _nome_uuid(nome: str) -> bool:
    try:
        return str(uuid.UUID(nome)) == nome
    except ValueError:
        return False


def _motivo_para_manter(diretorio: Path, pasta: Path, vivos: set[str], agora: float) -> str | None:
    """Motivo para NÃO apagar o diretório, ou None se ele é órfão com certeza."""
    if diretorio.is_symlink():
        return "link simbólico"
    if not diretorio.is_dir():
        return "não é diretório"
    if not _nome_uuid(diretorio.name):
        return "nome não é UUID"
    if diretorio.resolve().parent != pasta:
        return "fora da pasta do Chroma"
    if diretorio.name in vivos:
        return "segmento vivo"
    itens = list(diretorio.iterdir())
    if any(i.is_symlink() or not i.is_file() or i.name not in ARQUIVOS_HNSW for i in itens):
        return "conteúdo que não é de índice HNSW"
    mais_recente = max([diretorio.stat().st_mtime, *(i.stat().st_mtime for i in itens)])
    if agora - mais_recente < IDADE_MINIMA_ORFAO_SEGUNDOS:
        return "modificado há menos tempo que a idade mínima"
    return None


def coletar_diretorios_orfaos(pasta_chroma: Path) -> ResultadoColeta:
    """Remove os diretórios de segmento órfãos de ``pasta_chroma``.

    Nada é apagado se a pasta for suspeita ou o catálogo não puder ser lido.
    """
    resultado = ResultadoColeta()
    motivo = pasta_suspeita(pasta_chroma)
    if motivo:
        logger.warning("Coleta de diretórios do Chroma recusada (%s): %s.", motivo, pasta_chroma)
        return resultado
    pasta = pasta_chroma.resolve()
    try:
        vivos = segmentos_vivos(pasta)
    except CatalogoIlegivel as exc:
        logger.warning("Coleta de diretórios do Chroma não executada: catálogo ilegível (%s).", exc)
        return resultado

    agora = time.time()
    for diretorio in sorted(pasta.iterdir()):
        try:
            if _motivo_para_manter(diretorio, pasta, vivos, agora):
                continue
            tamanho = sum(f.stat().st_size for f in diretorio.iterdir())
            shutil.rmtree(diretorio)
            resultado.diretorios += 1
            resultado.bytes_liberados += tamanho
        except Exception as exc:
            logger.warning(
                "Não foi possível remover o diretório órfão %s do Chroma (%s).",
                diretorio.name,
                type(exc).__name__,
            )
    return resultado
