"""Schemas somente leitura da área do aluno."""

from __future__ import annotations

from pydantic import BaseModel

from app.models import FormatoSaida, NivelDetalhe, PerfilDestinatario


class IdentificacaoAlunoItem(BaseModel):
    """Item de ``GET /api/v1/aluno/identificacao``; nunca expõe e-mail."""

    aluno_id: str
    nome: str


class IdentificacaoAlunoResposta(BaseModel):
    """Resposta de ``GET /api/v1/aluno/identificacao``."""

    itens: list[IdentificacaoAlunoItem]


class ItemCatalogoAluno(BaseModel):
    """Item do catálogo do aluno — subconjunto de ``MaterialResumo``."""

    material_id: str
    titulo: str
    documento_titulo: str
    formato: FormatoSaida
    perfil: PerfilDestinatario
    nivel: NivelDetalhe
    tempo_estimado_estudo_minutos: int
    criado_em: str
    conceitos_chave: list[str]


class PaginaCatalogoAluno(BaseModel):
    """Resposta paginada de ``GET /api/v1/aluno/materiais``."""

    itens: list[ItemCatalogoAluno]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int
