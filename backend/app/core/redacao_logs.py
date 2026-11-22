"""Remove chaves e credenciais dos logs, mesmo quando vêm no texto de uma exceção.

O código evita logar segredos, mas a mensagem de uma exceção de biblioteca
(e a causa encadeada que o traceback mostra) pode trazê-los, por exemplo numa
URL com ``?key=``. Esta fábrica de ``LogRecord`` troca o valor dos segredos
por ``***`` na mensagem, nos argumentos e no traceback, para todos os
handlers (console, arquivo ou captura de testes).

Segredos considerados: ``settings.google_api_key`` e o valor de toda variável
de ambiente cujo nome termina em ``API_KEY``, ``SECRET``, ``TOKEN``,
``PASSWORD``, ``PRIVATE_KEY`` ou ``ACCESS_KEY``. Valores com menos de
``TAMANHO_MINIMO`` caracteres são ignorados, para não mascarar texto comum.
"""

from __future__ import annotations

import logging
import os
import re

from app.core.config import settings

MASCARA = "***"
TAMANHO_MINIMO = 8
_NOME_SECRETO = re.compile(r"(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY|ACCESS_KEY)$", re.IGNORECASE)


def segredos_conhecidos() -> list[str]:
    """Valores a esconder, os mais longos primeiro (para não deixar sobra de um prefixo)."""
    valores = {settings.google_api_key}
    valores.update(valor for nome, valor in os.environ.items() if _NOME_SECRETO.search(nome))
    return sorted((v for v in valores if v and len(v) >= TAMANHO_MINIMO), key=len, reverse=True)


def mascarar(texto: str, segredos: list[str] | None = None) -> str:
    for segredo in segredos if segredos is not None else segredos_conhecidos():
        texto = texto.replace(segredo, MASCARA)
    return texto


def _mascarar_argumento(argumento, segredos: list[str]):
    """Mantém o argumento original, a menos que o seu texto contenha um segredo."""
    if isinstance(argumento, (int, float, bool)) or argumento is None:
        return argumento
    try:
        texto = argumento if isinstance(argumento, str) else str(argumento)
    except Exception:
        return argumento
    mascarado = mascarar(texto, segredos)
    return argumento if mascarado == texto else mascarado


def _limpar_registro(registro: logging.LogRecord) -> None:
    segredos = segredos_conhecidos()
    if not segredos:
        return
    if isinstance(registro.msg, str):
        registro.msg = mascarar(registro.msg, segredos)
    if isinstance(registro.args, tuple):
        registro.args = tuple(_mascarar_argumento(a, segredos) for a in registro.args)
    elif isinstance(registro.args, dict):
        registro.args = {k: _mascarar_argumento(v, segredos) for k, v in registro.args.items()}
    if registro.exc_info and registro.exc_info[0] is not None and not registro.exc_text:
        # O Formatter reaproveita exc_text: o traceback já sai mascarado em todos os handlers.
        registro.exc_text = mascarar(logging.Formatter().formatException(registro.exc_info), segredos)


def instalar_redacao_de_segredos() -> None:
    """Passa a mascarar os segredos em todos os registros de log. Pode ser chamada de novo."""
    fabrica_atual = logging.getLogRecordFactory()
    if getattr(fabrica_atual, "_redige_segredos", False):
        return

    def fabrica(*args, **kwargs) -> logging.LogRecord:
        registro = fabrica_atual(*args, **kwargs)
        try:
            _limpar_registro(registro)
        except Exception:  # o log nunca pode derrubar a requisição
            pass
        return registro

    fabrica._redige_segredos = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(fabrica)
