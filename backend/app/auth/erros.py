"""Respostas de erro do login no envelope ``{"erro": {...}}`` do projeto."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.erros import CodigoErro
from app.core.limite_taxa import segundos_para_cabecalho

MSG_CREDENCIAIS = "E-mail ou senha incorretos."
MSG_CODIGO = "Código inválido ou vencido."


def erro(
    status: int, codigo: CodigoErro, mensagem: str, *,
    headers: dict[str, str] | None = None, campos: dict[str, str] | None = None,
) -> HTTPException:
    corpo: dict = {"codigo": codigo, "mensagem": mensagem}
    if campos:
        corpo["campos"] = campos
    return HTTPException(status_code=status, detail={"erro": corpo}, headers=headers)


def nao_encontrado() -> HTTPException:
    """O mesmo 404 de uma rota que não existe."""
    return HTTPException(status_code=404, detail="Not Found")


def nao_autenticado() -> HTTPException:
    return erro(401, "NAO_AUTENTICADO", "Entre para continuar.")


def acesso_negado() -> HTTPException:
    return erro(403, "ACESSO_NEGADO", "Você não tem acesso a esta área.")


def credenciais_invalidas() -> HTTPException:
    return erro(401, "CREDENCIAIS_INVALIDAS", MSG_CREDENCIAIS)


def codigo_invalido() -> HTTPException:
    return erro(401, "CODIGO_INVALIDO", MSG_CODIGO)


def senha_fraca(mensagem: str) -> HTTPException:
    return erro(422, "SENHA_FRACA", "A senha não atende aos requisitos.", campos={"senha": mensagem})


def limite_excedido(espera: float) -> HTTPException:
    return erro(
        429, "AUTH_LIMITE_EXCEDIDO", "Muitas tentativas. Aguarde um pouco e tente novamente.",
        headers={"Retry-After": str(segundos_para_cabecalho(espera))},
    )


def email_indisponivel() -> HTTPException:
    return erro(
        503, "EMAIL_INDISPONIVEL",
        "Não foi possível enviar o código agora. Tente novamente em instantes.",
    )
