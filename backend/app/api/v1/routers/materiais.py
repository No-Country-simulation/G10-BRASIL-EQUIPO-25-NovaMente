"""Router de materiais (empresa) — listagem, detalhe, edição e exclusão."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import (
    FormatoSaida,
    MaterialAtualizacao,
    MaterialDetalhe,
    MaterialResumo,
    PaginaMateriais,
    PerfilDestinatario,
    RemocaoMaterialResposta,
    VisibilidadeMaterial,
)
from app.models.db import MaterialDB
from app.services import materiais as materiais_service
from app.services.oci import remover_objeto

router = APIRouter(prefix="/materiais", tags=["materiais"])

OrdenacaoMaterial = Literal[
    "criado_em:desc", "criado_em:asc", "ancoragem:desc", "titulo:asc"
]

_ORDENACAO = {
    "criado_em:desc": MaterialDB.criado_em.desc(),
    "criado_em:asc": MaterialDB.criado_em.asc(),
    "ancoragem:desc": MaterialDB.ancoragem_score.desc(),
    "titulo:asc": MaterialDB.titulo.asc(),
}


def _nao_encontrado() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "erro": {
                "codigo": "MATERIAL_NAO_ENCONTRADO",
                "mensagem": "Material não encontrado.",
            }
        },
    )


# ── GET /materiais ────────────────────────────────────────────────────────────


@router.get("", response_model=PaginaMateriais)
def listar(
    db: Session = Depends(get_db),
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=50)] = 12,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    formato: FormatoSaida | None = None,
    perfil: PerfilDestinatario | None = None,
    visibilidade: VisibilidadeMaterial | None = None,
    ordenar: OrdenacaoMaterial = "criado_em:desc",
) -> PaginaMateriais:
    """Lista paginada do catálogo, filtrável e ordenável em SQL."""
    condicoes = []
    if q:
        termo = f"%{q}%"
        condicoes.append(
            or_(
                MaterialDB.titulo.ilike(termo),
                MaterialDB.documento_titulo.ilike(termo),
            )
        )
    if formato:
        condicoes.append(MaterialDB.formato == formato)
    if perfil:
        condicoes.append(MaterialDB.perfil == perfil)
    if visibilidade:
        condicoes.append(MaterialDB.visibilidade == visibilidade)

    total = db.scalar(
        select(func.count()).select_from(MaterialDB).where(*condicoes)
    ) or 0

    linhas = db.scalars(
        select(MaterialDB)
        .where(*condicoes)
        .order_by(_ORDENACAO[ordenar], MaterialDB.material_id)
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
    ).all()

    total_paginas = (
        (total + tamanho_pagina - 1) // tamanho_pagina if total else 0
    )
    return PaginaMateriais(
        itens=[materiais_service.resumo_de_material(row) for row in linhas],
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=total_paginas,
    )


# ── GET /materiais/{material_id} ──────────────────────────────────────────────


@router.get("/{material_id}", response_model=MaterialDetalhe)
def obter(material_id: str, db: Session = Depends(get_db)) -> MaterialDetalhe:
    """Devolve o resumo e o pacote imutável do material."""
    row = db.get(MaterialDB, material_id)
    if row is None:
        raise _nao_encontrado()

    try:
        pacote = materiais_service.pacote_de_material(row)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "erro": {
                    "codigo": "INTERNO",
                    "mensagem": "Pacote de material corrompido.",
                    "request_id": str(uuid.uuid4()),
                }
            },
        ) from exc

    return MaterialDetalhe(
        material=materiais_service.resumo_de_material(row),
        pacote=pacote,
    )


# ── PATCH /materiais/{material_id} ────────────────────────────────────────────


@router.patch("/{material_id}", response_model=MaterialResumo)
def atualizar(
    material_id: str,
    body: MaterialAtualizacao,
    db: Session = Depends(get_db),
) -> MaterialResumo:
    """Edita título e/ou visibilidade do catálogo, nunca o pacote."""
    row = db.get(MaterialDB, material_id)
    if row is None:
        raise _nao_encontrado()

    if body.titulo is not None:
        row.titulo = body.titulo
    if body.visibilidade is not None:
        row.visibilidade = body.visibilidade
    row.atualizado_em = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(row)

    return materiais_service.resumo_de_material(row)


# ── DELETE /materiais/{material_id} ───────────────────────────────────────────


@router.delete(
    "/{material_id}",
    response_model=RemocaoMaterialResposta,
    response_model_exclude_none=True,
)
def excluir(
    material_id: str, db: Session = Depends(get_db)
) -> RemocaoMaterialResposta:
    """Remove o material (e vínculos em cascata) e tenta apagar o objeto OCI."""
    row = db.get(MaterialDB, material_id)
    if row is None:
        raise _nao_encontrado()

    objeto_id = row.oci_objeto_id
    db.delete(row)
    db.commit()

    oci_removido = remover_objeto(objeto_id)
    return RemocaoMaterialResposta(
        material_id=material_id,
        oci_removido=oci_removido,
        aviso=None
        if oci_removido
        else "Material removido, mas o objeto no OCI não pôde ser excluído.",
    )
