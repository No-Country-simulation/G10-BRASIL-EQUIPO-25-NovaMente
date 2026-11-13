"""Router de alunos (empresa) — cadastro, consulta, edição e exclusão."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    AlunoAtualizacao,
    AlunoCriacao,
    AlunoResumo,
    AtualizarVinculosInput,
    PaginaAlunos,
    StatusAluno,
    VinculoMaterial,
    VinculosAluno,
)
from app.models.db import AlunoDB, MaterialDB
from app.services import alunos as alunos_service

router = APIRouter(prefix="/alunos", tags=["alunos"])

OrdenacaoAluno = Literal["nome:asc", "nome:desc", "criado_em:desc"]

_MENSAGEM_EMAIL_CADASTRADO = "E-mail já cadastrado."


def _nao_encontrado() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "erro": {
                "codigo": "ALUNO_NAO_ENCONTRADO",
                "mensagem": "Aluno não encontrado.",
            }
        },
    )


def _email_duplicado() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "erro": {
                "codigo": "EMAIL_JA_CADASTRADO",
                "mensagem": _MENSAGEM_EMAIL_CADASTRADO,
                "campos": {"email": _MENSAGEM_EMAIL_CADASTRADO},
            }
        },
    )


def _material_nao_encontrado() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "erro": {
                "codigo": "MATERIAL_NAO_ENCONTRADO",
                "mensagem": "Material não encontrado.",
            }
        },
    )


def _materiais_inexistentes(material_ids: list[str]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "erro": {
                "codigo": "VALIDACAO",
                "mensagem": "Dados de entrada inválidos.",
                "campos": {
                    "material_ids": "Materiais não encontrados: "
                    + ", ".join(material_ids)
                    + "."
                },
            }
        },
    )


def _obter_ou_404(db: Session, aluno_id: str) -> AlunoDB:
    row = alunos_service.obter_aluno(db, aluno_id)
    if row is None:
        raise _nao_encontrado()
    return row


def _obter_material_ou_404(db: Session, material_id: str) -> MaterialDB:
    row = db.get(MaterialDB, material_id)
    if row is None:
        raise _material_nao_encontrado()
    return row


# ── GET /alunos ───────────────────────────────────────────────────────────────


@router.get("", response_model=PaginaAlunos)
def listar(
    db: Session = Depends(get_db),
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=50)] = 12,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    status: StatusAluno | None = None,
    ordenar: OrdenacaoAluno = "nome:asc",
) -> PaginaAlunos:
    """Lista paginada de alunos, filtrável e ordenável em SQL."""
    return alunos_service.listar_alunos(
        db,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        q=q,
        status=status,
        ordenar=ordenar,
    )


# ── POST /alunos ──────────────────────────────────────────────────────────────


@router.post("", status_code=201, response_model=AlunoResumo)
def criar(body: AlunoCriacao, db: Session = Depends(get_db)) -> AlunoResumo:
    """Cadastra um aluno com e-mail normalizado e único."""
    try:
        row = alunos_service.criar_aluno(db, body)
    except alunos_service.EmailJaCadastrado as exc:
        raise _email_duplicado() from exc
    return alunos_service.resumo_de_aluno(db, row)


# ── GET /alunos/{aluno_id} ────────────────────────────────────────────────────


@router.get("/{aluno_id}", response_model=AlunoResumo)
def obter(aluno_id: str, db: Session = Depends(get_db)) -> AlunoResumo:
    """Devolve os dados do aluno e a quantidade de materiais vinculados."""
    row = _obter_ou_404(db, aluno_id)
    return alunos_service.resumo_de_aluno(db, row)


# ── PATCH /alunos/{aluno_id} ──────────────────────────────────────────────────


@router.patch("/{aluno_id}", response_model=AlunoResumo)
def atualizar(
    aluno_id: str,
    body: AlunoAtualizacao,
    db: Session = Depends(get_db),
) -> AlunoResumo:
    """Edita nome, e-mail e/ou status do aluno."""
    row = _obter_ou_404(db, aluno_id)
    try:
        row = alunos_service.atualizar_aluno(db, row, body)
    except alunos_service.EmailJaCadastrado as exc:
        raise _email_duplicado() from exc
    return alunos_service.resumo_de_aluno(db, row)


# ── DELETE /alunos/{aluno_id} ─────────────────────────────────────────────────


@router.delete("/{aluno_id}", status_code=204)
def excluir(aluno_id: str, db: Session = Depends(get_db)) -> Response:
    """Remove o aluno; os vínculos caem em cascata e materiais são mantidos."""
    row = _obter_ou_404(db, aluno_id)
    alunos_service.excluir_aluno(db, row)
    return Response(status_code=204)


# ── GET /alunos/{aluno_id}/materiais ──────────────────────────────────────────


@router.get("/{aluno_id}/materiais", response_model=VinculosAluno)
def listar_vinculos(aluno_id: str, db: Session = Depends(get_db)) -> VinculosAluno:
    """Devolve todos os vínculos do aluno, sem paginação."""
    _obter_ou_404(db, aluno_id)
    return alunos_service.vinculos_do_aluno(db, aluno_id)


# ── PUT /alunos/{aluno_id}/materiais ──────────────────────────────────────────


@router.put("/{aluno_id}/materiais", response_model=VinculosAluno)
def substituir_vinculos(
    aluno_id: str,
    body: AtualizarVinculosInput,
    db: Session = Depends(get_db),
) -> VinculosAluno:
    """Substitui o conjunto inteiro de vínculos de forma atômica."""
    _obter_ou_404(db, aluno_id)
    try:
        alunos_service.substituir_vinculos(db, aluno_id, body.material_ids)
    except alunos_service.MateriaisInexistentes as exc:
        raise _materiais_inexistentes(exc.material_ids) from exc
    return alunos_service.vinculos_do_aluno(db, aluno_id)


# ── POST /alunos/{aluno_id}/materiais/{material_id} ───────────────────────────


@router.post(
    "/{aluno_id}/materiais/{material_id}", response_model=VinculoMaterial
)
def adicionar_vinculo(
    aluno_id: str,
    material_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> VinculoMaterial:
    """Cria o vínculo; responde 201 na criação e 200 se já existia."""
    _obter_ou_404(db, aluno_id)
    material = _obter_material_ou_404(db, material_id)
    row, criado = alunos_service.adicionar_vinculo(db, aluno_id, material_id)
    response.status_code = 201 if criado else 200
    return alunos_service.vinculo_de_material(material, row.criado_em)


# ── DELETE /alunos/{aluno_id}/materiais/{material_id} ─────────────────────────


@router.delete("/{aluno_id}/materiais/{material_id}", status_code=204)
def remover_vinculo(
    aluno_id: str, material_id: str, db: Session = Depends(get_db)
) -> Response:
    """Remove o vínculo; 204 mesmo quando ele não existia."""
    _obter_ou_404(db, aluno_id)
    _obter_material_ou_404(db, material_id)
    alunos_service.remover_vinculo(db, aluno_id, material_id)
    return Response(status_code=204)
