"""Provedores de LLM: contrato, erros normalizados e fábrica por configuração."""

from app.llm.base import Mensagem, PapelMensagem, ProvedorLLM
from app.llm.erros import (
    ErroAutenticacao,
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroLLM,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
    ErroRespostaInvalida,
    ErroTimeout,
    ErroTransitorio,
    ModeloNaoPermitido,
    ProvedorDesconhecido,
)
from app.llm.chat import ProvedorDoChat
from app.llm.retentativa import ProvedorComRetentativa, cabe_outra_chamada, limites_da_geracao
from app.llm.fabrica import (
    modelo_padrao_do_chat,
    modelos_do_chat,
    obter_provedor,
    obter_provedor_chat,
    provedores_disponiveis,
    redefinir_provedor,
    redefinir_provedor_chat,
    registrar_provedor,
    validar_provedor_chat_configurado,
    validar_provedor_configurado,
)

__all__ = [
    "ErroAutenticacao",
    "ErroConfiguracao",
    "ErroIndisponivel",
    "ErroLimiteTaxa",
    "ErroLLM",
    "ErroModeloIndisponivel",
    "ErroRequisicaoRecusada",
    "ErroRespostaInvalida",
    "ErroTimeout",
    "ErroTransitorio",
    "Mensagem",
    "ModeloNaoPermitido",
    "PapelMensagem",
    "ProvedorComRetentativa",
    "ProvedorDesconhecido",
    "ProvedorDoChat",
    "ProvedorLLM",
    "cabe_outra_chamada",
    "limites_da_geracao",
    "modelo_padrao_do_chat",
    "modelos_do_chat",
    "obter_provedor",
    "obter_provedor_chat",
    "provedores_disponiveis",
    "redefinir_provedor",
    "redefinir_provedor_chat",
    "registrar_provedor",
    "validar_provedor_chat_configurado",
    "validar_provedor_configurado",
]
