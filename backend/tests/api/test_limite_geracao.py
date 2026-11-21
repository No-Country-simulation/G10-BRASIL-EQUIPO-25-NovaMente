"""Limite de requisições por IP nos endpoints de geração (POST /adaptacoes e /upload).

Nada chama o LLM: ``criar_job`` é trocado por um falso que só devolve um job.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core import limite_geracao
from app.core.config import settings
from app.core.limite_geracao import ip_do_cliente, limitador
from app.main import app
from app.models import JobResposta

CORPO = {
    "documento_titulo": "Manual de Teste",
    "documento_conteudo": "Texto de teste sobre APIs REST. " * 20,
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}
DADOS_UPLOAD = {
    "documento_titulo": "Manual de Teste",
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}
TEXTO_ARQUIVO = ("Texto de teste sobre APIs REST e verbos HTTP. " * 10).encode()


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture
def jobs_criados(monkeypatch):
    """Troca criar_job por um falso e devolve a lista das chamadas."""
    chamadas: list[dict] = []

    def falso(**kw):
        chamadas.append(kw)
        return JobResposta(
            job_id=f"JOB{len(chamadas)}",
            status="queued",
            iniciado_em="2026-11-20T12:00:00+00:00",
            atualizado_em="2026-11-20T12:00:00+00:00",
        )

    monkeypatch.setattr("app.api.v1.routers.adaptacoes.criar_job", falso)
    return chamadas


@pytest.fixture(autouse=True)
def limite_isolado(monkeypatch):
    """Contador zerado a cada teste, relógio falso e limite pequeno."""
    limitador.limpar()
    relogio = _Relogio()
    monkeypatch.setattr(limitador, "relogio", relogio)
    monkeypatch.setattr(settings, "geracao_limite_por_minuto", 2)
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", False)
    yield relogio
    limitador.limpar()


@pytest.fixture
def cliente_http():
    return TestClient(app)


def _texto(cliente, **kw):
    return cliente.post("/api/v1/adaptacoes", json=CORPO, **kw)


def _upload(cliente, **kw):
    arquivos = {"arquivo": ("doc.txt", TEXTO_ARQUIVO, "text/plain")}
    return cliente.post("/api/v1/adaptacoes/upload", files=arquivos, data=DADOS_UPLOAD, **kw)


def test_dentro_do_limite_aceita(cliente_http, jobs_criados):
    assert _texto(cliente_http).status_code == 202
    assert _texto(cliente_http).status_code == 202
    assert len(jobs_criados) == 2


def test_acima_do_limite_devolve_429_com_envelope_e_retry_after(cliente_http, jobs_criados):
    _texto(cliente_http)
    _texto(cliente_http)
    resp = _texto(cliente_http)

    assert resp.status_code == 429
    erro = resp.json()["erro"]
    assert erro["codigo"] == "LIMITE_EXCEDIDO"
    assert erro["mensagem"]
    espera = resp.headers["Retry-After"]
    assert espera.isdigit() and 1 <= int(espera) <= 60
    assert len(jobs_criados) == 2  # a recusada nem chegou na rota


def test_retry_after_e_arredondado_para_cima(cliente_http, jobs_criados, limite_isolado):
    _texto(cliente_http)
    limite_isolado.agora += 10.5
    _texto(cliente_http)
    resp = _texto(cliente_http)
    # a primeira requisição sai da janela em 60 - 10,5 = 49,5 s
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "50"


def test_texto_e_upload_dividem_o_mesmo_limite(cliente_http, jobs_criados):
    assert _texto(cliente_http).status_code == 202
    assert _upload(cliente_http).status_code == 202
    assert _upload(cliente_http).status_code == 429
    assert _texto(cliente_http).status_code == 429


def test_libera_depois_da_janela(cliente_http, jobs_criados, limite_isolado):
    _texto(cliente_http)
    _texto(cliente_http)
    assert _texto(cliente_http).status_code == 429
    limite_isolado.agora += 61
    assert _texto(cliente_http).status_code == 202


def test_requisicao_invalida_nao_consome_o_limite(cliente_http, jobs_criados):
    for _ in range(5):
        assert cliente_http.post("/api/v1/adaptacoes", json={}).status_code == 422
    arquivos = {"arquivo": ("doc.exe", b"x", "application/octet-stream")}
    assert (
        cliente_http.post("/api/v1/adaptacoes/upload", files=arquivos, data=DADOS_UPLOAD).status_code
        == 415
    )
    assert _texto(cliente_http).status_code == 202
    assert _texto(cliente_http).status_code == 202
    assert _texto(cliente_http).status_code == 429


def test_get_nao_conta(cliente_http, jobs_criados):
    for _ in range(5):
        assert cliente_http.get("/api/v1/adaptacoes").status_code == 200
    assert _texto(cliente_http).status_code == 202


def test_barra_final_tambem_conta(cliente_http, jobs_criados):
    # A rota redireciona "/adaptacoes/" para "/adaptacoes" (307); nada escapa da contagem.
    for _ in range(2):
        assert cliente_http.post("/api/v1/adaptacoes/", json=CORPO).status_code == 202
    assert cliente_http.post("/api/v1/adaptacoes/", json=CORPO).status_code == 429


def test_429_sai_com_cabecalhos_de_cors(cliente_http, jobs_criados):
    origem = settings.cors_origins_lista[0]
    _texto(cliente_http)
    _texto(cliente_http)
    resp = _texto(cliente_http, headers={"Origin": origem})

    assert resp.status_code == 429
    assert resp.headers["access-control-allow-origin"] == origem
    assert "retry-after" in resp.headers["access-control-expose-headers"].lower()


# ── IP do cliente ─────────────────────────────────────────────────────────────


def test_x_forwarded_for_e_ignorado_por_padrao(cliente_http, jobs_criados):
    for i in range(2):
        _texto(cliente_http, headers={"X-Forwarded-For": f"10.0.0.{i}"})
    resp = _texto(cliente_http, headers={"X-Forwarded-For": "10.0.0.99"})
    assert resp.status_code == 429  # todos contam como o mesmo cliente


def test_x_forwarded_for_separa_clientes_quando_confiado(
    cliente_http, jobs_criados, monkeypatch
):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", True)
    for _ in range(2):
        assert _texto(cliente_http, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 202
    assert _texto(cliente_http, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    assert _texto(cliente_http, headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 202


def test_entrada_forjada_a_esquerda_do_x_forwarded_for_nao_burla(
    cliente_http, jobs_criados, monkeypatch
):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", True)
    # O proxy confiável acrescenta o IP real por último; o cliente só controla o início.
    for falso in ("1.1.1.1", "2.2.2.2"):
        _texto(cliente_http, headers={"X-Forwarded-For": f"{falso}, 203.0.113.7"})
    resp = _texto(cliente_http, headers={"X-Forwarded-For": "3.3.3.3, 203.0.113.7"})
    assert resp.status_code == 429


def _scope(headers: list[tuple[bytes, bytes]], client=("192.0.2.10", 5000)) -> dict:
    return {"type": "http", "headers": headers, "client": client}


def test_ip_do_cliente_usa_a_conexao_por_padrao(monkeypatch):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", False)
    assert ip_do_cliente(_scope([(b"x-forwarded-for", b"9.9.9.9")])) == "192.0.2.10"


def test_ip_do_cliente_com_x_forwarded_for_invalido_volta_para_a_conexao(monkeypatch):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", True)
    assert ip_do_cliente(_scope([(b"x-forwarded-for", b"nao-e-ip")])) == "192.0.2.10"
    assert ip_do_cliente(_scope([(b"x-forwarded-for", b"")])) == "192.0.2.10"
    assert ip_do_cliente(_scope([])) == "192.0.2.10"


def test_ip_do_cliente_aceita_ipv6(monkeypatch):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", True)
    assert ip_do_cliente(_scope([(b"x-forwarded-for", b"2001:db8::1")])) == "2001:db8::1"


def test_ip_do_cliente_sem_conexao(monkeypatch):
    monkeypatch.setattr(settings, "confiar_x_forwarded_for", False)
    assert ip_do_cliente(_scope([], client=None)) == "desconhecido"


def test_devolver_remove_so_a_ultima_reserva():
    assert limitador.registrar("a") is None
    assert limitador.registrar("a") is None
    assert limitador.registrar("a") is not None  # cheio
    limitador.devolver("a")
    assert limitador.registrar("a") is None
    limitador.devolver("inexistente")  # sem efeito, sem erro


def test_limite_acompanha_a_configuracao(cliente_http, jobs_criados, monkeypatch):
    monkeypatch.setattr(settings, "geracao_limite_por_minuto", 1)
    assert _texto(cliente_http).status_code == 202
    assert _texto(cliente_http).status_code == 429


def test_modulo_exporta_as_rotas_de_geracao():
    assert limite_geracao.ROTAS_GERACAO == {"/api/v1/adaptacoes", "/api/v1/adaptacoes/upload"}
