"""Dependências que protegem as rotas quando ``AUTH_HABILITADA=true``.

Com o login desligado nenhuma delas bloqueia nada, exceto a chave de API em
``exigir_empresa_com_chave``: as rotas se comportam como antes (e
``aluno_da_requisicao`` volta a exigir o ``aluno_id`` da query).

- ``exigir_empresa``: único ponto de entrada das rotas da empresa. Com o login
  ligado, sessão de empresa (demo inclusa) ou o X-API-Key de API_KEY_EMPRESA.
- ``exigir_empresa_com_chave``: o mesmo, mais a chave exigida com o login
  desligado (o comportamento de antes do login nas rotas que ela protege).
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
from app.core.seguranca import (
    cabecalho_chave_empresa,
    chave_empresa_confere,
    exigir_chave_empresa,
)
from app.models.db import AlunoDB


def aluno_ativo_da_sessao(db: Session, sessao: Sessao) -> AlunoDB:
    """Aluno da sessão, ainda existente e ativo; senão 401."""
    aluno = db.get(AlunoDB, sessao.sub)
    if aluno is None or aluno.status != "ativo":
        raise nao_autenticado()
    return aluno


def exigir_empresa(
    request: Request,
    chave_enviada: Annotated[str | None, Depends(cabecalho_chave_empresa)] = None,
) -> Sessao | None:
    """Ponto de entrada das rotas da empresa.

    Com o login ligado, aceita a sessão de empresa (demo inclusa) ou o
    ``X-API-Key`` igual a ``API_KEY_EMPRESA``, para scripts. Sem nenhum dos
    dois, 401; sessão de aluno sem a chave, 403. Com o login desligado não
    bloqueia: nas rotas que a chave protege, a regra fica com
    ``exigir_empresa_com_chave``.
    """
    if not settings.auth_habilitada:
        return None
    sessao = sessao_da_requisicao(request)
    if sessao is not None and sessao.tipo == "empresa":
        return sessao
    if chave_empresa_confere(chave_enviada):
        return None
    if sessao is not None:
        raise acesso_negado()
    raise nao_autenticado()


def exigir_empresa_com_chave(
    sessao: Annotated[Sessao | None, Depends(exigir_empresa)],
    _chave: Annotated[None, Depends(exigir_chave_empresa)],
) -> Sessao | None:
    """``exigir_empresa`` mais a regra da chave com o login desligado (como era
    antes do login): com API_KEY_EMPRESA definida, exige o X-API-Key; vazia, não
    bloqueia. Vai no APIRouter de /alunos e /materiais e nas escritas de
    /adaptacoes e /jobs. Com o login ligado, só ``exigir_empresa`` decide.
    """
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
