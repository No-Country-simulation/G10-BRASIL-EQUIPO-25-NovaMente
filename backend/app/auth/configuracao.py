"""Conferência da configuração do login na subida (chamada no lifespan)."""

from __future__ import annotations

import logging

from app.auth.senhas import hash_valido
from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

SEGREDO_MINIMO = 32


class ConfiguracaoAuthInvalida(RuntimeError):
    """A mensagem lista as variáveis com problema, nunca os valores."""


def validar_configuracao_auth(cfg: Settings | None = None) -> None:
    cfg = cfg or settings
    if not cfg.auth_habilitada:
        return
    problemas: list[str] = []
    if len(cfg.sessao_segredo.get_secret_value()) < SEGREDO_MINIMO:
        problemas.append(f"SESSAO_SEGREDO precisa de pelo menos {SEGREDO_MINIMO} caracteres")
    if not cfg.empresa_email:
        problemas.append("EMPRESA_EMAIL é obrigatório")
    hash_empresa = cfg.empresa_senha_hash.get_secret_value().strip()
    if not hash_empresa:
        problemas.append("EMPRESA_SENHA_HASH é obrigatório (gere com scripts/gerar_hash_senha.py)")
    elif not hash_valido(hash_empresa):
        problemas.append("EMPRESA_SENHA_HASH não está no formato scrypt$n$r$p$salt$hash")
    if cfg.email_modo == "smtp":
        obrigatorios = {
            "SMTP_HOST": cfg.smtp_host,
            "SMTP_USUARIO": cfg.smtp_usuario,
            "SMTP_SENHA": cfg.smtp_senha.get_secret_value(),
            "EMAIL_REMETENTE": cfg.email_remetente,
        }
        faltando = [nome for nome, valor in obrigatorios.items() if not valor]
        if faltando:
            problemas.append(f"com EMAIL_MODO=smtp, defina {', '.join(faltando)}")
    elif cfg.sessao_cookie_seguro:
        # Cookie seguro indica produção (HTTPS): ali o código não pode ir para o log.
        problemas.append(
            "EMAIL_MODO=console não é permitido com SESSAO_COOKIE_SEGURO=true "
            "(os códigos iriam para o log)"
        )
    if problemas:
        raise ConfiguracaoAuthInvalida(
            "Configuração do login inválida (AUTH_HABILITADA=true): " + "; ".join(problemas) + "."
        )
    if cfg.email_modo == "console":
        logger.warning(
            "Login ligado com EMAIL_MODO=console: os códigos de verificação aparecem no log. "
            "Use só em desenvolvimento."
        )
