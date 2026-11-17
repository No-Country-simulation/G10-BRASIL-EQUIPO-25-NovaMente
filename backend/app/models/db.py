"""Modelos ORM das tabelas SQLite de alunos, materiais e vínculos."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AlunoDB(Base):
    __tablename__ = "alunos"
    __table_args__ = (
        CheckConstraint("status IN ('ativo','inativo')", name="ck_alunos_status"),
        Index("ix_alunos_status", "status"),
    )

    aluno_id: Mapped[str] = mapped_column(Text, primary_key=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(
        Text(collation="NOCASE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="ativo", server_default="ativo"
    )
    owner_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[str] = mapped_column(Text, nullable=False)
    atualizado_em: Mapped[str] = mapped_column(Text, nullable=False)


class MaterialDB(Base):
    __tablename__ = "materiais"
    __table_args__ = (
        CheckConstraint(
            "status_upload IN ('concluido','falha')",
            name="ck_materiais_status_upload",
        ),
        CheckConstraint(
            "visibilidade IN ('rascunho','publicado')",
            name="ck_materiais_visibilidade",
        ),
        Index("ix_materiais_visibilidade", "visibilidade"),
        Index("ix_materiais_formato", "formato"),
        Index("ix_materiais_ancoragem", "ancoragem_score"),
    )

    material_id: Mapped[str] = mapped_column(Text, primary_key=True)
    adaptacao_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    documento_titulo: Mapped[str] = mapped_column(Text, nullable=False)
    documento_origem: Mapped[str] = mapped_column(Text, nullable=False)
    documento_nome_arquivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    documento_tamanho_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    perfil: Mapped[str] = mapped_column(Text, nullable=False)
    formato: Mapped[str] = mapped_column(Text, nullable=False)
    nivel: Mapped[str] = mapped_column(Text, nullable=False)
    nicho: Mapped[str] = mapped_column(Text, nullable=False)
    tempo_estimado_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    ancoragem_score: Mapped[float] = mapped_column(Float, nullable=False)
    status_upload: Mapped[str] = mapped_column(Text, nullable=False)
    conceitos_chave_json: Mapped[str] = mapped_column(Text, nullable=False)
    oci_objeto_id: Mapped[str] = mapped_column(Text, nullable=False)
    visibilidade: Mapped[str] = mapped_column(
        Text, nullable=False, default="rascunho", server_default="rascunho"
    )
    pacote_json: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[str] = mapped_column(Text, nullable=False)
    atualizado_em: Mapped[str] = mapped_column(Text, nullable=False)


class VinculoDB(Base):
    __tablename__ = "vinculos"
    __table_args__ = (
        Index("ix_vinculos_material", "material_id"),
    )

    aluno_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("alunos.aluno_id", ondelete="CASCADE"),
        primary_key=True,
    )
    material_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("materiais.material_id", ondelete="CASCADE"),
        primary_key=True,
    )
    criado_em: Mapped[str] = mapped_column(Text, nullable=False)
