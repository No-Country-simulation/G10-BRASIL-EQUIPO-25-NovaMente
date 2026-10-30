"""Garante o modelo LLM padrão quando nada é configurado no ambiente."""

from app.core.config import Settings


def test_modelo_llm_padrao_sem_env(monkeypatch):
    monkeypatch.delenv("MODELO_LLM", raising=False)
    config = Settings(_env_file=None)
    assert config.modelo_llm == "gemini-3.5-flash-lite"


def test_modelo_llm_respeita_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("MODELO_LLM", "outro-modelo")
    assert Settings(_env_file=None).modelo_llm == "outro-modelo"
