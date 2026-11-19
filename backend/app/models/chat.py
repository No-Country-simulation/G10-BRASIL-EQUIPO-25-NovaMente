"""Schemas das rotas de chat sobre o material."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Limites só para proteger o corpo da requisição; os de verdade são do serviço
# (CHAT_MAX_PERGUNTA_CARACTERES, CHAT_MAX_MENSAGENS_HISTORICO).
MAX_CARACTERES_CORPO = 10_000
MAX_ITENS_HISTORICO_CORPO = 50
MAX_CARACTERES_MODELO = 200


class MensagemHistorico(BaseModel):
    papel: Literal["user", "assistant"] = Field(
        description="Quem escreveu: `user` (pergunta) ou `assistant` (resposta anterior)."
    )
    conteudo: str = Field(max_length=MAX_CARACTERES_CORPO, description="Texto da mensagem.")


class PerguntaChat(BaseModel):
    """Pergunta sobre o material, com o histórico da conversa (não é guardado no servidor)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "pergunta": "O que é uma subnet?",
                    "historico": [
                        {"papel": "user", "conteudo": "O que é uma VCN?"},
                        {"papel": "assistant", "conteudo": "É a rede virtual privada da nuvem [F1]."},
                    ],
                    "modelo": None,
                }
            ]
        }
    )

    pergunta: str = Field(
        max_length=MAX_CARACTERES_CORPO,
        description="Pergunta do usuário. O limite efetivo é CHAT_MAX_PERGUNTA_CARACTERES.",
    )
    historico: list[MensagemHistorico] = Field(
        default_factory=list,
        max_length=MAX_ITENS_HISTORICO_CORPO,
        description="Mensagens anteriores, da mais antiga para a mais recente. "
        "O servidor usa só as últimas CHAT_MAX_MENSAGENS_HISTORICO.",
    )
    modelo: str | None = Field(
        default=None,
        max_length=MAX_CARACTERES_MODELO,
        description="Id do modelo, um dos de `GET /chat/modelos`. Vazio usa o padrão.",
    )


class CitacaoChat(BaseModel):
    id: str = Field(description="Marcador citado na resposta, por exemplo `F1` ou `P2`.")
    origem: Literal["documento", "pacote"] = Field(
        description="`documento` (texto original) ou `pacote` (material gerado)."
    )
    excerto: str = Field(description="Começo do trecho citado (até 240 caracteres).")


class RespostaChatSaida(BaseModel):
    resposta: str = Field(description="Resposta, com os marcadores das citações no texto.")
    citacoes: list[CitacaoChat] = Field(description="Trechos citados que existem no material.")
    base: Literal["documento_e_pacote", "pacote"] = Field(
        description="`pacote` quando o material não tem o texto original guardado."
    )
    recusou: bool = Field(description="A resposta não estava no material.")
    fundamentada: bool = Field(description="A resposta citou pelo menos um trecho.")
    ancoragem: float | None = Field(
        description="Quanto da resposta aparece nos trechos enviados (0 a 1, informativo); "
        "nulo na recusa."
    )
    modelo: str = Field(description="Id do modelo usado.")
    trechos_usados: int = Field(description="Quantos trechos do material foram enviados ao modelo.")


class ModelosChat(BaseModel):
    padrao: str = Field(description="Modelo usado quando a pergunta não escolhe um.")
    modelos: list[str] = Field(description="Modelos aceitos, com o padrão primeiro.")
