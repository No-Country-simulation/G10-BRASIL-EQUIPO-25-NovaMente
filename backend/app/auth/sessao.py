"""Sessão em cookie assinado (``nm_sessao``).

O valor é ``<payload>.<assinatura>``: o payload é o JSON
``{t, sub, nome?, demo?, exp}`` em base64url (sem ``=``) e a assinatura é o
HMAC-SHA256 desse texto com ``SESSAO_SEGREDO``, também em base64url. Não há
estado no servidor: assinatura inválida, payload malformado ou ``exp`` no
passado valem como "sem sessão".

O cookie é httpOnly, SameSite=Lax, Path=/ e sem ``Domain`` (fica preso ao
host que o definiu); ``Secure`` segue ``SESSAO_COOKIE_SEGURO``.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import Request, Response

from app.core.config import settings

NOME_COOKIE = "nm_sessao"
DURACAO_EMPRESA_SEGUNDOS = 8 * 3600
DURACAO_ALUNO_SEGUNDOS = 12 * 3600
DURACAO_DEMO_SEGUNDOS = 2 * 3600

TipoSessao = Literal["empresa", "aluno"]

# Relógio em segundos de época; os testes trocam por um falso.
_relogio: Callable[[], float] = time.time


@dataclass(frozen=True)
class Sessao:
    tipo: TipoSessao
    sub: str  # e-mail da empresa ou aluno_id
    nome: str | None = None
    demo: bool = False
    exp: int = 0


def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _de_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(conteudo: str, segredo: str) -> str:
    return _b64url(hmac.new(segredo.encode("utf-8"), conteudo.encode("ascii"), hashlib.sha256).digest())


def _segredo() -> str:
    return settings.sessao_segredo.get_secret_value()


def duracao(tipo: TipoSessao, demo: bool) -> int:
    if demo:
        return DURACAO_DEMO_SEGUNDOS
    return DURACAO_EMPRESA_SEGUNDOS if tipo == "empresa" else DURACAO_ALUNO_SEGUNDOS


def criar_token(
    tipo: TipoSessao, sub: str, *, nome: str | None = None, demo: bool = False,
    segredo: str | None = None,
) -> tuple[str, int]:
    """Devolve o valor do cookie e a duração em segundos."""
    segundos = duracao(tipo, demo)
    payload: dict = {"t": tipo, "sub": sub, "exp": int(_relogio()) + segundos}
    if nome is not None:
        payload["nome"] = nome
    if demo:
        payload["demo"] = True
    conteudo = _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return f"{conteudo}.{_assinar(conteudo, segredo or _segredo())}", segundos


def ler_token(token: str | None, *, segredo: str | None = None) -> Sessao | None:
    """Sessão do token, ou ``None`` se ausente, adulterado, malformado ou expirado."""
    segredo = segredo or _segredo()
    if not token or not segredo or token.count(".") != 1:
        return None
    conteudo, assinatura = token.split(".")
    try:
        esperado = _assinar(conteudo, segredo)
    except UnicodeEncodeError:
        return None
    if not hmac.compare_digest(assinatura.encode("ascii", "replace"), esperado.encode("ascii")):
        return None
    try:
        payload = json.loads(_de_b64url(conteudo))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict):
        return None
    tipo, sub, exp = payload.get("t"), payload.get("sub"), payload.get("exp")
    nome, demo = payload.get("nome"), payload.get("demo", False)
    if tipo not in ("empresa", "aluno") or not isinstance(sub, str) or not sub:
        return None
    if not isinstance(exp, int) or isinstance(exp, bool) or exp <= _relogio():
        return None
    if nome is not None and not isinstance(nome, str):
        return None
    return Sessao(tipo=tipo, sub=sub, nome=nome, demo=demo is True, exp=exp)


def sessao_da_requisicao(request: Request) -> Sessao | None:
    return ler_token(request.cookies.get(NOME_COOKIE))


def abrir_sessao(
    response: Response, tipo: TipoSessao, sub: str, *, nome: str | None = None, demo: bool = False
) -> None:
    token, segundos = criar_token(tipo, sub, nome=nome, demo=demo)
    response.set_cookie(
        NOME_COOKIE, token, max_age=segundos, path="/", httponly=True,
        samesite="lax", secure=settings.sessao_cookie_seguro,
    )


def encerrar_sessao(response: Response) -> None:
    response.delete_cookie(
        NOME_COOKIE, path="/", httponly=True, samesite="lax", secure=settings.sessao_cookie_seguro,
    )
