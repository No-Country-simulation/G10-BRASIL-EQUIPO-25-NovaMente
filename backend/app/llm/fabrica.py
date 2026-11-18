"""Fábrica de provedores de LLM, escolhidos por ``LLM_PROVIDER``.

Cada provedor é registrado por nome com um construtor sem argumentos e é
entregue embrulhado em ``ProvedorComRetentativa`` (app/llm/retentativa.py). A
instância do provedor configurado é única e reaproveitada entre jobs; ela só
é recriada se ``LLM_PROVIDER`` mudar ou se ``redefinir_provedor`` for chamado.

O chat tem fábrica e cache próprios (``obter_provedor_chat``, ``CHAT_LLM_*``),
independentes de ``LLM_PROVIDER``; veja a seção "Chat" no fim do arquivo.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from app.core.config import settings
from app.llm.base import ProvedorLLM
from app.llm.chat import ProvedorDoChat
from app.llm.erros import ErroConfiguracao, ModeloNaoPermitido, ProvedorDesconhecido
from app.llm.retentativa import ProvedorComRetentativa

ConstrutorProvedor = Callable[[], ProvedorLLM]


def _criar_gemini() -> ProvedorLLM:
    from app.llm.gemini import ProvedorGemini

    return ProvedorGemini(modelo=settings.modelo_llm)


def _criar_nvidia() -> ProvedorLLM:
    from app.llm.nvidia import criar_provedor_nvidia

    return criar_provedor_nvidia()


_construtores: dict[str, ConstrutorProvedor] = {"gemini": _criar_gemini, "nvidia": _criar_nvidia}
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
    with _trava_chat:
        for chave_chat in [c for c in _cache_chat if c[0] == chave]:
            del _cache_chat[chave_chat]


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


# ── Chat ──────────────────────────────────────────────────────────────────────
#
# O chat tem provedor, modelo e cache próprios (CHAT_LLM_*), independentes de
# LLM_PROVIDER: trocar um não mexe no outro.

_cache_chat: dict[tuple[str, str, str], ProvedorLLM] = {}
_trava_chat = threading.Lock()


def validar_provedor_chat_configurado() -> str:
    """Confere ``CHAT_LLM_PROVIDER`` e ``CHAT_LLM_RACIOCINIO`` sem criar o provedor nem exigir chave."""
    nome = _normalizar(settings.chat_llm_provider) or "nvidia"
    if nome not in _construtores:
        raise ProvedorDesconhecido(
            f"CHAT_LLM_PROVIDER '{settings.chat_llm_provider}' desconhecido. "
            f"Valores válidos: {', '.join(provedores_disponiveis())}."
        )
    if _raciocinio_do_chat() not in ("ligado", "desligado"):
        raise ErroConfiguracao(
            f"CHAT_LLM_RACIOCINIO '{settings.chat_llm_raciocinio}' inválido. "
            "Valores válidos: vazio (desligado), ligado, desligado."
        )
    return nome


def _raciocinio_do_chat() -> str:
    return (settings.chat_llm_raciocinio or "").strip().lower() or "desligado"


def modelo_padrao_do_chat() -> str:
    """``CHAT_LLM_MODELO`` ou, vazio, o modelo padrão do provedor do chat.

    Para provedores registrados sem modelo próprio na configuração, vazio.
    """
    if settings.chat_llm_modelo.strip():
        return settings.chat_llm_modelo.strip()
    nome = validar_provedor_chat_configurado()
    if nome == "nvidia":
        return settings.nvidia_nim_modelo
    if nome == "gemini":
        return settings.modelo_llm
    return ""


def modelos_do_chat() -> list[str]:
    """Modelos que o chat aceita, com o padrão primeiro e sem repetição (sem rede)."""
    padrao = modelo_padrao_do_chat()
    extras = [m.strip() for m in settings.chat_modelos_permitidos.split(",")]
    return list(dict.fromkeys(m for m in [padrao, *extras] if m))


def _criar_base_do_chat(nome: str, modelo: str, raciocinio: str) -> ProvedorLLM:
    if nome == "nvidia":
        from app.llm.nvidia import ProvedorNvidia

        return ProvedorNvidia(
            modelo=modelo,
            base_url=settings.nvidia_nim_base_url,
            temperatura=settings.chat_llm_temperatura,
            max_tokens=settings.chat_llm_max_tokens,
            raciocinio=raciocinio,
        )
    if nome == "gemini" and modelo:
        from app.llm.gemini import ProvedorGemini

        return ProvedorGemini(modelo=modelo)
    return _construtores[nome]()


def obter_provedor_chat(modelo: str | None = None) -> ProvedorLLM:
    """Provedor do chat, com prazo total por pergunta e no máximo uma retentativa.

    ``modelo`` precisa estar em :func:`modelos_do_chat` (senão
    ``ModeloNaoPermitido``); vazio ou ``None`` usa o padrão. Chame ``gerar``
    com ``timeout_segundos=settings.chat_llm_timeout_segundos``: no chat é o
    prazo da pergunta inteira (app/llm/chat.py).

    Na nvidia valem modelo, raciocínio, temperatura e max_tokens do chat. No
    gemini vale só o modelo (temperatura, tokens e raciocínio ficam os do SDK).
    Outros provedores registrados usam o próprio construtor, sem nenhum
    desses ajustes. Uma instância por (provedor, modelo, raciocínio).
    """
    nome = validar_provedor_chat_configurado()
    permitidos = modelos_do_chat()
    escolhido = (modelo or "").strip() or modelo_padrao_do_chat()
    if modelo and modelo.strip() and escolhido not in permitidos:
        raise ModeloNaoPermitido(escolhido, permitidos)
    raciocinio = _raciocinio_do_chat()
    chave = (nome, escolhido, raciocinio)
    with _trava_chat:
        if chave not in _cache_chat:
            _cache_chat[chave] = ProvedorDoChat(_criar_base_do_chat(nome, escolhido, raciocinio))
        return _cache_chat[chave]


def redefinir_provedor_chat() -> None:
    """Descarta as instâncias do chat; as próximas chamadas criam outras."""
    with _trava_chat:
        _cache_chat.clear()
