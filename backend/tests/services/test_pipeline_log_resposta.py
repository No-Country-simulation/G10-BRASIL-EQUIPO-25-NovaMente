"""Linha de log "Resposta inválida do LLM": motivo seguro, sem texto do documento nem da resposta."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.llm.erros import ErroRespostaInvalida, ErroTimeout
from app.llm.nvidia import ProvedorNvidia
from app.services import pipeline

SEGREDO = "trecho-confidencial-do-documento"
QUIZ = {
    "titulo": "Quiz", "introducao_contextualizada": "Revisão.",
    "itens": [{"pergunta": "Qual?", "opcoes": ["GET", "POST"], "resposta_correta": 1, "explicacao": "Porque."}],
}


class ProvedorFila:
    nome = "fila"

    def __init__(self, *respostas):
        self.respostas = list(respostas)

    def gerar(self, mensagens, *, timeout_segundos):
        item = self.respostas.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _quiz(**mudancas):
    dados = json.loads(json.dumps(QUIZ))
    for chave, valor in mudancas.items():
        if valor is None:
            del dados["itens"][0][chave]
        else:
            dados["itens"][0][chave] = valor
    return json.dumps(dados)


def _linhas(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("Resposta inválida do LLM")]


def _gerar(caplog, *respostas):
    caplog.set_level(logging.WARNING, logger=pipeline.logger.name)
    pipeline._gerar_conteudo(ProvedorFila(*respostas, json.dumps(QUIZ)), "prompt", "Quiz", lambda: None)
    (linha,) = _linhas(caplog)
    assert SEGREDO not in linha
    return linha


def _nvidia(monkeypatch, corpo: dict) -> ProvedorNvidia:
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr("nvapi-chave-falsa-do-log"))
    return ProvedorNvidia("m", "http://nim.teste/v1", transporte=httpx.MockTransport(
        lambda _req: httpx.Response(200, json=corpo)))


@pytest.mark.parametrize(
    "escolha,mensagem",
    [
        ({"message": {"content": SEGREDO}, "finish_reason": "length"},
         "NVIDIA NIM: resposta cortada pelo limite de tokens; aumente NVIDIA_NIM_MAX_TOKENS ou reduza o raciocínio."),
        ({"message": {"content": None}, "finish_reason": "stop"}, "NVIDIA NIM: resposta sem texto."),
        ({"message": {"content": f"<think>{SEGREDO}</think>"}, "finish_reason": "stop"}, "NVIDIA NIM: resposta vazia."),
    ],
)
def test_mensagens_do_provedor_nvidia_aparecem_no_log(monkeypatch, caplog, escolha, mensagem):
    # O provedor de verdade, com HTTP simulado: garante que a lista de mensagens
    # conhecidas acompanha o texto de app/llm/nvidia.py.
    nvidia = _nvidia(monkeypatch, {"choices": [escolha]})
    with pytest.raises(ErroRespostaInvalida) as erro:
        nvidia.gerar([], timeout_segundos=1)
    # Pelo caminho real: _chamar_llm embrulha o erro do provedor em _RespostaInvalida.
    linha = _gerar(caplog, erro.value)
    assert linha == f"Resposta inválida do LLM (tentativa 1 de 3): _RespostaInvalida; {mensagem}"


def test_mensagem_desconhecida_do_provedor_vira_categoria(caplog):
    linha = _gerar(caplog, ErroRespostaInvalida(f"bloqueado por {SEGREDO}"))
    assert linha.endswith("_RespostaInvalida; erro do provedor sem mensagem conhecida (ErroRespostaInvalida)")


def test_mensagem_sem_texto_do_gemini(caplog):
    linha = _gerar(caplog, ErroRespostaInvalida("Resposta sem texto: ValueError"))
    assert linha.endswith("_RespostaInvalida; Resposta sem texto: ValueError")


@pytest.mark.parametrize(
    "resposta,final",
    [
        (f'{{"titulo": "{SEGREDO}", "itens": [}}', "JSONDecodeError; não é JSON: Expecting value (caractere "),
        (f'{{"titulo": "{SEGREDO}\n"}}', "JSONDecodeError; não é JSON: Invalid control character at (caractere "),
        (f"Sem JSON: {SEGREDO}", "ValueError; LLM não retornou JSON válido."),
        (_quiz(resposta_correta=SEGREDO), "ValidationError; fora do esquema: 1 erro(s): resposta_correta int_parsing"),
        (_quiz(explicacao=None), "ValidationError; fora do esquema: 1 erro(s): explicacao missing"),
        (json.dumps({"introducao_contextualizada": SEGREDO, "itens": []}), "KeyError; campo ausente: titulo"),
        (json.dumps({"titulo": "T", "introducao_contextualizada": "I", "itens": [SEGREDO]}),
         "TypeError; item fora do formato (não é objeto)"),
    ],
)
def test_erros_de_formato_mostram_so_a_categoria(caplog, resposta, final):
    linha = _gerar(caplog, resposta)
    assert final in linha


def test_comportamento_nao_muda(caplog):
    caplog.set_level(logging.WARNING, logger=pipeline.logger.name)
    with pytest.raises(RuntimeError, match="não devolveu um conteúdo válido"):
        pipeline._gerar_conteudo(ProvedorFila("nada", "nada", "nada", json.dumps(QUIZ)), "p", "Quiz", lambda: None)
    assert len(_linhas(caplog)) == 3
    # Timeout continua fora da repetição por resposta inválida (e sem esta linha de log).
    caplog.clear()
    with pytest.raises(RuntimeError, match="demorou demais"):
        pipeline._gerar_conteudo(ProvedorFila(ErroTimeout("t")), "p", "Quiz", lambda: None)
    assert _linhas(caplog) == []
