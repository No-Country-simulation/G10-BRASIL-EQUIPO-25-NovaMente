"""Corpos e respostas das rotas ``/api/v1/auth``.

Nenhum schema daqui (nem de outro módulo) tem ``senha_hash``. E-mails chegam
como texto livre e são normalizados nas rotas: um e-mail malformado recebe a
mesma resposta de um e-mail desconhecido.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

_EMAIL = Field(min_length=1, max_length=254)
_SENHA = Field(min_length=1, max_length=1024)
_CODIGO = Field(min_length=1, max_length=16)


class ConfigAuth(BaseModel):
    auth_habilitada: bool
    demo_habilitado: bool


class LoginInput(BaseModel):
    email: str = _EMAIL
    senha: str = _SENHA


class VerificarInput(BaseModel):
    email: str = _EMAIL
    codigo: str = _CODIGO


class SenhaCodigoInput(BaseModel):
    email: str = _EMAIL


class SenhaDefinirInput(BaseModel):
    email: str = _EMAIL
    codigo: str = _CODIGO
    senha: str = _SENHA  # a política é conferida na rota (422 SENHA_FRACA)


class DemoInput(BaseModel):
    perfil: Literal["empresa", "aluno"]


class CodigoEnviado(BaseModel):
    mensagem: str
    expira_em_segundos: int


class SessaoEmpresa(BaseModel):
    tipo: Literal["empresa"] = "empresa"
    email: str
    demo: bool | None = None  # só aparece (true) na demonstração


class SessaoAluno(BaseModel):
    tipo: Literal["aluno"] = "aluno"
    aluno_id: str
    nome: str
    demo: bool | None = None
