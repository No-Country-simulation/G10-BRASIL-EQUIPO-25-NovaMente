"""Limites do login, sobre o ``LimiteDeTaxa`` do projeto (em memória, por processo).

- envio de código: 3 por e-mail e 10 por IP a cada 10 min;
- senha errada: 10 por e-mail e 30 por IP a cada 15 min (só as falhas contam);
- verificação de código: 30 por IP a cada 10 min (além das 5 por código);
- código errado: 10 por e-mail (e perfil) a cada 15 min. Não zera quando um
  código novo é emitido, então reemitir não dá novas chances de chutar.

Passou do limite: 429 ``AUTH_LIMITE_EXCEDIDO`` com ``Retry-After``.
"""

from __future__ import annotations

from app.auth.erros import limite_excedido
from app.core.limite_taxa import LimiteDeTaxa

DEZ_MINUTOS = 600.0
QUINZE_MINUTOS = 900.0

envio_por_email = LimiteDeTaxa(3, janela_segundos=DEZ_MINUTOS)
envio_por_ip = LimiteDeTaxa(10, janela_segundos=DEZ_MINUTOS)
falha_por_email = LimiteDeTaxa(10, janela_segundos=QUINZE_MINUTOS)
falha_por_ip = LimiteDeTaxa(30, janela_segundos=QUINZE_MINUTOS)
verificacao_por_ip = LimiteDeTaxa(30, janela_segundos=DEZ_MINUTOS)
falha_de_codigo_por_email = LimiteDeTaxa(10, janela_segundos=QUINZE_MINUTOS)

TODOS = (
    envio_por_email,
    envio_por_ip,
    falha_por_email,
    falha_por_ip,
    verificacao_por_ip,
    falha_de_codigo_por_email,
)


def _chave_email(perfil: str, email: str) -> str:
    return f"{perfil}:{email}"


def _barrar_se_cheio(*pares: tuple[LimiteDeTaxa, str]) -> None:
    esperas = [e for limite, chave in pares if (e := limite.espera(chave)) is not None]
    if esperas:
        raise limite_excedido(max(esperas))


def barrar_falhas_de_senha(perfil: str, email: str, ip: str) -> None:
    """Antes de conferir a senha: 429 se o e-mail ou o IP já erraram demais."""
    _barrar_se_cheio((falha_por_email, _chave_email(perfil, email)), (falha_por_ip, ip))


def contar_falha_de_senha(perfil: str, email: str, ip: str) -> None:
    falha_por_email.registrar(_chave_email(perfil, email))
    falha_por_ip.registrar(ip)


def consumir_envio(perfil: str, email: str, ip: str) -> None:
    """Conta um envio de código; 429 (sem contar) se o e-mail ou o IP estão no limite."""
    chave = _chave_email(perfil, email)
    _barrar_se_cheio((envio_por_email, chave), (envio_por_ip, ip))
    envio_por_email.registrar(chave)
    envio_por_ip.registrar(ip)


def consumir_verificacao(ip: str) -> None:
    espera = verificacao_por_ip.registrar(ip)
    if espera is not None:
        raise limite_excedido(espera)


def barrar_falhas_de_codigo(perfil: str, email: str) -> None:
    """Antes de validar o código: 429 se o e-mail já errou códigos demais (sem contar)."""
    _barrar_se_cheio((falha_de_codigo_por_email, _chave_email(perfil, email)))


def contar_falha_de_codigo(perfil: str, email: str) -> None:
    falha_de_codigo_por_email.registrar(_chave_email(perfil, email))


def limpar() -> None:
    for limite in TODOS:
        limite.limpar()
