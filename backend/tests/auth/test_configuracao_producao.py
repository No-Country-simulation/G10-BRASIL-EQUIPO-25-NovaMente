"""EMAIL_MODO=console não sobe com SESSAO_COOKIE_SEGURO=true."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from app.auth.configuracao import ConfiguracaoAuthInvalida, validar_configuracao_auth
from app.core.config import Settings
from tests.auth.apoio import SEGREDO_TESTE, SENHA_EMPRESA, hash_de


def _cfg(**campos) -> Settings:
    return Settings.model_construct(**{
        **Settings(_env_file=None).model_dump(),
        "auth_habilitada": True,
        "sessao_segredo": SecretStr(SEGREDO_TESTE),
        "empresa_email": "empresa@exemplo.com",
        "empresa_senha_hash": SecretStr(hash_de(SENHA_EMPRESA)),
        **campos,
    })


def test_console_com_cookie_seguro_impede_a_subida():
    with pytest.raises(ConfiguracaoAuthInvalida) as erro:
        validar_configuracao_auth(_cfg(email_modo="console", sessao_cookie_seguro=True))
    assert (
        "EMAIL_MODO=console não é permitido com SESSAO_COOKIE_SEGURO=true (os códigos iriam para o log)"
        in str(erro.value)
    )


def test_console_sem_cookie_seguro_so_avisa(caplog):
    caplog.set_level(logging.WARNING)
    validar_configuracao_auth(_cfg(email_modo="console", sessao_cookie_seguro=False))
    assert any("EMAIL_MODO=console" in r.getMessage() for r in caplog.records)


def test_smtp_com_cookie_seguro_sobe():
    validar_configuracao_auth(_cfg(
        email_modo="smtp", sessao_cookie_seguro=True, smtp_host="smtp.exemplo.com",
        smtp_usuario="u", smtp_senha=SecretStr("s"), email_remetente="nao-responda@exemplo.com",
    ))
