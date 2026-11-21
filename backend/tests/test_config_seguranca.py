"""Variáveis de segurança do config: padrões, parsing e validação na subida."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _config(monkeypatch, **env) -> Settings:
    for nome in (
        "CORS_ORIGINS",
        "GERACAO_LIMITE_POR_MINUTO",
        "GERACAO_MAX_JOBS_SIMULTANEOS",
        "CONFIAR_X_FORWARDED_FOR",
    ):
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in env.items():
        monkeypatch.setenv(nome, valor)
    return Settings(_env_file=None)


def test_padroes(monkeypatch):
    config = _config(monkeypatch)
    assert config.cors_origins_lista == ["http://localhost:3000"]
    assert config.geracao_limite_por_minuto == 6
    assert config.geracao_max_jobs_simultaneos == 4
    assert config.confiar_x_forwarded_for is False


def test_cors_origins_separa_por_virgula_tira_espacos_e_ignora_vazias(monkeypatch):
    config = _config(
        monkeypatch,
        CORS_ORIGINS=" https://app.exemplo.com , ,http://localhost:3000,, https://b.exemplo.com:8443 ",
    )
    assert config.cors_origins_lista == [
        "https://app.exemplo.com",
        "http://localhost:3000",
        "https://b.exemplo.com:8443",
    ]


def test_cors_origins_com_curinga_impede_a_subida(monkeypatch):
    with pytest.raises(ValidationError) as erro:
        _config(monkeypatch, CORS_ORIGINS="*")
    assert "CORS_ORIGINS" in str(erro.value)
    assert "credenciais" in str(erro.value)


def test_cors_origins_com_curinga_no_meio_da_lista_tambem_impede(monkeypatch):
    with pytest.raises(ValidationError):
        _config(monkeypatch, CORS_ORIGINS="https://app.exemplo.com, *")


@pytest.mark.parametrize(
    "valor",
    [
        "",
        " , ,",
        "app.exemplo.com",  # sem esquema
        "https://app.exemplo.com/",  # barra final
        "https://app.exemplo.com/painel",  # caminho
        "ftp://app.exemplo.com",
    ],
)
def test_cors_origins_invalida_impede_a_subida(monkeypatch, valor):
    with pytest.raises(ValidationError) as erro:
        _config(monkeypatch, CORS_ORIGINS=valor)
    assert "CORS_ORIGINS" in str(erro.value)


@pytest.mark.parametrize("nome", ["GERACAO_LIMITE_POR_MINUTO", "GERACAO_MAX_JOBS_SIMULTANEOS"])
@pytest.mark.parametrize("valor", ["0", "-1", "abc", "1.5"])
def test_limites_invalidos_impedem_a_subida(monkeypatch, nome, valor):
    with pytest.raises(ValidationError):
        _config(monkeypatch, **{nome: valor})


def test_limites_validos(monkeypatch):
    config = _config(
        monkeypatch,
        GERACAO_LIMITE_POR_MINUTO="1",
        GERACAO_MAX_JOBS_SIMULTANEOS="10",
        CONFIAR_X_FORWARDED_FOR="true",
    )
    assert config.geracao_limite_por_minuto == 1
    assert config.geracao_max_jobs_simultaneos == 10
    assert config.confiar_x_forwarded_for is True
