"""Fábrica de provedores e validação de ``LLM_PROVIDER`` na subida do app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.llm import (
    ProvedorDesconhecido,
    obter_provedor,
    provedores_disponiveis,
    registrar_provedor,
    validar_provedor_configurado,
)
from app.llm.gemini import ProvedorGemini
from app.main import app


class _ProvedorTeste:
    nome = "teste"

    def gerar(self, mensagens, *, timeout_segundos):
        return "ok"


def test_padrao_e_gemini(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert Settings(_env_file=None).llm_provider == "gemini"
    assert "gemini" in provedores_disponiveis()


def test_gemini_e_instancia_unica_e_nao_exige_chave_para_existir(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    provedor = obter_provedor()
    assert isinstance(provedor, ProvedorGemini)
    assert provedor.modelo == settings.modelo_llm
    assert obter_provedor() is provedor


def test_registrar_e_selecionar_por_nome_sem_diferenciar_maiusculas(monkeypatch):
    registrar_provedor("Teste", _ProvedorTeste)
    monkeypatch.setattr(settings, "llm_provider", "  TESTE ")
    provedor = obter_provedor()
    assert isinstance(provedor, _ProvedorTeste)
    assert obter_provedor() is provedor
    assert "teste" in provedores_disponiveis()


def test_trocar_llm_provider_troca_a_instancia(monkeypatch):
    registrar_provedor("teste", _ProvedorTeste)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    gemini = obter_provedor()
    monkeypatch.setattr(settings, "llm_provider", "teste")
    assert isinstance(obter_provedor(), _ProvedorTeste)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    assert obter_provedor() is not gemini  # recriado depois da troca


def test_provedor_desconhecido_tem_mensagem_com_nomes_validos(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "inexistente")
    with pytest.raises(ProvedorDesconhecido) as erro:
        validar_provedor_configurado()
    assert "'inexistente'" in str(erro.value)
    assert "gemini" in str(erro.value)
    with pytest.raises(ProvedorDesconhecido):
        obter_provedor()


def test_llm_provider_desconhecido_impede_a_subida(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "inexistente")
    with pytest.raises(ProvedorDesconhecido, match="Valores válidos: gemini"):
        with TestClient(app):
            pass


def test_subida_sem_chave_continua_funcionando(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "google_api_key", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with TestClient(app) as client:
        resposta = client.get("/api/v1/health")
    assert resposta.status_code == 200
    assert resposta.json()["llm"] == "indisponivel"
