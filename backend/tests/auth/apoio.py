"""Constantes e funções de apoio dos testes do login."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.auth.email import ErroEnvioEmail
from app.auth.senhas import gerar_hash

SEGREDO_TESTE = "segredo-de-teste-com-mais-de-32-caracteres"
EMPRESA_EMAIL = "empresa@exemplo.com"
SENHA_EMPRESA = "Empresa@2026"
SENHA_ALUNO = "Aluno#2026x"

# Um hash por senha na sessão de testes: o scrypt é lento de propósito.
_HASHES: dict[str, str] = {}


def hash_de(senha: str) -> str:
    if senha not in _HASHES:
        _HASHES[senha] = gerar_hash(senha)
    return _HASHES[senha]


@dataclass
class EnviadorFalso:
    enviados: list[tuple[str, str]] = field(default_factory=list)
    falhar: bool = False

    def enviar_codigo(self, destinatario: str, codigo: str) -> None:
        if self.falhar:
            raise ErroEnvioEmail("Falha no envio do e-mail.")
        self.enviados.append((destinatario, codigo))

    @property
    def ultimo_codigo(self) -> str:
        return self.enviados[-1][1]


def entrar_empresa(cliente, enviador) -> None:
    r = cliente.post("/api/v1/auth/empresa/login", json={"email": EMPRESA_EMAIL, "senha": SENHA_EMPRESA})
    assert r.status_code == 202, r.text
    r = cliente.post(
        "/api/v1/auth/empresa/verificar", json={"email": EMPRESA_EMAIL, "codigo": enviador.ultimo_codigo}
    )
    assert r.status_code == 200, r.text


def entrar_aluno(cliente, enviador, email: str, senha: str = SENHA_ALUNO) -> None:
    r = cliente.post("/api/v1/auth/aluno/login", json={"email": email, "senha": senha})
    assert r.status_code == 202, r.text
    r = cliente.post("/api/v1/auth/aluno/verificar", json={"email": email, "codigo": enviador.ultimo_codigo})
    assert r.status_code == 200, r.text
