"""Regras de negócio do cadastro de alunos da área da empresa."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from ulid import ULID

from app.models import (
    AlunoAtualizacao,
    AlunoCriacao,
    AlunoResumo,
    PaginaAlunos,
    StatusAluno,
)
from app.models.db import AlunoDB, VinculoDB

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_ORDENACAO = {
    "nome:asc": AlunoDB.nome.asc(),
    "nome:desc": AlunoDB.nome.desc(),
    "criado_em:desc": AlunoDB.criado_em.desc(),
}


class EmailJaCadastrado(Exception):
    """O e-mail informado já pertence a outro aluno."""


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
