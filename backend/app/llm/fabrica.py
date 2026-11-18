"""Fábrica de provedores de LLM, escolhidos por ``LLM_PROVIDER``.

Cada provedor é registrado por nome com um construtor sem argumentos e é
entregue embrulhado em ``ProvedorComRetentativa`` (app/llm/retentativa.py). A
instância do provedor configurado é única e reaproveitada entre jobs; ela só
é recriada se ``LLM_PROVIDER`` mudar ou se ``redefinir_provedor`` for chamado.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.core.config import settings
from app.llm.base import ProvedorLLM
from app.llm.erros import ProvedorDesconhecido
from app.llm.retentativa import ProvedorComRetentativa

ConstrutorProvedor = Callable[[], ProvedorLLM]


def _criar_gemini() -> ProvedorLLM:
    from app.llm.gemini import ProvedorGemini

    return ProvedorGemini(modelo=settings.modelo_llm)


_construtores: dict[str, ConstrutorProvedor] = {"gemini": _criar_gemini}
_instancia: ProvedorLLM | None = None
_nome_instancia: str | None = None
_trava = threading.Lock()


def _normalizar(nome: str) -> str:
    return nome.strip().lower()


def registrar_provedor(nome: str, construtor: ConstrutorProvedor) -> None:
    """Registra (ou substitui) o construtor de um provedor pelo nome."""
    global _instancia, _nome_instancia
    chave = _normalizar(nome)
    with _trava:
        _construtores[chave] = construtor
        if _nome_instancia == chave:
            _instancia, _nome_instancia = None, None


def provedores_disponiveis() -> list[str]:
    """Nomes registrados, em ordem alfabética."""
    return sorted(_construtores)


def validar_provedor_configurado() -> str:
    """Confere ``LLM_PROVIDER`` sem criar o provedor; levanta ``ProvedorDesconhecido``."""
    nome = _normalizar(settings.llm_provider)
    if nome not in _construtores:
        raise ProvedorDesconhecido(
            f"LLM_PROVIDER '{settings.llm_provider}' desconhecido. "
            f"Valores válidos: {', '.join(provedores_disponiveis())}."
        )
    return nome


def obter_provedor() -> ProvedorLLM:
    """Instância única do provedor configurado em ``LLM_PROVIDER``, com retentativa."""
    global _instancia, _nome_instancia
    nome = validar_provedor_configurado()
    with _trava:
        if _instancia is None or _nome_instancia != nome:
            _instancia = ProvedorComRetentativa(_construtores[nome]())
            _nome_instancia = nome
        return _instancia


def redefinir_provedor() -> None:
    """Descarta a instância atual; a próxima chamada cria outra."""
    global _instancia, _nome_instancia
    with _trava:
        _instancia, _nome_instancia = None, None
