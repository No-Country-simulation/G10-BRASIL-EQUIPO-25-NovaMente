"""Router do chat sobre o material: aluno, empresa e lista de modelos.

- ``POST /aluno/materiais/{material_id}/chat?aluno_id=``: o aluno é
  identificado como nas outras rotas ``/aluno/*`` (``aluno_id`` na query,
  aluno ativo); só material publicado e vinculado a ele, senão o mesmo 404.
- ``POST /materiais/{material_id}/chat``: a empresa testa o chat em qualquer
  visibilidade, sem credencial, como as outras rotas de materiais.
- ``GET /chat/modelos``: modelos aceitos pelo chat (sem rede).

As rotas são ``def``: o serviço bloqueia (rede e CPU) e roda no pool de
threads. Pergunta, histórico, resposta e texto do material não vão para o log
nem para as mensagens de erro; os erros do provedor viram mensagens fixas.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.routers.aluno import _obter_aluno_ativo
from app.core.config import settings
from app.core.db import get_db
from app.core.limite_taxa import LimiteDeTaxa, segundos_para_cabecalho
from app.llm import (
    ErroConfiguracao,
    ErroLimiteTaxa,
    ErroRespostaInvalida,
    ErroTimeout,
    ErroTransitorio,
    ModeloNaoPermitido,
    modelo_padrao_do_chat,
    modelos_do_chat,
)
from app.models.chat import ModelosChat, PerguntaChat, RespostaChatSaida
from app.models.db import MaterialDB
from app.services import alunos as alunos_service
from app.services import servico_chat
from app.services.constantes_chat import MaterialNaoEncontrado, PerguntaInvalida, RespostaVazia
from app.services.repositorio import PacoteCorrompido

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Perguntas por minuto: uma chave por aluno e um balde só para a empresa.
limite_chat = LimiteDeTaxa(lambda: settings.chat_limite_por_minuto)
CHAVE_EMPRESA = "empresa"
RETRY_AFTER_PROVEDOR_SEGUNDOS = 10

_MSG_INDISPONIVEL = "O chat está indisponível no momento. Tente novamente em instantes."


def _erro(status: int, codigo: str, mensagem: str, *, headers: dict | None = None, **extra) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"erro": {"codigo": codigo, "mensagem": mensagem, **extra}},
        headers=headers,
    )


def _material_nao_encontrado() -> HTTPException:
    return _erro(404, "MATERIAL_NAO_ENCONTRADO", "Material não encontrado.")


def traduzir_erro(exc: Exception, material_id: str) -> HTTPException | None:
    """Erro do serviço ou do provedor -> resposta HTTP; ``None`` deixa o handler genérico agir."""
    if isinstance(exc, PerguntaInvalida):
        return _erro(422, exc.codigo, exc.mensagem, campos={"pergunta": exc.mensagem})
    if isinstance(exc, MaterialNaoEncontrado):
        return _material_nao_encontrado()
    if isinstance(exc, ModeloNaoPermitido):
        mensagem = "Modelo não permitido no chat."
        return _erro(
            422, "CHAT_MODELO_NAO_PERMITIDO", mensagem,
            campos={"modelo": mensagem}, detalhes={"modelos_permitidos": exc.permitidos},
        )
    if isinstance(exc, PacoteCorrompido):
        # O mesmo tratamento do detalhe do material.
        return _erro(500, "INTERNO", "Pacote de material corrompido.", request_id=str(uuid.uuid4()))

    resposta: HTTPException | None = None
    if isinstance(exc, RespostaVazia):
        resposta = _erro(502, "CHAT_RESPOSTA_VAZIA", "O modelo não devolveu uma resposta. Tente novamente.")
    elif isinstance(exc, ErroRespostaInvalida):
        resposta = _erro(502, "CHAT_RESPOSTA_INVALIDA", "O modelo devolveu uma resposta inválida. Tente novamente.")
    elif isinstance(exc, ErroTimeout):
        resposta = _erro(504, "CHAT_TEMPO_ESGOTADO", "A resposta demorou demais. Tente novamente.")
    elif isinstance(exc, ErroLimiteTaxa):
        resposta = _erro(
            429, "CHAT_PROVEDOR_OCUPADO", "O chat está ocupado. Tente novamente em alguns segundos.",
            headers={"Retry-After": str(RETRY_AFTER_PROVEDOR_SEGUNDOS)},
        )
    elif isinstance(exc, (ErroTransitorio, ErroConfiguracao)):
        resposta = _erro(503, "CHAT_INDISPONIVEL", _MSG_INDISPONIVEL)
    if resposta is not None:
        # Só o tipo: a mensagem original do provedor pode trazer detalhes dele.
        logger.warning("Chat: falha no material %s (%s).", material_id, type(exc).__name__)
    return resposta


def _consumir_limite(chave: str) -> None:
    espera = limite_chat.registrar(chave)
    if espera is not None:
        raise _erro(
            429, "CHAT_LIMITE_EXCEDIDO",
            "Limite de perguntas por minuto atingido. Aguarde um pouco para perguntar de novo.",
            headers={"Retry-After": str(segundos_para_cabecalho(espera))},
        )


def _responder(material_id: str, corpo: PerguntaChat) -> RespostaChatSaida:
    try:
        resultado = servico_chat.responder(
            material_id,
            corpo.pergunta,
            [(m.papel, m.conteudo) for m in corpo.historico],
            corpo.modelo,
        )
    except Exception as exc:
        traduzido = traduzir_erro(exc, material_id)
        if traduzido is None:
            raise
        raise traduzido from None
    return RespostaChatSaida(**asdict(resultado))


_RESPOSTAS_DE_ERRO = {
    404: {"description": "Material não encontrado (ou não disponível para o aluno)."},
    422: {"description": "Entrada inválida: VALIDACAO, PERGUNTA_VAZIA, PERGUNTA_LONGA ou CHAT_MODELO_NAO_PERMITIDO."},
    429: {"description": "CHAT_LIMITE_EXCEDIDO ou CHAT_PROVEDOR_OCUPADO, com Retry-After."},
    502: {"description": "CHAT_RESPOSTA_VAZIA ou CHAT_RESPOSTA_INVALIDA."},
    503: {"description": "CHAT_INDISPONIVEL."},
    504: {"description": "CHAT_TEMPO_ESGOTADO."},
}


# ── POST /aluno/materiais/{material_id}/chat ─────────────────────────────────


@router.post(
    "/aluno/materiais/{material_id}/chat",
    response_model=RespostaChatSaida,
    responses=_RESPOSTAS_DE_ERRO,
    summary="Pergunta do aluno sobre um material publicado e vinculado a ele",
)
def chat_do_aluno(
    material_id: str,
    corpo: PerguntaChat,
    aluno_id: Annotated[str, Query(min_length=1)],
    db: Session = Depends(get_db),
) -> RespostaChatSaida:
    _obter_aluno_ativo(db, aluno_id)
    _consumir_limite(f"aluno:{aluno_id}")
    if alunos_service.material_do_aluno(db, aluno_id, material_id) is None:
        raise _material_nao_encontrado()
    return _responder(material_id, corpo)


# ── POST /materiais/{material_id}/chat ───────────────────────────────────────


@router.post(
    "/materiais/{material_id}/chat",
    response_model=RespostaChatSaida,
    responses=_RESPOSTAS_DE_ERRO,
    summary="Pergunta da empresa sobre um material, em qualquer visibilidade",
)
def chat_da_empresa(
    material_id: str, corpo: PerguntaChat, db: Session = Depends(get_db)
) -> RespostaChatSaida:
    _consumir_limite(CHAVE_EMPRESA)
    if db.get(MaterialDB, material_id) is None:
        raise _material_nao_encontrado()
    return _responder(material_id, corpo)


# ── GET /chat/modelos ─────────────────────────────────────────────────────────


@router.get("/chat/modelos", response_model=ModelosChat, summary="Modelos aceitos pelo chat")
def listar_modelos() -> ModelosChat:
    modelos = modelos_do_chat()
    return ModelosChat(padrao=modelo_padrao_do_chat() or (modelos[0] if modelos else ""), modelos=modelos)
