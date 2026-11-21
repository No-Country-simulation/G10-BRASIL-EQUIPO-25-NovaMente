"""Conferência da configuração do login na subida."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from app.auth.configuracao import ConfiguracaoAuthInvalida, validar_configuracao_auth
from app.core.config import Settings
from tests.auth.apoio import SEGREDO_TESTE, SENHA_EMPRESA, hash_de

SENHA_SMTP = "senha-smtp-que-nao-pode-aparecer"


def _cfg(**campos) -> Settings:
    base = {
        "auth_habilitada": True,
        "sessao_segredo": SecretStr(SEGREDO_TESTE),
        "empresa_email": "empresa@exemplo.com",
        "empresa_senha_hash": SecretStr(hash_de(SENHA_EMPRESA)),
        "email_modo": "console",
    }
    base.update(campos)
    return Settings.model_construct(**{**Settings().model_dump(), **base})


def test_desligado_nao_confere_nada():
    validar_configuracao_auth(_cfg(auth_habilitada=False, sessao_segredo=SecretStr("")))


def test_configuracao_completa_em_console_avisa_no_log(caplog):
    caplog.set_level(logging.WARNING)
    validar_configuracao_auth(_cfg())
    assert any("EMAIL_MODO=console" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    "campos,trecho",
    [
        ({"sessao_segredo": SecretStr("curto")}, "SESSAO_SEGREDO precisa de pelo menos 32"),
        ({"empresa_email": ""}, "EMPRESA_EMAIL é obrigatório"),
        ({"empresa_senha_hash": SecretStr("")}, "EMPRESA_SENHA_HASH é obrigatório"),
        ({"empresa_senha_hash": SecretStr("Empresa@2026")}, "EMPRESA_SENHA_HASH não está no formato"),
        ({"email_modo": "smtp", "smtp_host": "smtp.exemplo.com"},
         "com EMAIL_MODO=smtp, defina SMTP_USUARIO, SMTP_SENHA, EMAIL_REMETENTE"),
    ],
)
def test_configuracao_incompleta_impede_a_subida(campos, trecho):
    with pytest.raises(ConfiguracaoAuthInvalida) as erro:
        validar_configuracao_auth(_cfg(**campos))
    assert trecho in str(erro.value)


def test_mensagem_nunca_traz_valores():
    with pytest.raises(ConfiguracaoAuthInvalida) as erro:
        validar_configuracao_auth(
            _cfg(sessao_segredo=SecretStr("segredo-curto"), empresa_senha_hash=SecretStr("Empresa@2026"),
                 email_modo="smtp", smtp_senha=SecretStr(SENHA_SMTP))
        )
    texto = str(erro.value)
    assert "segredo-curto" not in texto and "Empresa@2026" not in texto and SENHA_SMTP not in texto


def test_smtp_completo_sem_aviso(caplog):
    caplog.set_level(logging.WARNING)
    validar_configuracao_auth(
        _cfg(email_modo="smtp", smtp_host="smtp.exemplo.com", smtp_usuario="u",
             smtp_senha=SecretStr(SENHA_SMTP), email_remetente="nao-responda@exemplo.com")
    )
    assert not caplog.records


@pytest.mark.parametrize(
    "ambiente,esperado",
    [
        ({}, ("console", False, False, 587)),
        ({"AUTH_HABILITADA": "", "EMAIL_MODO": "", "SMTP_PORTA": "", "DEMO_HABILITADO": ""}, ("console", False, False, 587)),
        ({"AUTH_HABILITADA": "true", "EMAIL_MODO": " SMTP ", "SMTP_PORTA": "2525", "DEMO_HABILITADO": "1"}, ("smtp", True, True, 2525)),
    ],
)
def test_variaveis_vazias_valem_o_padrao(monkeypatch, ambiente, esperado):
    for nome in ("AUTH_HABILITADA", "EMAIL_MODO", "SMTP_PORTA", "DEMO_HABILITADO"):
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in ambiente.items():
        monkeypatch.setenv(nome, valor)
    cfg = Settings(_env_file=None)
    assert (cfg.email_modo, cfg.auth_habilitada, cfg.demo_habilitado, cfg.smtp_porta) == esperado


def test_email_modo_invalido(monkeypatch):
    monkeypatch.setenv("EMAIL_MODO", "pombo")
    with pytest.raises(ValueError, match="EMAIL_MODO"):
        Settings(_env_file=None)


def test_email_da_empresa_normalizado(monkeypatch):
    monkeypatch.setenv("EMPRESA_EMAIL", "  Empresa@Exemplo.COM ")
    assert Settings(_env_file=None).empresa_email == "empresa@exemplo.com"
