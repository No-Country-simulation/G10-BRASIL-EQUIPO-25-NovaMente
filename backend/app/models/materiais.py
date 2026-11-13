"""Schemas do catálogo de materiais da área da empresa."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import (
    AdaptacaoPacote,
    FormatoSaida,
    NichoSetor,
    NivelDetalhe,
    PerfilDestinatario,
)

VisibilidadeMaterial = Literal["rascunho", "publicado"]

TituloMaterial = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)
]


class MaterialResumo(BaseModel):
    """Item da listagem de ``GET /api/v1/materiais``."""

    material_id: str
    adaptacao_id: str
    titulo: str
    documento_titulo: str
    perfil: PerfilDestinatario
    formato: FormatoSaida
    nivel: NivelDetalhe
    nicho: NichoSetor
    visibilidade: VisibilidadeMaterial
    tempo_estimado_estudo_minutos: int
    ancoragem_fonte_score: float
    status_upload: Literal["concluido", "falha"]
    criado_em: str
    atualizado_em: str


class MaterialDetalhe(BaseModel):
    """Resposta de ``GET /api/v1/materiais/{material_id}``."""

    material: MaterialResumo
    pacote: AdaptacaoPacote


class MaterialAtualizacao(BaseModel):
    """Corpo de ``PATCH /api/v1/materiais/{material_id}``.

    Somente título e visibilidade são editáveis; qualquer outro campo é
    rejeitado e ao menos um campo deve ser informado.
    """

    model_config = ConfigDict(extra="forbid")

    titulo: TituloMaterial | None = None
    visibilidade: VisibilidadeMaterial | None = None

    @model_validator(mode="after")
    def _exige_ao_menos_um_campo(self) -> "MaterialAtualizacao":
        if self.titulo is None and self.visibilidade is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self


class PaginaMateriais(BaseModel):
    """Resposta paginada de ``GET /api/v1/materiais``."""

    itens: list[MaterialResumo]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class RemocaoMaterialResposta(BaseModel):
    """Resposta de ``DELETE /api/v1/materiais/{material_id}``."""

    material_id: str
    removido: Literal[True] = True
    oci_removido: bool
    aviso: str | None = None
