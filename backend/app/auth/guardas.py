"""Dependências que protegem as rotas quando ``AUTH_HABILITADA=true``.

Com o login desligado nenhuma delas bloqueia nada: as rotas se comportam
como antes (e ``aluno_da_requisicao`` volta a exigir o ``aluno_id`` da query).

- ``exigir_empresa``: sessão de empresa (demo inclusa). É o único ponto de
  entrada das rotas da empresa: quando a chave de API para scripts entrar,
  ela deve ser aceita aqui.
- ``exigir_aluno``: sessão de aluno, revalidada no banco a cada requisição
  (aluno apagado ou inativo vira 401). Devolve o ``aluno_id`` da sessão.
- ``exigir_sessao``: qualquer um dos dois perfis.
- ``aluno_da_requisicao``: o ``aluno_id`` que as rotas do aluno devem usar.
- ``so_sem_login``: a rota existe só com o login desligado (404 com ele ligado).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session

from app.auth.erros import acesso_negado, nao_autenticado, nao_encontrado
from app.auth.sessao import Sessao, sessao_da_requisicao
from app.core.config import settings
from app.core.db import get_db
from app.models.db import AlunoDB


def aluno_ativo_da_sessao(db: Session, sessao: Sessao) -> AlunoDB:
    """Aluno da sessão, ainda existente e ativo; senão 401."""
    aluno = db.get(AlunoDB, sessao.sub)
    if aluno is None or aluno.status != "ativo":
        raise nao_autenticado()
    return aluno


def exigir_empresa(request: Request) -> Sessao | None:
    if not settings.auth_habilitada:
        return None
    sessao = sessao_da_requisicao(request)
    if sessao is None:
        raise nao_autenticado()
    if sessao.tipo != "empresa":
        raise acesso_negado()
    return sessao


def exigir_aluno(request: Request, db: Session = Depends(get_db)) -> str | None:
    if not settings.auth_habilitada:
        return None
    sessao = sessao_da_requisicao(request)
    if sessao is None:
        raise nao_autenticado()
    if sessao.tipo != "aluno":
        raise acesso_negado()
    return aluno_ativo_da_sessao(db, sessao).aluno_id


def exigir_sessao(request: Request, db: Session = Depends(get_db)) -> Sessao | None:
    if not settings.auth_habilitada:
        return None
    sessao = sessao_da_requisicao(request)
    if sessao is None:
        raise nao_autenticado()
    if sessao.tipo == "aluno":
        aluno_ativo_da_sessao(db, sessao)
    return sessao


def aluno_da_requisicao(
    aluno_id: Annotated[str | None, Query(min_length=1)] = None,
    da_sessao: str | None = Depends(exigir_aluno),
) -> str:
    """Com login, o aluno da sessão (o ``aluno_id`` da query é ignorado).
    Sem login, o ``aluno_id`` da query, obrigatório como antes."""
    if settings.auth_habilitada:
        assert da_sessao is not None
        return da_sessao
    if aluno_id is None:
        raise RequestValidationError(
            [{"type": "missing", "loc": ("query", "aluno_id"), "msg": "Field required", "input": None}]
        )
    return aluno_id


def so_sem_login() -> None:
    if settings.auth_habilitada:
        raise nao_encontrado()


def auth_ligada() -> None:
    """Rotas de /auth/* (exceto /config): 404 com o login desligado."""
    if not settings.auth_habilitada:
        raise nao_encontrado()
