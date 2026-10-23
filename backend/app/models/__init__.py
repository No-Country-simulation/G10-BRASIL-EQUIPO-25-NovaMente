"""Modelos Pydantic que espelham o contrato de dados da spec do frontend.

Cada schema aqui corresponde 1-para-1 com os tipos TypeScript de
``docs/2026-10-21-novamente-frontend-design.md`` (seção 5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

PerfilDestinatario = Literal["Iniciante", "Desenvolvedor", "LiderTecnico", "Gestor"]
FormatoSaida = Literal["Flashcards", "Quiz", "Tutorial", "ResumoExecutivo"]
NichoSetor = Literal["Fintech", "Saude", "Ecommerce", "Geral"]
NivelDetalhe = Literal["Didatico", "Tecnico", "Executivo"]
OrigemDocumento = Literal["upload", "texto"]
FormatoExportacao = Literal["md", "pdf", "csv"]


# ── Entrada ───────────────────────────────────────────────────────────────────


class AdaptacaoInput(BaseModel):
    """Payload JSON para ``POST /api/v1/adaptacoes``."""

    documento_titulo: str = Field(min_length=3, max_length=150)
    documento_conteudo: str = Field(min_length=200, max_length=50_000)
    perfil_destinatario: PerfilDestinatario
    formato_saida: FormatoSaida
    nicho_setor: NichoSetor
    nivel_detalhe: NivelDetalhe


# ── Pacote gerado ─────────────────────────────────────────────────────────────


class DocumentoRef(BaseModel):
    titulo: str
    origem: OrigemDocumento
    nome_arquivo: str | None = None
    tamanho_bytes: int | None = None


class MetadadosAdaptacao(BaseModel):
    perfil_aplicado: PerfilDestinatario
    formato_gerado: FormatoSaida
    nivel_detalhe_aplicado: NivelDetalhe
    tempo_estimado_estudo_minutos: int = Field(ge=1)
    conceitos_chave: list[str] = Field(min_length=1, max_length=12)


class FlashcardItem(BaseModel):
    frente: str
    verso: str
    dica_didatica: str | None = None


class QuizItem(BaseModel):
    pergunta: str
    opcoes: list[str] = Field(min_length=2, max_length=6)
    resposta_correta: int = Field(ge=0)
    explicacao: str


class ConteudoFlashcards(BaseModel):
    tipo: Literal["flashcards"] = "flashcards"
    titulo: str
    introducao_contextualizada: str
    itens: list[FlashcardItem] = Field(min_length=3, max_length=30)


class ConteudoQuiz(BaseModel):
    tipo: Literal["quiz"] = "quiz"
    titulo: str
    introducao_contextualizada: str
    itens: list[QuizItem]


class ConteudoMarkdown(BaseModel):
    """Usado para Tutorial e Resumo Executivo."""

    tipo: Literal["markdown"] = "markdown"
    titulo: str
    introducao_contextualizada: str
    itens: str = Field(min_length=40)


# União discriminada idêntica à do TypeScript
ConteudoAdaptado = ConteudoFlashcards | ConteudoQuiz | ConteudoMarkdown


class AvaliacaoQualidade(BaseModel):
    ancoragem_fonte_score: float = Field(ge=0.0, le=1.0)
    clareza_pedagogica: Literal["Alta", "Media", "Baixa"]
    observacoes: str | None = None


class ArmazenamentoOci(BaseModel):
    bucket: str
    objeto_id: str
    status_upload: Literal["concluido", "falha"]


class AdaptacaoPacote(BaseModel):
    """Pacote completo devolvido em ``GET /api/v1/adaptacoes/{id}``."""

    adaptacao_id: str  # ULID
    status: Literal["sucesso"] = "sucesso"
    criado_em: str  # ISO 8601 UTC
    documento: DocumentoRef
    metadados: MetadadosAdaptacao
    conteudo_adaptado: ConteudoAdaptado
    avaliacao_qualidade: AvaliacaoQualidade
    armazenamento_oci: ArmazenamentoOci


# ── Job ───────────────────────────────────────────────────────────────────────

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
EtapaJob = Literal[
    "extraindo", "chunking", "embeddings", "gerando", "revisando", "armazenando"
]


class ErroJob(BaseModel):
    """Formato de ``erro`` embutido no JobResposta quando ``failed``."""

    codigo: str
    mensagem: str
    request_id: str | None = None


class JobResposta(BaseModel):
    """Estado de um job assíncrono — polling em ``GET /api/v1/jobs/{id}``."""

    job_id: str
    status: JobStatus
    etapa_atual: EtapaJob | None = None
    etapas_concluidas: list[EtapaJob] = Field(default_factory=list)
    progresso_percentual: int = Field(ge=0, le=100, default=0)
    mensagem: str | None = None
    iniciado_em: str  # ISO 8601
    atualizado_em: str  # ISO 8601
    adaptacao_id: str | None = None          # presente em succeeded
    resultado: AdaptacaoPacote | None = None  # presente em succeeded
    erro: ErroJob | None = None               # presente em failed


# ── Envelopes ─────────────────────────────────────────────────────────────────


class ErroDetalhe(BaseModel):
    codigo: str
    mensagem: str
    campos: dict[str, str] | None = None
    request_id: str | None = None


class ApiProblema(BaseModel):
    """Envelope padrão de erro — corresponde a ``ApiProblema`` no TS."""

    erro: ErroDetalhe


class AdaptacaoResumo(BaseModel):
    """Item da lista de histórico — ``GET /api/v1/adaptacoes``."""

    adaptacao_id: str
    criado_em: str
    documento: DocumentoRef
    perfil_aplicado: PerfilDestinatario
    formato_gerado: FormatoSaida
    nivel_detalhe_aplicado: NivelDetalhe
    tempo_estimado_estudo_minutos: int
    ancoragem_fonte_score: float
    status_upload: Literal["concluido", "falha"]
    conceitos_chave: list[str]


class PaginaAdaptacoes(BaseModel):
    """Resposta paginada de ``GET /api/v1/adaptacoes``."""

    itens: list[AdaptacaoResumo]
    pagina: int
    tamanho_pagina: int
    total: int
    total_paginas: int


class OciStatus(BaseModel):
    """Resposta de ``GET /api/v1/oci/status``."""

    configurado: bool
    bucket: str | None = None
    regiao: str | None = None
    total_objetos: int | None = None
    bytes_armazenados: int | None = None
    ultimo_upload_em: str | None = None
    mensagem: str | None = None
    verificado_em: str


class HealthResposta(BaseModel):
    """Resposta de ``GET /api/v1/health``."""

    status: Literal["ok", "degraded"]
    versao: str
    oci: Literal["ok", "indisponivel"]
    llm: Literal["ok", "indisponivel"]
    verificado_em: str
