"""Erros normalizados dos provedores de LLM.

Cada adaptador converte as exceções do seu SDK nestas categorias, para que o
resto do backend não dependa de nenhum SDK. A mensagem destas exceções é
técnica e vai só para o log: quem fala com o usuário é o pipeline.
"""

from __future__ import annotations


class ErroLLM(Exception):
    """Base de todos os erros de provedor de LLM."""


class ErroTransitorio(ErroLLM):
    """Falha passageira do serviço; tentar de novo mais tarde pode funcionar."""


class ErroLimiteTaxa(ErroTransitorio):
    """Limite de uso ou de requisições atingido (HTTP 429)."""


class ErroIndisponivel(ErroTransitorio):
    """Serviço fora do ar, erro 5xx ou falha de conexão."""


class ErroTimeout(ErroLLM):
    """O modelo não respondeu dentro do tempo limite da chamada."""


class ErroRespostaInvalida(ErroLLM):
    """Resposta vazia, bloqueada ou sem texto."""


class ErroConfiguracao(ErroLLM):
    """Chave ausente ou inválida, modelo inexistente ou argumento recusado."""


class ProvedorDesconhecido(ErroConfiguracao):
    """``LLM_PROVIDER`` aponta para um provedor que não está registrado."""


class ErroModeloIndisponivel(ErroConfiguracao):
    """O modelo configurado não existe ou saiu do catálogo do provedor (HTTP 404)."""


class ErroAutenticacao(ErroConfiguracao):
    """Chave inválida ou sem acesso ao modelo (HTTP 401/403)."""


class ErroRequisicaoRecusada(ErroConfiguracao):
    """O provedor recusou a requisição (HTTP 4xx), por exemplo um parâmetro que o modelo não aceita."""
