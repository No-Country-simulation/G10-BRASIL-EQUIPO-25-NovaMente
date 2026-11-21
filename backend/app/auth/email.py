"""Envio do código de verificação por e-mail.

``EnviadorEmail`` tem duas implementações, escolhidas por ``EMAIL_MODO``:

- ``ConsoleEnviador``: escreve destinatário e código no log (INFO). Só para
  desenvolvimento; a subida avisa com um WARNING quando o login está ligado.
- ``SmtpEnviador``: smtplib com STARTTLS e timeout de 10 s. Nunca escreve o
  código nem a senha do SMTP no log; qualquer falha vira ``ErroEnvioEmail``
  sem os detalhes do servidor.

As rotas recebem o enviador por ``obter_enviador`` (``Depends``), que os
testes trocam por um falso. As rotas são síncronas e rodam no pool de
threads, então o SMTP não bloqueia o loop assíncrono.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.auth.codigos import VALIDADE_SEGUNDOS
from app.core.config import settings

logger = logging.getLogger(__name__)

ASSUNTO = "Seu código de verificação do NovaMente"
TIMEOUT_SMTP_SEGUNDOS = 10


class ErroEnvioEmail(Exception):
    """O e-mail não pôde ser enviado (a mensagem não traz detalhes do servidor)."""


class EnviadorEmail(Protocol):
    def enviar_codigo(self, destinatario: str, codigo: str) -> None: ...


def montar_mensagem(remetente: str, destinatario: str, codigo: str) -> EmailMessage:
    minutos = VALIDADE_SEGUNDOS // 60
    texto = (
        "Olá!\n\n"
        f"Seu código de verificação do NovaMente é: {codigo}\n\n"
        f"Ele vale por {minutos} minutos.\n\n"
        "Se não foi você, ignore este e-mail.\n"
    )
    html = (
        "<!doctype html><html lang=\"pt-BR\"><body>"
        "<p>Olá!</p>"
        "<p>Seu código de verificação do NovaMente é:</p>"
        f"<p style=\"font-size:24px;font-weight:bold;letter-spacing:4px\">{codigo}</p>"
        f"<p>Ele vale por {minutos} minutos.</p>"
        "<p>Se não foi você, ignore este e-mail.</p>"
        "</body></html>"
    )
    mensagem = EmailMessage()
    mensagem["Subject"] = ASSUNTO
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto)
    mensagem.add_alternative(html, subtype="html")
    return mensagem


class ConsoleEnviador:
    """Só desenvolvimento: o código aparece no log."""

    def enviar_codigo(self, destinatario: str, codigo: str) -> None:
        logger.info("E-mail (modo console) para %s: código de verificação %s", destinatario, codigo)


class SmtpEnviador:
    def __init__(
        self, host: str, porta: int, usuario: str, senha: str, remetente: str,
        *, timeout: float = TIMEOUT_SMTP_SEGUNDOS,
    ):
        self.host = host
        self.porta = porta
        self.usuario = usuario
        self._senha = senha
        self.remetente = remetente
        self.timeout = timeout

    def enviar_codigo(self, destinatario: str, codigo: str) -> None:
        mensagem = montar_mensagem(self.remetente, destinatario, codigo)
        try:
            with smtplib.SMTP(self.host, self.porta, timeout=self.timeout) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(self.usuario, self._senha)
                smtp.send_message(mensagem)
        except (smtplib.SMTPException, OSError) as exc:
            # Só o tipo: a resposta do servidor pode ecoar dados da conta.
            logger.error("Falha ao enviar e-mail por SMTP (%s).", type(exc).__name__)
            raise ErroEnvioEmail("Falha no envio do e-mail.") from None


def obter_enviador() -> EnviadorEmail:
    """Dependência das rotas: o enviador conforme ``EMAIL_MODO``."""
    if settings.email_modo == "smtp":
        return SmtpEnviador(
            settings.smtp_host,
            settings.smtp_porta,
            settings.smtp_usuario,
            settings.smtp_senha.get_secret_value(),
            settings.email_remetente,
        )
    return ConsoleEnviador()
