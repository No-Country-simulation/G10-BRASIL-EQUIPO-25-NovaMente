"""Política e hash de senhas (scrypt da biblioteca padrão).

Formato gravado: ``scrypt$n$r$p$salt_b64$hash_b64`` (base64 padrão, sem
quebras). A comparação é em tempo constante. ``verificar_fantasma`` gasta o
mesmo tempo de uma verificação real, para o caso em que não há hash a
conferir (e-mail desconhecido, aluno sem senha), sem revelar isso pelo tempo.

A política é a mesma do frontend (``frontend/src/lib/senha.ts``): 8 a 128
caracteres, com maiúscula, minúscula, número e símbolo. O tamanho é contado
em unidades UTF-16, como o ``length`` do JavaScript.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import unicodedata
from functools import lru_cache

SENHA_MINIMO = 8
SENHA_MAXIMO = 128

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
HASH_BYTES = 32
_N_MAXIMO = 2**20  # hash fora disso é tratado como inválido (evita custo exagerado)
_PREFIXO = "scrypt"


# ── Política ──────────────────────────────────────────────────────────────────


def _tamanho_utf16(texto: str) -> int:
    return len(texto.encode("utf-16-le")) // 2


def _e_espaco(caractere: str) -> bool:
    # \s do JavaScript inclui o U+FEFF, que o isspace() do Python não considera.
    return caractere.isspace() or caractere == "﻿"


def _e_simbolo(caractere: str) -> bool:
    """Equivale a ``[^\\p{L}\\p{N}\\s]``: nem letra, nem número, nem espaço."""
    categoria = unicodedata.category(caractere)
    return categoria[0] not in ("L", "N") and not _e_espaco(caractere)


def requisitos_faltando(senha: str) -> list[str]:
    """O que falta para a senha atender à política (lista vazia: atende)."""
    faltando: list[str] = []
    tamanho = _tamanho_utf16(senha)
    if tamanho < SENHA_MINIMO:
        faltando.append(f"pelo menos {SENHA_MINIMO} caracteres")
    elif tamanho > SENHA_MAXIMO:
        faltando.append(f"no máximo {SENHA_MAXIMO} caracteres")
    categorias = [unicodedata.category(c) for c in senha]
    if "Lu" not in categorias:
        faltando.append("uma letra maiúscula")
    if "Ll" not in categorias:
        faltando.append("uma letra minúscula")
    if not any(c.startswith("N") for c in categorias):
        faltando.append("um número")
    if not any(_e_simbolo(c) for c in senha):
        faltando.append("um símbolo (por exemplo ! @ # $ %)")
    return faltando


def mensagem_da_politica(senha: str) -> str | None:
    """Mensagem em português com o que falta, ou ``None`` se a senha atende à política."""
    faltando = requisitos_faltando(senha)
    if not faltando:
        return None
    if len(faltando) == 1:
        lista = faltando[0]
    else:
        lista = ", ".join(faltando[:-1]) + " e " + faltando[-1]
    return f"A senha precisa ter {lista}."


# ── Hash ──────────────────────────────────────────────────────────────────────


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def _scrypt(senha: str, salt: bytes, n: int, r: int, p: int, tamanho: int) -> bytes:
    return hashlib.scrypt(
        senha.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=tamanho,
        maxmem=128 * n * r * p + 1024 * 1024,
    )


def gerar_hash(senha: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derivado = _scrypt(senha, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, HASH_BYTES)
    return f"{_PREFIXO}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(derivado)}"


def _decompor(hash_gravado: str) -> tuple[int, int, int, bytes, bytes] | None:
    partes = hash_gravado.split("$")
    if len(partes) != 6 or partes[0] != _PREFIXO:
        return None
    try:
        n, r, p = int(partes[1]), int(partes[2]), int(partes[3])
        salt = base64.b64decode(partes[4], validate=True)
        derivado = base64.b64decode(partes[5], validate=True)
    except (ValueError, binascii.Error):
        return None
    if n < 2 or n > _N_MAXIMO or n & (n - 1) or not (1 <= r <= 32) or not (1 <= p <= 16):
        return None
    if not salt or not derivado:
        return None
    return n, r, p, salt, derivado


def hash_valido(hash_gravado: str) -> bool:
    """True se o texto tem o formato ``scrypt$n$r$p$salt$hash`` com parâmetros aceitáveis."""
    return _decompor(hash_gravado) is not None


@lru_cache(maxsize=1)
def _hash_fantasma() -> str:
    return gerar_hash(secrets.token_urlsafe(16))


def verificar_fantasma(senha: str) -> bool:
    """Faz o trabalho de uma verificação contra um hash descartável. Sempre False."""
    verificar_senha(senha, _hash_fantasma())
    return False


def verificar_senha(senha: str, hash_gravado: str | None) -> bool:
    """Confere a senha com o hash gravado; formato inválido ou ausente vale como errada."""
    partes = _decompor(hash_gravado or "")
    if partes is None:
        return verificar_fantasma(senha)
    n, r, p, salt, esperado = partes
    try:
        calculado = _scrypt(senha, salt, n, r, p, len(esperado))
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(calculado, esperado)
