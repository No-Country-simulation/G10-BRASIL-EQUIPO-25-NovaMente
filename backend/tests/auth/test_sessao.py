"""Cookie de sessão: assinatura, expiração, adulteração e atributos."""

from __future__ import annotations

import base64
import json

import pytest
from fastapi import Response

from app.auth import sessao
from tests.auth.apoio import SEGREDO_TESTE

OUTRO_SEGREDO = "outro-segredo-tambem-com-mais-de-32-caracteres"


@pytest.fixture
def relogio(monkeypatch):
    agora = {"t": 1_800_000_000.0}
    monkeypatch.setattr(sessao, "_relogio", lambda: agora["t"])
    return agora


def _token(tipo="empresa", sub="empresa@exemplo.com", **kw):
    return sessao.criar_token(tipo, sub, segredo=SEGREDO_TESTE, **kw)[0]


def test_token_valido_volta_como_sessao(relogio):
    lido = sessao.ler_token(_token("aluno", "A1", nome="Ana"), segredo=SEGREDO_TESTE)
    assert lido == sessao.Sessao(tipo="aluno", sub="A1", nome="Ana", demo=False, exp=int(relogio["t"]) + 12 * 3600)


@pytest.mark.parametrize(
    "tipo,demo,segundos", [("empresa", False, 8 * 3600), ("aluno", False, 12 * 3600), ("empresa", True, 2 * 3600), ("aluno", True, 2 * 3600)]
)
def test_duracoes(relogio, tipo, demo, segundos):
    token, duracao = sessao.criar_token(tipo, "x", demo=demo, segredo=SEGREDO_TESTE)
    assert duracao == segundos
    relogio["t"] += segundos - 1
    assert sessao.ler_token(token, segredo=SEGREDO_TESTE) is not None
    relogio["t"] += 1
    assert sessao.ler_token(token, segredo=SEGREDO_TESTE) is None


def test_payload_em_base64url_com_os_campos_combinados(relogio):
    conteudo = _token("empresa", "demo@novamente.app", demo=True).split(".")[0]
    payload = json.loads(base64.urlsafe_b64decode(conteudo + "=" * (-len(conteudo) % 4)))
    assert payload == {"t": "empresa", "sub": "demo@novamente.app", "demo": True, "exp": int(relogio["t"]) + 7200}
    assert "=" not in conteudo


def _forjar(payload: dict, assinatura_de: str) -> str:
    conteudo = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{conteudo}.{assinatura_de.split('.')[1]}"


def test_adulteracao_invalida(relogio):
    original = _token("aluno", "A1")
    # Troca o aluno mantendo a assinatura antiga.
    forjado = _forjar({"t": "aluno", "sub": "A2", "exp": int(relogio["t"]) + 999}, original)
    assert sessao.ler_token(forjado, segredo=SEGREDO_TESTE) is None
    # Promove o aluno a empresa.
    forjado = _forjar({"t": "empresa", "sub": "A1", "exp": int(relogio["t"]) + 999}, original)
    assert sessao.ler_token(forjado, segredo=SEGREDO_TESTE) is None
    # Outro segredo.
    assert sessao.ler_token(original, segredo=OUTRO_SEGREDO) is None


@pytest.mark.parametrize("token", [None, "", "sem-ponto", "a.b.c", "abc.def", "éé.éé"])
def test_tokens_malformados(relogio, token):
    assert sessao.ler_token(token, segredo=SEGREDO_TESTE) is None


def test_payload_assinado_mas_invalido(relogio):
    def assinado(payload) -> str:
        conteudo = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        return f"{conteudo}.{sessao._assinar(conteudo, SEGREDO_TESTE)}"

    exp = int(relogio["t"]) + 60
    assert sessao.ler_token(assinado({"t": "admin", "sub": "x", "exp": exp}), segredo=SEGREDO_TESTE) is None
    assert sessao.ler_token(assinado({"t": "aluno", "sub": "", "exp": exp}), segredo=SEGREDO_TESTE) is None
    assert sessao.ler_token(assinado({"t": "aluno", "sub": "x", "exp": "amanhã"}), segredo=SEGREDO_TESTE) is None
    assert sessao.ler_token(assinado(["lista"]), segredo=SEGREDO_TESTE) is None
    assert sessao.ler_token(assinado({"t": "aluno", "sub": "x", "exp": exp}), segredo=SEGREDO_TESTE) is not None


def test_sem_segredo_nao_ha_sessao(relogio):
    assert sessao.ler_token(_token(), segredo="") is None


@pytest.mark.parametrize("seguro", [False, True])
def test_atributos_do_cookie(auth_ligada, monkeypatch, seguro):
    monkeypatch.setattr(auth_ligada, "sessao_cookie_seguro", seguro)
    resposta = Response()
    sessao.abrir_sessao(resposta, "empresa", "empresa@exemplo.com")
    cabecalho = resposta.headers["set-cookie"]
    assert cabecalho.startswith("nm_sessao=")
    assert "HttpOnly" in cabecalho and "SameSite=lax" in cabecalho and "Path=/" in cabecalho
    assert "Max-Age=28800" in cabecalho
    assert "Domain" not in cabecalho
    assert ("Secure" in cabecalho) is seguro


def test_encerrar_expira_o_cookie(auth_ligada):
    resposta = Response()
    sessao.encerrar_sessao(resposta)
    cabecalho = resposta.headers["set-cookie"]
    assert cabecalho.startswith('nm_sessao=""') and "Max-Age=0" in cabecalho and "Domain" not in cabecalho
