"""Códigos de 6 dígitos enviados por e-mail (tabela ``codigos_login``).

- Gerar um código apaga os pendentes do mesmo (e-mail, perfil, propósito) e
  os registros expirados há mais de um dia (a limpeza não tem job próprio).
- Só o HMAC-SHA256 do código é gravado, com ``SESSAO_SEGREDO`` sobre
  ``email|perfil|proposito|codigo``.
- A validação usa o pendente mais recente ainda no prazo, compara em tempo
  constante e marca ``usado_em`` (uso único). Cada erro soma uma tentativa;
  com 5, o código deixa de valer. Errado, expirado ou já usado: sempre ``False``.

As datas são texto ISO 8601 em UTC com microssegundos, então a comparação
como texto no SQL segue a ordem do tempo.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db import CodigoLoginDB

PerfilCodigo = Literal["empresa", "aluno"]
PropositoCodigo = Literal["login", "senha"]

VALIDADE_SEGUNDOS = 600
MAX_TENTATIVAS = 5
GUARDA_EXPIRADOS = timedelta(days=1)

_agora: Callable[[], datetime] = lambda: datetime.now(timezone.utc)  # noqa: E731


def _iso(instante: datetime) -> str:
    return instante.astimezone(timezone.utc).isoformat(timespec="microseconds")


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def hash_do_codigo(email: str, perfil: str, proposito: str, codigo: str) -> str:
    chave = settings.sessao_segredo.get_secret_value().encode("utf-8")
    mensagem = f"{email}|{perfil}|{proposito}|{codigo}".encode("utf-8")
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def novo_codigo() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def emitir(db: Session, perfil: PerfilCodigo, proposito: PropositoCodigo, email: str) -> str:
    """Grava um código novo e devolve o texto dele (só para enviar por e-mail)."""
    email = normalizar_email(email)
    agora = _agora()
    db.execute(delete(CodigoLoginDB).where(CodigoLoginDB.expira_em < _iso(agora - GUARDA_EXPIRADOS)))
    db.execute(
        delete(CodigoLoginDB).where(
            CodigoLoginDB.email == email,
            CodigoLoginDB.perfil == perfil,
            CodigoLoginDB.proposito == proposito,
            CodigoLoginDB.usado_em.is_(None),
        )
    )
    codigo = novo_codigo()
    db.add(
        CodigoLoginDB(
            perfil=perfil,
            proposito=proposito,
            email=email,
            codigo_hash=hash_do_codigo(email, perfil, proposito, codigo),
            criado_em=_iso(agora),
            expira_em=_iso(agora + timedelta(seconds=VALIDADE_SEGUNDOS)),
            tentativas=0,
        )
    )
    db.commit()
    return codigo


def validar(
    db: Session, perfil: PerfilCodigo, proposito: PropositoCodigo, email: str, codigo: str
) -> bool:
    """Consome o código se ele confere; senão soma uma tentativa ao pendente."""
    email = normalizar_email(email)
    agora = _iso(_agora())
    pendente = db.scalars(
        select(CodigoLoginDB)
        .where(
            CodigoLoginDB.email == email,
            CodigoLoginDB.perfil == perfil,
            CodigoLoginDB.proposito == proposito,
            CodigoLoginDB.usado_em.is_(None),
            CodigoLoginDB.expira_em > agora,
            CodigoLoginDB.tentativas < MAX_TENTATIVAS,
        )
        .order_by(CodigoLoginDB.id.desc())
        .limit(1)
    ).first()
    if pendente is None:
        # Mesmo sem código, calcula um HMAC para não responder mais rápido.
        hmac.compare_digest(hash_do_codigo(email, perfil, proposito, codigo), "0" * 64)
        return False
    calculado = hash_do_codigo(email, perfil, proposito, codigo)
    if not hmac.compare_digest(calculado, pendente.codigo_hash):
        db.execute(
            update(CodigoLoginDB)
            .where(CodigoLoginDB.id == pendente.id)
            .values(tentativas=CodigoLoginDB.tentativas + 1)
        )
        db.commit()
        return False
    # Condicional: duas verificações simultâneas não consomem o mesmo código.
    consumido = db.execute(
        update(CodigoLoginDB)
        .where(CodigoLoginDB.id == pendente.id, CodigoLoginDB.usado_em.is_(None))
        .values(usado_em=agora)
    )
    db.commit()
    return consumido.rowcount == 1


def invalidar_pendentes(db: Session, perfil: PerfilCodigo, email: str) -> None:
    """Apaga os códigos ainda não usados do e-mail no perfil (todos os propósitos)."""
    db.execute(
        delete(CodigoLoginDB).where(
            CodigoLoginDB.email == normalizar_email(email),
            CodigoLoginDB.perfil == perfil,
            CodigoLoginDB.usado_em.is_(None),
        )
    )
    db.commit()
