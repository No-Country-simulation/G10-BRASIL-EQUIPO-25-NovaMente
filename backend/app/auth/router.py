"""Rotas ``/api/v1/auth``: login em duas etapas, primeiro acesso, demo e sessão.

``GET /config`` é sempre público. As demais rotas respondem 404 com o login
desligado (``AUTH_HABILITADA=false``), como se não existissem.

Para não revelar quais e-mails existem:

- no login, e-mail desconhecido, aluno inativo, aluno sem senha e senha
  errada recebem a mesma resposta 401, depois do mesmo trabalho de scrypt;
- ``POST /aluno/senha/codigo`` sempre responde 202 com o mesmo texto, conta
  o limite mesmo para e-mails desconhecidos e envia o e-mail depois da
  resposta (o tempo do SMTP não aparece na resposta).

As rotas são síncronas e rodam no pool de threads (scrypt, SQLite e SMTP).
"""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import codigos, limites
from app.auth.email import EnviadorEmail, ErroEnvioEmail, obter_enviador
from app.auth.erros import (
    codigo_invalido,
    credenciais_invalidas,
    email_indisponivel,
    nao_autenticado,
    nao_encontrado,
    senha_fraca,
)
from app.auth.guardas import aluno_ativo_da_sessao, auth_ligada
from app.auth.schemas import (
    CodigoEnviado,
    ConfigAuth,
    DemoInput,
    LoginInput,
    SenhaCodigoInput,
    SenhaDefinirInput,
    SessaoAluno,
    SessaoEmpresa,
    VerificarInput,
)
from app.auth.senhas import gerar_hash, mensagem_da_politica, verificar_fantasma, verificar_senha
from app.auth.sessao import abrir_sessao, encerrar_sessao, sessao_da_requisicao
from app.core.cliente import ip_do_cliente
from app.core.config import settings
from app.core.db import get_db
from app.models.db import AlunoDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_DEMO_EMPRESA = "demo@novamente.app"
MSG_CODIGO_ENVIADO = "Enviamos um código de 6 dígitos para o seu e-mail."
MSG_CODIGO_SE_CADASTRADO = "Se o e-mail estiver cadastrado, enviamos um código de 6 dígitos."

_LIGADA = [Depends(auth_ligada)]
_RESPOSTAS_LOGIN = {
    401: {"description": "CREDENCIAIS_INVALIDAS (a mesma para e-mail e senha)."},
    404: {"description": "Login desligado."},
    429: {"description": "AUTH_LIMITE_EXCEDIDO, com Retry-After."},
    503: {"description": "EMAIL_INDISPONIVEL."},
}
_RESPOSTAS_VERIFICAR = {
    401: {"description": "CODIGO_INVALIDO (errado, vencido ou já usado)."},
    404: {"description": "Login desligado."},
    429: {"description": "AUTH_LIMITE_EXCEDIDO, com Retry-After."},
}


def _codigo_enviado(mensagem: str = MSG_CODIGO_ENVIADO) -> CodigoEnviado:
    return CodigoEnviado(mensagem=mensagem, expira_em_segundos=codigos.VALIDADE_SEGUNDOS)


def _iguais(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _aluno_por_email(db: Session, email: str) -> AlunoDB | None:
    return db.scalars(select(AlunoDB).where(AlunoDB.email == email)).first()


def _aluno_ativo_por_email(db: Session, email: str) -> AlunoDB | None:
    aluno = _aluno_por_email(db, email)
    return aluno if aluno is not None and aluno.status == "ativo" else None


def _enviar_ou_503(enviador: EnviadorEmail, destinatario: str, codigo: str) -> None:
    try:
        enviador.enviar_codigo(destinatario, codigo)
    except ErroEnvioEmail:
        raise email_indisponivel() from None


def _demo(valor: bool) -> bool | None:
    return True if valor else None


# ── Configuração e sessão ─────────────────────────────────────────────────────


@router.get("/config", response_model=ConfigAuth, summary="Login e demonstração ligados?")
def config() -> ConfigAuth:
    return ConfigAuth(auth_habilitada=settings.auth_habilitada, demo_habilitado=settings.demo_habilitado)


@router.get(
    "/eu",
    response_model=SessaoEmpresa | SessaoAluno,
    response_model_exclude_none=True,
    dependencies=_LIGADA,
    responses={401: {"description": "NAO_AUTENTICADO."}},
    summary="Quem está na sessão",
)
def eu(request: Request, db: Session = Depends(get_db)) -> SessaoEmpresa | SessaoAluno:
    sessao = sessao_da_requisicao(request)
    if sessao is None:
        raise nao_autenticado()
    if sessao.tipo == "empresa":
        return SessaoEmpresa(email=sessao.sub, demo=_demo(sessao.demo))
    aluno = aluno_ativo_da_sessao(db, sessao)
    return SessaoAluno(aluno_id=aluno.aluno_id, nome=aluno.nome, demo=_demo(sessao.demo))


@router.post("/sair", status_code=204, dependencies=_LIGADA, summary="Encerra a sessão")
def sair() -> Response:
    resposta = Response(status_code=204)
    encerrar_sessao(resposta)
    return resposta


# ── Empresa ───────────────────────────────────────────────────────────────────


@router.post(
    "/empresa/login", status_code=202, response_model=CodigoEnviado,
    dependencies=_LIGADA, responses=_RESPOSTAS_LOGIN, summary="Etapa 1 da empresa: e-mail e senha",
)
def login_empresa(
    corpo: LoginInput,
    request: Request,
    db: Session = Depends(get_db),
    enviador: EnviadorEmail = Depends(obter_enviador),
) -> CodigoEnviado:
    email = codigos.normalizar_email(corpo.email)
    ip = ip_do_cliente(request)
    limites.barrar_falhas_de_senha("empresa", email, ip)
    # As duas conferências sempre rodam: o tempo não diz qual delas falhou.
    email_certo = _iguais(email, settings.empresa_email)
    senha_certa = verificar_senha(corpo.senha, settings.empresa_senha_hash.get_secret_value().strip())
    if not (email_certo and senha_certa):
        limites.contar_falha_de_senha("empresa", email, ip)
        raise credenciais_invalidas()
    limites.consumir_envio("empresa", email, ip)
    codigo = codigos.emitir(db, "empresa", "login", email)
    _enviar_ou_503(enviador, settings.empresa_email, codigo)
    return _codigo_enviado()


@router.post(
    "/empresa/verificar", response_model=SessaoEmpresa, response_model_exclude_none=True,
    dependencies=_LIGADA, responses=_RESPOSTAS_VERIFICAR, summary="Etapa 2 da empresa: código",
)
def verificar_empresa(
    corpo: VerificarInput, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessaoEmpresa:
    limites.consumir_verificacao(ip_do_cliente(request))
    email = codigos.normalizar_email(corpo.email)
    limites.barrar_falhas_de_codigo("empresa", email)
    valido = codigos.validar(db, "empresa", "login", email, corpo.codigo.strip())
    if not (valido and _iguais(email, settings.empresa_email)):
        limites.contar_falha_de_codigo("empresa", email)
        raise codigo_invalido()
    abrir_sessao(response, "empresa", settings.empresa_email)
    return SessaoEmpresa(email=settings.empresa_email)


# ── Aluno ─────────────────────────────────────────────────────────────────────


@router.post(
    "/aluno/login", status_code=202, response_model=CodigoEnviado,
    dependencies=_LIGADA, responses=_RESPOSTAS_LOGIN, summary="Etapa 1 do aluno: e-mail e senha",
)
def login_aluno(
    corpo: LoginInput,
    request: Request,
    db: Session = Depends(get_db),
    enviador: EnviadorEmail = Depends(obter_enviador),
) -> CodigoEnviado:
    email = codigos.normalizar_email(corpo.email)
    ip = ip_do_cliente(request)
    limites.barrar_falhas_de_senha("aluno", email, ip)
    aluno = _aluno_ativo_por_email(db, email)
    if aluno is not None and aluno.senha_hash:
        senha_certa = verificar_senha(corpo.senha, aluno.senha_hash)
    else:
        senha_certa = verificar_fantasma(corpo.senha)
    if aluno is None or not senha_certa:
        limites.contar_falha_de_senha("aluno", email, ip)
        raise credenciais_invalidas()
    limites.consumir_envio("aluno", email, ip)
    codigo = codigos.emitir(db, "aluno", "login", email)
    _enviar_ou_503(enviador, aluno.email, codigo)
    return _codigo_enviado()


@router.post(
    "/aluno/verificar", response_model=SessaoAluno, response_model_exclude_none=True,
    dependencies=_LIGADA, responses=_RESPOSTAS_VERIFICAR, summary="Etapa 2 do aluno: código",
)
def verificar_aluno(
    corpo: VerificarInput, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessaoAluno:
    limites.consumir_verificacao(ip_do_cliente(request))
    email = codigos.normalizar_email(corpo.email)
    limites.barrar_falhas_de_codigo("aluno", email)
    valido = codigos.validar(db, "aluno", "login", email, corpo.codigo.strip())
    aluno = _aluno_ativo_por_email(db, email) if valido else None
    if aluno is None:  # código recusado, ou aluno desativado entre a senha e o código
        limites.contar_falha_de_codigo("aluno", email)
        raise codigo_invalido()
    abrir_sessao(response, "aluno", aluno.aluno_id, nome=aluno.nome)
    return SessaoAluno(aluno_id=aluno.aluno_id, nome=aluno.nome)


def _enviar_sem_falhar(enviador: EnviadorEmail, destinatario: str, codigo: str) -> None:
    """Envio depois da resposta: a falha só vai para o log (sem o código)."""
    try:
        enviador.enviar_codigo(destinatario, codigo)
    except Exception as exc:  # noqa: BLE001 - nada pode sair daqui
        logger.error("Primeiro acesso: falha ao enviar o código (%s).", type(exc).__name__)


@router.post(
    "/aluno/senha/codigo", status_code=202, response_model=CodigoEnviado, dependencies=_LIGADA,
    responses={429: {"description": "AUTH_LIMITE_EXCEDIDO, com Retry-After."}},
    summary="Primeiro acesso ou esqueci a senha: envia um código, se o e-mail existir",
)
def codigo_de_senha(
    corpo: SenhaCodigoInput,
    request: Request,
    tarefas: BackgroundTasks,
    db: Session = Depends(get_db),
    enviador: EnviadorEmail = Depends(obter_enviador),
) -> CodigoEnviado:
    email = codigos.normalizar_email(corpo.email)
    # Conta antes de saber se o aluno existe: o limite também não revela nada.
    limites.consumir_envio("aluno", email, ip_do_cliente(request))
    aluno = _aluno_ativo_por_email(db, email)
    if aluno is not None:
        codigo = codigos.emitir(db, "aluno", "senha", email)
        tarefas.add_task(_enviar_sem_falhar, enviador, aluno.email, codigo)
    return _codigo_enviado(MSG_CODIGO_SE_CADASTRADO)


@router.post(
    "/aluno/senha/definir", response_model=SessaoAluno, response_model_exclude_none=True,
    dependencies=_LIGADA,
    responses={
        401: {"description": "CODIGO_INVALIDO."},
        422: {"description": "SENHA_FRACA (o código não é consumido) ou VALIDACAO."},
        429: {"description": "AUTH_LIMITE_EXCEDIDO, com Retry-After."},
    },
    summary="Cria ou troca a senha do aluno com o código e já abre a sessão",
)
def definir_senha(
    corpo: SenhaDefinirInput, request: Request, response: Response, db: Session = Depends(get_db)
) -> SessaoAluno:
    problema = mensagem_da_politica(corpo.senha)
    if problema:
        raise senha_fraca(problema)
    limites.consumir_verificacao(ip_do_cliente(request))
    email = codigos.normalizar_email(corpo.email)
    limites.barrar_falhas_de_codigo("aluno", email)
    valido = codigos.validar(db, "aluno", "senha", email, corpo.codigo.strip())
    aluno = _aluno_ativo_por_email(db, email) if valido else None
    if aluno is None:
        limites.contar_falha_de_codigo("aluno", email)
        raise codigo_invalido()
    aluno.senha_hash = gerar_hash(corpo.senha)
    aluno.atualizado_em = datetime.now(timezone.utc).isoformat()
    db.commit()
    codigos.invalidar_pendentes(db, "aluno", email)
    abrir_sessao(response, "aluno", aluno.aluno_id, nome=aluno.nome)
    return SessaoAluno(aluno_id=aluno.aluno_id, nome=aluno.nome)


# ── Demonstração ──────────────────────────────────────────────────────────────


@router.post(
    "/demo", response_model=SessaoEmpresa | SessaoAluno, response_model_exclude_none=True,
    dependencies=_LIGADA,
    responses={404: {"description": "Demonstração desligada, ou nenhum aluno ativo (ALUNO_NAO_ENCONTRADO)."}},
    summary="Sessão de demonstração (2 h), sem código",
)
def demo(corpo: DemoInput, response: Response, db: Session = Depends(get_db)) -> SessaoEmpresa | SessaoAluno:
    if not settings.demo_habilitado:
        raise nao_encontrado()
    if corpo.perfil == "empresa":
        abrir_sessao(response, "empresa", EMAIL_DEMO_EMPRESA, demo=True)
        return SessaoEmpresa(email=EMAIL_DEMO_EMPRESA, demo=True)
    aluno = db.scalars(
        select(AlunoDB).where(AlunoDB.status == "ativo").order_by(AlunoDB.nome, AlunoDB.aluno_id).limit(1)
    ).first()
    if aluno is None:
        raise HTTPException(
            status_code=404,
            detail={"erro": {"codigo": "ALUNO_NAO_ENCONTRADO", "mensagem": "Nenhum aluno ativo para a demonstração."}},
        )
    abrir_sessao(response, "aluno", aluno.aluno_id, nome=aluno.nome, demo=True)
    return SessaoAluno(aluno_id=aluno.aluno_id, nome=aluno.nome, demo=True)
