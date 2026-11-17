"""Schemas de alunos da área da empresa."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import FormatoSaida, PerfilDestinatario
from app.models.materiais import VisibilidadeMaterial

StatusAluno = Literal["ativo", "inativo"]


def _normalizar_email(valor: object) -> object:
    """Remove espaços e coloca o e-mail em minúsculas antes da validação."""
    if isinstance(valor, str):
        return valor.strip().lower()
    return valor


NomeAluno = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)
]
EmailAluno = Annotated[
    EmailStr,
    BeforeValidator(_normalizar_email),
    Field(max_length=254),
]


class AlunoCriacao(BaseModel):
    """Corpo de ``POST /api/v1/alunos``."""

    nome: NomeAluno
    email: EmailAluno
    status: StatusAluno = "ativo"


class AlunoAtualizacao(BaseModel):
    """Corpo de ``PATCH /api/v1/alunos/{aluno_id}``.

    Apenas ``nome``, ``email`` e ``status`` são editáveis; campos desconhecidos
    são rejeitados e ao menos um campo deve ser informado.
    """

    model_config = ConfigDict(extra="forbid")

    nome: NomeAluno | None = None
    email: EmailAluno | None = None
    status: StatusAluno | None = None

    @model_validator(mode="after")
    def _exige_ao_menos_um_campo(self) -> "AlunoAtualizacao":
        if self.nome is None and self.email is None and self.status is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class AlunoResumo(BaseModel):
    """Item de ``GET /api/v1/alunos`` e resposta de create/get/patch."""

    aluno_id: str
    nome: str
    email: str
    status: StatusAluno
    total_materiais: int
    criado_em: str
    atualizado_em: str


class PaginaAlunos(BaseModel):
    """Resposta paginada de ``GET /api/v1/alunos``."""

    itens: list[AlunoResumo]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class VinculoMaterial(BaseModel):
    """Item de ``GET /api/v1/alunos/{aluno_id}/materiais``."""

    material_id: str
    titulo: str
    formato: FormatoSaida
    perfil: PerfilDestinatario
    visibilidade: VisibilidadeMaterial
    vinculado_em: str


class VinculosAluno(BaseModel):
    """Resposta de ``GET/PUT /api/v1/alunos/{aluno_id}/materiais``."""

    aluno_id: str
    itens: list[VinculoMaterial]


class AtualizarVinculosInput(BaseModel):
    """Corpo de ``PUT /api/v1/alunos/{aluno_id}/materiais``.

    O conjunto inteiro de vínculos é substituído; até 500 ids são aceitos.
    """

    material_ids: list[str] = Field(max_length=500)
