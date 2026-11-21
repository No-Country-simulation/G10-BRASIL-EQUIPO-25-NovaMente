"""Tentativas por resposta inválida em pipeline._gerar_conteudo (até 3, dentro do prazo do job)."""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.llm import limites_da_geracao, retentativa
from app.llm.erros import ErroRespostaInvalida
from app.services import pipeline

QUIZ = json.dumps({
    "titulo": "Quiz", "introducao_contextualizada": "Revisão.",
    "itens": [{"pergunta": "Qual?", "opcoes": ["GET", "POST"], "resposta_correta": 1, "explicacao": "Porque."}],
})


class ProvedorFila:
    nome = "fila"

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    def gerar(self, mensagens, *, timeout_segundos):
        self.chamadas += 1
        item = self.respostas.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _gerar(provedor):
    return pipeline._gerar_conteudo(provedor, "prompt", "Quiz", lambda: None)


def test_sao_tres_tentativas():
    assert pipeline._TENTATIVAS_RESPOSTA_INVALIDA == 3


def test_falha_falha_sucesso_devolve_o_resultado():
    provedor = ProvedorFila("não é json", ErroRespostaInvalida("NVIDIA NIM: resposta vazia."), QUIZ)
    _texto, conteudo, _conceitos = _gerar(provedor)
    assert conteudo.titulo == "Quiz" and provedor.chamadas == 3


def test_tres_falhas_levantam_resposta_invalida():
    provedor = ProvedorFila("nada", '{"titulo": ', ErroRespostaInvalida("NVIDIA NIM: resposta vazia."), QUIZ)
    with pytest.raises(RuntimeError) as erro:
        _gerar(provedor)
    assert str(erro.value) == pipeline._MSG_RESPOSTA_INVALIDA
    assert provedor.chamadas == 3  # a quarta resposta nunca é pedida


def test_nao_comeca_tentativa_que_nao_cabe_no_prazo(monkeypatch):
    agora = [0.0]
    monkeypatch.setattr(retentativa, "_relogio", lambda: agora[0])
    monkeypatch.setattr(settings, "llm_timeout_segundos", 120)

    class Lento(ProvedorFila):
        def gerar(self, mensagens, *, timeout_segundos):
            agora[0] += 100  # cada chamada consome 100 s do prazo
            return super().gerar(mensagens, timeout_segundos=timeout_segundos)

    provedor = Lento("nada", "nada", QUIZ)
    # Prazo de 300 s: depois da 1ª (t=100) cabe a 2ª (100 + 120 <= 300); depois da 2ª
    # (t=200) não cabe a 3ª (200 + 120 > 300), então falha sem estourar o prazo.
    with limites_da_geracao(300.0), pytest.raises(RuntimeError, match="não devolveu um conteúdo válido"):
        _gerar(provedor)
    assert provedor.chamadas == 2


def test_sem_prazo_vale_o_limite_de_tentativas():
    assert retentativa.cabe_outra_chamada(10_000) is True


def test_resposta_correta_fora_das_opcoes_entra_na_nova_tentativa(caplog):
    fora = json.loads(QUIZ)
    fora["itens"][0]["resposta_correta"] = 2  # só há 2 opções
    provedor = ProvedorFila(json.dumps(fora), QUIZ)
    _texto, conteudo, _ = _gerar(provedor)
    assert conteudo.itens[0].resposta_correta == 1 and provedor.chamadas == 2
    assert "resposta_correta resposta_fora_das_opcoes" in caplog.text
