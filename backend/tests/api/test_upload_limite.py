"""Limite de tamanho do upload: recusa antes de ler o arquivo inteiro.

Cobre o middleware (Content-Length e envio em blocos), a leitura em blocos
da rota e o envelope 413 LIMITE_EXCEDIDO, que é o mesmo de antes.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser

from app.core import limite_corpo
from app.core.config import settings
from app.core.limite_corpo import (
    FOLGA_MULTIPART_BYTES,
    TAMANHO_BLOCO,
    ArquivoGrandeDemais,
    LimiteCorpoUploadMiddleware,
    ler_arquivo_limitado,
)
from app.core.limite_geracao import limitador
from app.main import app
from app.models import JobResposta

DADOS = {
    "documento_titulo": "Manual de Teste",
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}
ROTA = "/api/v1/adaptacoes/upload"
MIB = 1024 * 1024


@pytest.fixture(autouse=True)
def _limite_de_geracao_zerado():
    limitador.limpar()
    yield
    limitador.limpar()


@pytest.fixture
def espioes(monkeypatch):
    """Registra chamadas a criar_job e a UploadFile.read (nada chama LLM nem OCI)."""
    estado = {"jobs": [], "leituras": [], "multipart": 0}

    def criar_job_falso(**kw):
        estado["jobs"].append(kw)
        return JobResposta(
            job_id="JOB1",
            status="queued",
            iniciado_em="2026-11-20T12:00:00+00:00",
            atualizado_em="2026-11-20T12:00:00+00:00",
        )

    leitura_real = UploadFile.read

    async def read_espiao(self, size=-1):
        dados = await leitura_real(self, size)
        estado["leituras"].append(len(dados))
        return dados

    parse_real = MultiPartParser.parse

    async def parse_espiao(self):
        estado["multipart"] += 1
        return await parse_real(self)

    monkeypatch.setattr(MultiPartParser, "parse", parse_espiao)
    monkeypatch.setattr("app.api.v1.routers.adaptacoes.criar_job", criar_job_falso)
    monkeypatch.setattr(UploadFile, "read", read_espiao)
    return estado


@pytest.fixture
def cliente_http():
    return TestClient(app)


def _enviar(cliente, conteudo: bytes, nome="doc.txt", tipo="text/plain"):
    return cliente.post(ROTA, files={"arquivo": (nome, conteudo, tipo)}, data=DADOS)


def _texto_valido(tamanho: int) -> bytes:
    base = b"Texto de teste sobre APIs REST e verbos HTTP. "
    return (base * (tamanho // len(base) + 1))[:tamanho]


# ── Pela API ──────────────────────────────────────────────────────────────────


def test_arquivo_acima_do_limite_padrao_devolve_413_sem_ler_o_arquivo(cliente_http, espioes):
    # Maior que 10 MiB mais a folga do multipart: o middleware recusa pelo Content-Length.
    conteudo = _texto_valido(10 * MIB + FOLGA_MULTIPART_BYTES + 4096)
    resp = _enviar(cliente_http, conteudo)

    assert resp.status_code == 413
    erro = resp.json()["erro"]
    assert erro["codigo"] == "LIMITE_EXCEDIDO"
    assert "10 MiB" in erro["mensagem"]
    # O corpo nem foi interpretado: não houve parse do multipart nem leitura do arquivo.
    assert espioes["multipart"] == 0
    assert espioes["leituras"] == []
    assert espioes["jobs"] == []


def test_arquivo_um_byte_acima_do_limite_devolve_413_sem_ler(cliente_http, espioes, monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    resp = _enviar(cliente_http, _texto_valido(1001))

    assert resp.status_code == 413
    assert resp.json()["erro"]["codigo"] == "LIMITE_EXCEDIDO"
    # Passou do middleware (cabe na folga), mas a rota recusa pelo tamanho já
    # conhecido, antes de ler qualquer byte do arquivo.
    assert espioes["multipart"] == 1
    assert sum(espioes["leituras"]) == 0
    assert espioes["jobs"] == []


def test_arquivo_exatamente_no_limite_e_aceito(cliente_http, espioes, monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    resp = _enviar(cliente_http, _texto_valido(1000))

    assert resp.status_code == 202
    assert sum(espioes["leituras"]) == 1000
    assert espioes["jobs"][0]["tamanho_bytes"] == 1000


def test_mensagem_do_413_acompanha_o_limite_configurado(cliente_http, espioes, monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 2 * MIB)
    resp = _enviar(cliente_http, _texto_valido(2 * MIB + 1))
    assert resp.status_code == 413
    assert "2 MiB" in resp.json()["erro"]["mensagem"]


def test_413_do_middleware_sai_com_cors(cliente_http, espioes, monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    origem = settings.cors_origins_lista[0]
    resp = cliente_http.post(
        ROTA,
        files={"arquivo": ("doc.txt", _texto_valido(FOLGA_MULTIPART_BYTES + 5000), "text/plain")},
        data=DADOS,
        headers={"Origin": origem},
    )
    assert resp.status_code == 413
    assert resp.headers["access-control-allow-origin"] == origem


def test_validacoes_anteriores_continuam(cliente_http, espioes):
    resp = _enviar(cliente_http, b"x", nome="a.exe", tipo="application/octet-stream")
    assert resp.status_code == 415
    resp = _enviar(cliente_http, b"curto demais", nome="a.txt")
    assert resp.status_code == 400
    assert resp.json()["erro"]["codigo"] == "DOCUMENTO_ILEGIVEL"


def test_413_nao_consome_o_limite_de_geracoes(cliente_http, espioes, monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    monkeypatch.setattr(settings, "geracao_limite_por_minuto", 1)
    for _ in range(3):
        assert _enviar(cliente_http, _texto_valido(1001)).status_code == 413
    assert _enviar(cliente_http, _texto_valido(500)).status_code == 202


# ── Middleware sozinho (ASGI) ─────────────────────────────────────────────────


def _escopo(content_length: int | None) -> dict:
    cabecalhos = [(b"content-type", b"multipart/form-data; boundary=x")]
    if content_length is not None:
        cabecalhos.append((b"content-length", str(content_length).encode()))
    return {
        "type": "http",
        "method": "POST",
        "path": ROTA,
        "headers": cabecalhos,
        "client": ("127.0.0.1", 1),
    }


def _rodar(app_asgi, escopo, receive):
    enviadas: list[dict] = []

    async def send(mensagem):
        enviadas.append(mensagem)

    asyncio.run(LimiteCorpoUploadMiddleware(app_asgi)(escopo, receive, send))
    return enviadas


def _status_e_corpo(enviadas):
    status = next(m["status"] for m in enviadas if m["type"] == "http.response.start")
    corpo = b"".join(m.get("body", b"") for m in enviadas if m["type"] == "http.response.body")
    return status, json.loads(corpo)


def test_content_length_acima_do_limite_recusa_sem_chamar_receive(monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    chamadas = []

    async def receive():
        chamadas.append(1)
        raise AssertionError("o corpo não deveria ser lido")

    async def app_asgi(scope, receive, send):
        raise AssertionError("o app não deveria ser chamado")

    limite = limite_corpo.limite_do_corpo()
    enviadas = _rodar(app_asgi, _escopo(limite + 1), receive)

    status, corpo = _status_e_corpo(enviadas)
    assert status == 413
    assert corpo["erro"]["codigo"] == "LIMITE_EXCEDIDO"
    assert chamadas == []


def test_content_length_no_limite_passa_para_o_app(monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    chamado = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def app_asgi(scope, receive, send):
        chamado.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    enviadas = _rodar(app_asgi, _escopo(limite_corpo.limite_do_corpo()), receive)
    assert chamado == [True]
    assert enviadas[0]["status"] == 200


def test_envio_em_blocos_para_de_ler_ao_passar_do_limite(monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    total_blocos = 200
    entregues = []

    async def receive():
        entregues.append(1)
        return {
            "type": "http.request",
            "body": b"a" * TAMANHO_BLOCO,
            "more_body": len(entregues) < total_blocos,
        }

    async def app_asgi(scope, receive, send):
        # Imita o Starlette: lê o corpo até o fim; a desconexão vira erro.
        while True:
            mensagem = await receive()
            if mensagem["type"] == "http.disconnect":
                await send({"type": "http.response.start", "status": 400, "headers": []})
                await send({"type": "http.response.body", "body": b'{"detail":"erro"}'})
                return
            if not mensagem.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 202, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    enviadas = _rodar(app_asgi, _escopo(None), receive)

    status, corpo = _status_e_corpo(enviadas)
    assert status == 413
    assert corpo["erro"]["codigo"] == "LIMITE_EXCEDIDO"
    # Sem Content-Length, parou no primeiro bloco acima do limite (e não nos 200 blocos).
    assert len(entregues) <= 2


def test_envio_em_blocos_dentro_do_limite_passa(monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 1000)
    pedacos = [b"a" * 300, b"b" * 300, b""]
    lidos = []

    async def receive():
        corpo = pedacos[len(lidos)]
        lidos.append(corpo)
        return {"type": "http.request", "body": corpo, "more_body": len(lidos) < len(pedacos)}

    async def app_asgi(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        await send({"type": "http.response.start", "status": 202, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    enviadas = _rodar(app_asgi, _escopo(None), receive)
    assert enviadas[0]["status"] == 202


def test_outras_rotas_nao_passam_pelo_limite(monkeypatch):
    monkeypatch.setattr(settings, "arquivo_max_bytes", 10)
    escopo = _escopo(10 * MIB)
    escopo["path"] = "/api/v1/alunos"
    chamado = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def app_asgi(scope, receive, send):
        chamado.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    _rodar(app_asgi, escopo, receive)
    assert chamado == [True]


# ── Leitura em blocos ─────────────────────────────────────────────────────────


class _ArquivoFalso:
    """Arquivo que entrega ``total`` bytes em blocos e registra as leituras."""

    def __init__(self, total: int) -> None:
        self.restante = total
        self.leituras: list[int] = []

    async def read(self, tamanho: int = -1) -> bytes:
        entregue = min(self.restante, tamanho)
        self.restante -= entregue
        self.leituras.append(entregue)
        return b"x" * entregue


def test_leitura_em_blocos_para_ao_passar_do_limite():
    arquivo = _ArquivoFalso(total=50 * TAMANHO_BLOCO)
    limite = TAMANHO_BLOCO + 10

    with pytest.raises(ArquivoGrandeDemais):
        asyncio.run(ler_arquivo_limitado(arquivo, limite))

    # Dois blocos bastam para passar do limite: o resto nunca é lido.
    assert len(arquivo.leituras) == 2
    assert sum(arquivo.leituras) < limite + TAMANHO_BLOCO
    assert arquivo.restante == 48 * TAMANHO_BLOCO


def test_leitura_em_blocos_devolve_o_conteudo_dentro_do_limite():
    arquivo = _ArquivoFalso(total=TAMANHO_BLOCO * 2 + 7)
    conteudo = asyncio.run(ler_arquivo_limitado(arquivo, TAMANHO_BLOCO * 3))
    assert len(conteudo) == TAMANHO_BLOCO * 2 + 7


def test_leitura_no_limite_exato_nao_recusa():
    arquivo = _ArquivoFalso(total=TAMANHO_BLOCO)
    assert len(asyncio.run(ler_arquivo_limitado(arquivo, TAMANHO_BLOCO))) == TAMANHO_BLOCO
