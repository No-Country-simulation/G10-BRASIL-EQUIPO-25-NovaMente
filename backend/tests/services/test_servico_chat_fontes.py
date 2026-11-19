"""Parâmetros ``fontes`` e ``provedor`` de ``servico_chat.responder`` (usados na medição).

Sem eles o comportamento é o das rotas: fontes do banco e provedor da fábrica.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import repositorio, servico_chat
from app.services.contexto_chat import limpar_cache, montar_fontes

TEXTO = "\n\n".join(
    f"Seção {i}. Uma VCN é a rede virtual privada da nuvem, dividida em subnets públicas e privadas."
    for i in range(6)
)


class _Provedor:
    nome = "teste"

    def __init__(self, modelo):
        self.modelo = modelo
        self.chamadas = 0

    def gerar(self, mensagens, *, timeout_segundos):
        self.chamadas += 1
        return "Resposta [F1]."


@pytest.fixture(autouse=True)
def _configuracao(monkeypatch):
    for campo, valor in {
        "chat_llm_timeout_segundos": 45,
        "chat_max_pergunta_caracteres": 1000,
        "chat_max_mensagens_historico": 10,
        "chat_max_contexto_caracteres": 24_000,
    }.items():
        monkeypatch.setattr(settings, campo, valor)
    limpar_cache()
    yield
    limpar_cache()


def test_sem_parametros_usa_o_banco_e_a_fabrica(monkeypatch, pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    da_fabrica = _Provedor("org/da-fabrica")
    pedidos = []
    carregados = []
    original = servico_chat.carregar_fontes
    monkeypatch.setattr(servico_chat, "obter_provedor_chat", lambda modelo: pedidos.append(modelo) or da_fabrica)
    monkeypatch.setattr(servico_chat, "carregar_fontes", lambda mid: carregados.append(mid) or original(mid))

    resultado = servico_chat.responder(pacote_exemplo.adaptacao_id, "O que é uma VCN?", modelo="org/x")
    assert pedidos == ["org/x"]
    assert carregados == [pacote_exemplo.adaptacao_id]
    assert da_fabrica.chamadas == 1
    assert resultado.modelo == "org/da-fabrica"
    assert resultado.base == "documento_e_pacote"


def test_com_fontes_e_provedor_nao_toca_no_banco_nem_na_fabrica(monkeypatch, pacote_exemplo):
    def proibido(*_a, **_k):
        raise AssertionError("não deveria ser chamado")

    monkeypatch.setattr(servico_chat, "obter_provedor_chat", proibido)
    monkeypatch.setattr(servico_chat, "carregar_fontes", proibido)
    fontes = montar_fontes("em-memoria", pacote_exemplo, TEXTO)
    provedor = _Provedor("org/escolhido")
    resultado = servico_chat.responder("em-memoria", "O que é uma VCN?", fontes=fontes, provedor=provedor)
    assert provedor.chamadas == 1
    assert resultado.modelo == "org/escolhido"
    assert [c.id for c in resultado.citacoes] == ["F1"]


def test_parametros_novos_so_por_nome(pacote_exemplo):
    fontes = montar_fontes("x", pacote_exemplo, TEXTO)
    with pytest.raises(TypeError):
        servico_chat.responder("x", "O que é uma VCN?", (), None, fontes)  # type: ignore[misc]
