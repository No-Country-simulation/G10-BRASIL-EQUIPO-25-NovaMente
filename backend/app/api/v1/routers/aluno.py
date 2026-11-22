"""Router da área do aluno — identificação e catálogo somente leitura."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    FormatoSaida,
    IdentificacaoAlunoResposta,
    MaterialDetalhe,
    PaginaCatalogoAluno,
    PerfilDestinatario,
)
from app.models.db import AlunoDB
from app.services import alunos as alunos_service
from app.services import materiais as materiais_service

router = APIRouter(prefix="/aluno", tags=["aluno"])

OrdenacaoCatalogoAluno = Literal["criado_em:desc", "titulo:asc"]


def _aluno_nao_encontrado() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "erro": {
                "codigo": "ALUNO_NAO_ENCONTRADO",
                "mensagem": "Aluno não encontrado.",
            }
        },
    )


def _aluno_inativo() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "erro": {
                "codigo": "ALUNO_INATIVO",
                "mensagem": "Aluno inativo.",
            }
        },
    )


def _material_nao_disponivel() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "erro": {
                "codigo": "MATERIAL_NAO_DISPONIVEL",
                "mensagem": "Material não disponível.",
            }
        },
    )


def _pacote_corrompido() -> HTTPException:
    return HTTPException(
        status_code=500,
        detail={
            "erro": {
                "codigo": "INTERNO",
                "mensagem": "Pacote de material corrompido.",
                "request_id": str(uuid.uuid4()),
            }
        },
    )


def _obter_aluno_ativo(db: Session, aluno_id: str) -> AlunoDB:
    """Carrega o aluno, distinguindo inexistente (404) de inativo (403)."""
    row = alunos_service.obter_aluno(db, aluno_id)
    if row is None:
        raise _aluno_nao_encontrado()
    if row.status != "ativo":
        raise _aluno_inativo()
    return row


# ── GET /aluno/identificacao ──────────────────────────────────────────────────


@router.get("/identificacao", response_model=IdentificacaoAlunoResposta)
def identificacao(db: Session = Depends(get_db)) -> IdentificacaoAlunoResposta:
    """Lista os alunos ativos para identificação na área do aluno."""
    return alunos_service.identificacao_de_alunos(db)


# ── GET /aluno/materiais ──────────────────────────────────────────────────────


@router.get("/materiais", response_model=PaginaCatalogoAluno)
def listar_materiais(
    aluno_id: Annotated[str, Query(min_length=1)],
    db: Session = Depends(get_db),
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=50)] = 12,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    formato: FormatoSaida | None = None,
    perfil: PerfilDestinatario | None = None,
    ordenar: OrdenacaoCatalogoAluno = "criado_em:desc",
) -> PaginaCatalogoAluno:
    """Catálogo paginado com apenas materiais publicados e vinculados."""
    _obter_aluno_ativo(db, aluno_id)
    return alunos_service.listar_catalogo_aluno(
        db,
        aluno_id,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        q=q,
        formato=formato,
        perfil=perfil,
        ordenar=ordenar,
    )


# ── GET /aluno/materiais/{material_id} ────────────────────────────────────────


@router.get("/materiais/{material_id}", response_model=MaterialDetalhe)
def obter_material(
    material_id: str,
    aluno_id: Annotated[str, Query(min_length=1)],
    db: Session = Depends(get_db),
) -> MaterialDetalhe:
    """Detalhe apenas se publicado e vinculado; demais casos → 404 unificado."""
    _obter_aluno_ativo(db, aluno_id)
    row = alunos_service.material_do_aluno(db, aluno_id, material_id)
    if row is None:
        raise _material_nao_disponivel()

    try:
        pacote = materiais_service.pacote_de_material(row)
    except ValidationError as exc:
        raise _pacote_corrompido() from exc

    return MaterialDetalhe(
        material=materiais_service.resumo_de_material(row),
        pacote=pacote,
    )
