"""Regras de negócio do cadastro de alunos da área da empresa."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from app.models import (
    AlunoAtualizacao,
    AlunoCriacao,
    AlunoResumo,
    PaginaAlunos,
    StatusAluno,
    VinculoMaterial,
    VinculosAluno,
)
from app.models.db import AlunoDB, MaterialDB, VinculoDB

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_ORDENACAO = {
    "nome:asc": AlunoDB.nome.asc(),
    "nome:desc": AlunoDB.nome.desc(),
    "criado_em:desc": AlunoDB.criado_em.desc(),
}


class EmailJaCadastrado(Exception):
    """O e-mail informado já pertence a outro aluno."""


class MateriaisInexistentes(Exception):
    """Um ou mais ``material_id`` informados não existem."""

    def __init__(self, material_ids: list[str]) -> None:
        super().__init__(", ".join(material_ids))
        self.material_ids = material_ids


def normalizar_email(email: str) -> str:
    """Normaliza o e-mail antes de comparar ou gravar."""
    return email.strip().lower()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def email_em_uso(
    session: "Session", email: str, ignorar_aluno_id: str | None = None
) -> bool:
    """Indica se o e-mail já pertence a um aluno, ignorando um id se pedido."""
    stmt = select(AlunoDB.aluno_id).where(
        func.lower(AlunoDB.email) == normalizar_email(email)
    )
    if ignorar_aluno_id is not None:
        stmt = stmt.where(AlunoDB.aluno_id != ignorar_aluno_id)
    return session.scalar(stmt) is not None


def total_materiais(session: "Session", aluno_id: str) -> int:
    """Quantidade de vínculos do aluno com materiais."""
    return (
        session.scalar(
            select(func.count())
            .select_from(VinculoDB)
            .where(VinculoDB.aluno_id == aluno_id)
        )
        or 0
    )


def resumo_de_aluno(
    session: "Session", row: AlunoDB, quantidade_materiais: int | None = None
) -> AlunoResumo:
    """Monta o ``AlunoResumo``; a contagem é consultada se não for informada."""
    if quantidade_materiais is None:
        quantidade_materiais = total_materiais(session, row.aluno_id)
    return AlunoResumo(
        aluno_id=row.aluno_id,
        nome=row.nome,
        email=row.email,
        status=row.status,
        total_materiais=quantidade_materiais,
        criado_em=row.criado_em,
        atualizado_em=row.atualizado_em,
    )


def criar_aluno(session: "Session", dados: AlunoCriacao) -> AlunoDB:
    """Cria o aluno com e-mail normalizado e único (case-insensitive)."""
    if email_em_uso(session, dados.email):
        raise EmailJaCadastrado
    agora = _agora()
    row = AlunoDB(
        aluno_id=str(ULID()),
        nome=dados.nome,
        email=normalizar_email(dados.email),
        status=dados.status,
        owner_id=None,
        criado_em=agora,
        atualizado_em=agora,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:  # corrida entre duas requisições
        session.rollback()
        raise EmailJaCadastrado from exc
    session.refresh(row)
    return row


def listar_alunos(
    session: "Session",
    *,
    pagina: int,
    tamanho_pagina: int,
    q: str | None,
    status: StatusAluno | None,
    ordenar: str,
) -> PaginaAlunos:
    """Lista paginada com filtros e ordenação aplicados em SQL."""
    condicoes = []
    if q:
        termo = f"%{q}%"
        condicoes.append(
            or_(AlunoDB.nome.ilike(termo), AlunoDB.email.ilike(termo))
        )
    if status:
        condicoes.append(AlunoDB.status == status)

    total = (
        session.scalar(select(func.count()).select_from(AlunoDB).where(*condicoes))
        or 0
    )

    contagem = (
        select(VinculoDB.aluno_id, func.count().label("total"))
        .group_by(VinculoDB.aluno_id)
        .subquery()
    )
    linhas = session.execute(
        select(AlunoDB, func.coalesce(contagem.c.total, 0))
        .outerjoin(contagem, contagem.c.aluno_id == AlunoDB.aluno_id)
        .where(*condicoes)
        .order_by(_ORDENACAO[ordenar], AlunoDB.aluno_id)
        .offset((pagina - 1) * tamanho_pagina)
        .limit(tamanho_pagina)
    ).all()

    total_paginas = (total + tamanho_pagina - 1) // tamanho_pagina if total else 0
    itens = [
        resumo_de_aluno(session, row, quantidade) for row, quantidade in linhas
    ]
    return PaginaAlunos(
        itens=itens,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=total_paginas,
    )


def obter_aluno(session: "Session", aluno_id: str) -> AlunoDB | None:
    """Busca a linha do aluno pelo id."""
    return session.get(AlunoDB, aluno_id)


def atualizar_aluno(
    session: "Session", row: AlunoDB, dados: AlunoAtualizacao
) -> AlunoDB:
    """Aplica um PATCH parcial, renovando ``atualizado_em``."""
    if dados.email is not None:
        email = normalizar_email(dados.email)
        if email_em_uso(session, email, ignorar_aluno_id=row.aluno_id):
            raise EmailJaCadastrado
        row.email = email
    if dados.nome is not None:
        row.nome = dados.nome
    if dados.status is not None:
        row.status = dados.status
    row.atualizado_em = _agora()
    try:
        session.commit()
    except IntegrityError as exc:  # corrida entre duas requisições
        session.rollback()
        raise EmailJaCadastrado from exc
    session.refresh(row)
    return row


def excluir_aluno(session: "Session", row: AlunoDB) -> None:
    """Remove o aluno; o banco aplica a cascata dos vínculos."""
    session.delete(row)
    session.commit()


# ── Vínculos aluno ↔ material ─────────────────────────────────────────────────


def vinculo_de_material(
    row: MaterialDB, vinculado_em: str
) -> VinculoMaterial:
    """Serializa um vínculo a partir das colunas do material.

    Usa apenas as colunas desnormalizadas de ``MaterialDB``, sem abrir
    ``pacote_json``.
    """
    return VinculoMaterial(
        material_id=row.material_id,
        titulo=row.titulo,
        formato=row.formato,
        perfil=row.perfil,
        visibilidade=row.visibilidade,
        vinculado_em=vinculado_em,
    )


def vinculos_do_aluno(session: "Session", aluno_id: str) -> VinculosAluno:
    """Devolve todos os vínculos do aluno, mais recentes primeiro."""
    linhas = session.execute(
        select(MaterialDB, VinculoDB.criado_em)
        .join(VinculoDB, VinculoDB.material_id == MaterialDB.material_id)
        .where(VinculoDB.aluno_id == aluno_id)
        .order_by(VinculoDB.criado_em.desc(), MaterialDB.material_id)
    ).all()
    return VinculosAluno(
        aluno_id=aluno_id,
        itens=[
            vinculo_de_material(material, vinculado_em)
            for material, vinculado_em in linhas
        ],
    )


def _materiais_inexistentes(
    session: "Session", material_ids: list[str]
) -> list[str]:
    """Ids informados que não existem no catálogo, em ordem estável."""
    if not material_ids:
        return []
    existentes = set(
        session.scalars(
            select(MaterialDB.material_id).where(
                MaterialDB.material_id.in_(material_ids)
            )
        ).all()
    )
    return sorted({mid for mid in material_ids if mid not in existentes})


def substituir_vinculos(
    session: "Session", aluno_id: str, material_ids: list[str]
) -> None:
    """Substitui o conjunto inteiro de vínculos de forma atômica.

    Valida todos os ids antes de apagar/inserir; se algum não existir, nada é
    alterado. Duplicatas são deduplicadas preservando a primeira ocorrência.
    """
    unicos = list(dict.fromkeys(material_ids))
    faltando = _materiais_inexistentes(session, unicos)
    if faltando:
        raise MateriaisInexistentes(faltando)

    agora = _agora()
    session.execute(delete(VinculoDB).where(VinculoDB.aluno_id == aluno_id))
    session.add_all(
        VinculoDB(aluno_id=aluno_id, material_id=material_id, criado_em=agora)
        for material_id in unicos
    )
    try:
        session.commit()
    except IntegrityError as exc:  # material removido entre a validação e o insert
        session.rollback()
        faltando = _materiais_inexistentes(session, unicos)
        if faltando:
            raise MateriaisInexistentes(faltando) from exc
        raise


def adicionar_vinculo(
    session: "Session", aluno_id: str, material_id: str
) -> tuple[VinculoDB, bool]:
    """Cria o vínculo se necessário; devolve ``(linha, criado)``."""
    row = session.get(VinculoDB, (aluno_id, material_id))
    if row is not None:
        return row, False

    row = VinculoDB(
        aluno_id=aluno_id, material_id=material_id, criado_em=_agora()
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:  # corrida entre duas requisições
        session.rollback()
        existente = session.get(VinculoDB, (aluno_id, material_id))
        if existente is None:
            raise
        return existente, False
    return row, True


def remover_vinculo(
    session: "Session", aluno_id: str, material_id: str
) -> None:
    """Remove o vínculo, se existir; idempotente."""
    session.execute(
        delete(VinculoDB).where(
            VinculoDB.aluno_id == aluno_id,
            VinculoDB.material_id == material_id,
        )
    )
    session.commit()
