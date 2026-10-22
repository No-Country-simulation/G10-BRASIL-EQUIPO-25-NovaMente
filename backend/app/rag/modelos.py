"""Modelos de dados devolvidos pelo módulo RAG."""

from pydantic import BaseModel, Field


class Trecho(BaseModel):
    """Trecho recuperado do documento.

    `relevancia` é 1 - distância cosseno, limitada a [0, 1]. Quem integra
    combina esse valor com o LLM-as-a-judge para calcular o
    `ancoragem_fonte_score` final (fora deste módulo).
    """

    texto: str
    indice: int = Field(ge=0, description="Posição do chunk no documento")
    relevancia: float = Field(ge=0.0, le=1.0)
    documento_id: str


class ResultadoIndexacao(BaseModel):
    """Resumo da indexação de um documento."""

    documento_id: str
    total_trechos: int = Field(ge=0)
    caracteres: int = Field(ge=0)
