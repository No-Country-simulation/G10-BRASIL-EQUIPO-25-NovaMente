"""Texto-fonte do material, guardado para consultas depois do job.

O texto é o mesmo que o pipeline usou (já extraído do PDF, quando for o caso)
e nunca vai para o log nem para as respostas das rotas. A linha some junto com
o material (``ON DELETE CASCADE``, com ``PRAGMA foreign_keys=ON`` no engine).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.db import MaterialFonteDB


def salvar_fonte(session: Session, material_id: str, texto: str | None) -> bool:
    """Grava ou substitui o texto-fonte do material; não faz commit.

    Texto ausente ou só com espaços não cria linha (e não mexe numa que já
    exista). Devolve ``True`` quando gravou.
    """
    if not texto or not texto.strip():
        return False
    agora = datetime.now(timezone.utc).isoformat()
    row = session.get(MaterialFonteDB, material_id)
    if row is None:
        session.add(
            MaterialFonteDB(
                material_id=material_id, texto=texto, caracteres=len(texto), criado_em=agora
            )
        )
    else:
        row.texto = texto
        row.caracteres = len(texto)
        row.criado_em = agora
    return True


def obter_fonte(material_id: str) -> str | None:
    """Texto-fonte do material, ou ``None`` se ele não tiver fonte guardada."""
    with SessionLocal() as session:
        row = session.get(MaterialFonteDB, material_id)
        return row.texto if row is not None else None
