"""Conversão entre pacotes de adaptação e linhas da tabela ``materiais``."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models import AdaptacaoPacote, AdaptacaoResumo, DocumentoRef, MaterialResumo
from app.models.db import MaterialDB

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_TITULO_MAX = 150


def material_de_pacote(session: "Session", pacote: AdaptacaoPacote) -> MaterialDB:
    """Cria ou atualiza a linha do material correspondente ao pacote.

    Colunas desnormalizadas são sempre atualizadas a partir do pacote. Em uma
    linha já existente, ``titulo`` e ``visibilidade`` são preservados porque
    podem ter sido editados pela interface.
    """
    row = session.scalar(
        select(MaterialDB).where(MaterialDB.adaptacao_id == pacote.adaptacao_id)
    )
    if row is None:
        row = MaterialDB(
            material_id=pacote.adaptacao_id,
            adaptacao_id=pacote.adaptacao_id,
            titulo=pacote.conteudo_adaptado.titulo[:_TITULO_MAX],
            visibilidade="rascunho",
            criado_em=pacote.criado_em,
        )
        session.add(row)

    row.documento_titulo = pacote.documento.titulo
    row.documento_origem = pacote.documento.origem
    row.documento_nome_arquivo = pacote.documento.nome_arquivo
    row.documento_tamanho_bytes = pacote.documento.tamanho_bytes
    row.perfil = pacote.metadados.perfil_aplicado
    row.formato = pacote.metadados.formato_gerado
    row.nivel = pacote.metadados.nivel_detalhe_aplicado
    row.nicho = pacote.metadados.nicho_setor_aplicado
    row.tempo_estimado_minutos = pacote.metadados.tempo_estimado_estudo_minutos
    row.ancoragem_score = pacote.avaliacao_qualidade.ancoragem_fonte_score
    row.status_upload = pacote.armazenamento_oci.status_upload
    row.conceitos_chave_json = json.dumps(
        pacote.metadados.conceitos_chave, ensure_ascii=False
    )
    row.oci_objeto_id = pacote.armazenamento_oci.objeto_id
    row.pacote_json = pacote.model_dump_json()
    row.atualizado_em = datetime.now(timezone.utc).isoformat()
    return row


def pacote_de_material(row: MaterialDB) -> AdaptacaoPacote:
    """Reconstrói o pacote a partir do JSON persistido na linha."""
    return AdaptacaoPacote.model_validate_json(row.pacote_json)


def resumo_de_adaptacao(row: MaterialDB) -> AdaptacaoResumo:
    """Monta o resumo da listagem apenas com colunas desnormalizadas.

    Não toca em ``pacote_json``: listagens nunca desserializam o pacote.
    """
    return AdaptacaoResumo(
        adaptacao_id=row.adaptacao_id,
        criado_em=row.criado_em,
        documento=DocumentoRef(
            titulo=row.documento_titulo,
            origem=row.documento_origem,
            nome_arquivo=row.documento_nome_arquivo,
            tamanho_bytes=row.documento_tamanho_bytes,
        ),
        perfil_aplicado=row.perfil,
        formato_gerado=row.formato,
        nivel_detalhe_aplicado=row.nivel,
        nicho_setor_aplicado=row.nicho,
        tempo_estimado_estudo_minutos=row.tempo_estimado_minutos,
        ancoragem_fonte_score=row.ancoragem_score,
        status_upload=row.status_upload,
        conceitos_chave=json.loads(row.conceitos_chave_json)[:6],
    )


def resumo_de_material(row: MaterialDB) -> MaterialResumo:
    """Monta o resumo do catálogo a partir das colunas desnormalizadas.

    Assim como ``resumo_de_adaptacao``, nunca abre ``pacote_json``: a
    listagem continua funcionando mesmo se o pacote estiver corrompido.
    """
    return MaterialResumo(
        material_id=row.material_id,
        adaptacao_id=row.adaptacao_id,
        titulo=row.titulo,
        documento_titulo=row.documento_titulo,
        perfil=row.perfil,
        formato=row.formato,
        nivel=row.nivel,
        nicho=row.nicho,
        visibilidade=row.visibilidade,
        tempo_estimado_estudo_minutos=row.tempo_estimado_minutos,
        ancoragem_fonte_score=row.ancoragem_score,
        status_upload=row.status_upload,
        criado_em=row.criado_em,
        atualizado_em=row.atualizado_em,
    )
