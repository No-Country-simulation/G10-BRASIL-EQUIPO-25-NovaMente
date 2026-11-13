"""Provedores de LLM: contrato, erros normalizados e fábrica por configuração."""

from app.llm.base import Mensagem, PapelMensagem, ProvedorLLM
from app.llm.erros import (
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroLLM,
    ErroRespostaInvalida,
    ErroTimeout,
    ErroTransitorio,
    ProvedorDesconhecido,
)
from app.llm.fabrica import (
    obter_provedor,
    provedores_disponiveis,
    redefinir_provedor,
    registrar_provedor,
    validar_provedor_configurado,
)

__all__ = [
    "ErroConfiguracao",
    "ErroIndisponivel",
    "ErroLimiteTaxa",
    "ErroLLM",
    "ErroRespostaInvalida",
    "ErroTimeout",
    "ErroTransitorio",
    "Mensagem",
    "PapelMensagem",
    "ProvedorDesconhecido",
    "ProvedorLLM",
    "obter_provedor",
    "provedores_disponiveis",
    "redefinir_provedor",
    "registrar_provedor",
    "validar_provedor_configurado",
]
