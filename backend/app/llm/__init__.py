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
    ProvedorDesconhecido,
)
from app.llm.retentativa import ProvedorComRetentativa, limites_da_geracao
from app.llm.fabrica import (
    obter_provedor,
    provedores_disponiveis,
    redefinir_provedor,
    registrar_provedor,
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
    "PapelMensagem",
    "ProvedorComRetentativa",
    "ProvedorDesconhecido",
    "ProvedorLLM",
    "limites_da_geracao",
    "obter_provedor",
    "provedores_disponiveis",
    "redefinir_provedor",
    "registrar_provedor",
    "validar_provedor_configurado",
]
