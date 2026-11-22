"""CORS: origem permitida e negada (preflight e requisição simples) e CORS_ORIGINS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

ORIGEM_OK = "http://localhost:3000"
ORIGEM_NEGADA = "https://site-malicioso.exemplo"
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def cliente_http():
    return TestClient(app)


def _preflight(cliente, origem, metodo="POST", cabecalhos="content-type"):
    return cliente.options(
        "/api/v1/adaptacoes",
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": metodo,
            "Access-Control-Request-Headers": cabecalhos,
        },
    )


def test_padrao_permite_so_o_frontend_local():
    assert settings.cors_origins_lista == [ORIGEM_OK]


def test_preflight_de_origem_permitida(cliente_http):
    resp = _preflight(cliente_http, ORIGEM_OK)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_OK
    assert resp.headers["access-control-allow-credentials"] == "true"


def test_preflight_de_origem_negada(cliente_http):
    resp = _preflight(cliente_http, ORIGEM_NEGADA)
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_requisicao_simples_de_origem_permitida(cliente_http):
    resp = cliente_http.get("/api/v1/health", headers={"Origin": ORIGEM_OK})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGEM_OK


def test_requisicao_simples_de_origem_negada(cliente_http):
    resp = cliente_http.get("/api/v1/health", headers={"Origin": ORIGEM_NEGADA})
    # O servidor responde, mas sem o cabeçalho o navegador bloqueia a leitura.
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.parametrize("metodo", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_preflight_aceita_os_metodos_usados_pela_api(cliente_http, metodo):
    assert _preflight(cliente_http, ORIGEM_OK, metodo=metodo).status_code == 200


def test_preflight_recusa_metodo_fora_da_lista(cliente_http):
    resp = _preflight(cliente_http, ORIGEM_OK, metodo="TRACE")
    assert resp.status_code == 400


def test_preflight_aceita_cabecalhos_necessarios(cliente_http):
    resp = _preflight(cliente_http, ORIGEM_OK, cabecalhos="content-type, authorization, x-api-key")
    assert resp.status_code == 200
    permitidos = resp.headers["access-control-allow-headers"].lower()
    assert "authorization" in permitidos and "x-api-key" in permitidos


def test_preflight_recusa_cabecalho_fora_da_lista(cliente_http):
    resp = _preflight(cliente_http, ORIGEM_OK, cabecalhos="x-qualquer-coisa")
    assert resp.status_code == 400


def test_nao_ha_curinga_na_configuracao_do_middleware():
    from starlette.middleware.cors import CORSMiddleware

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    assert "*" not in cors.kwargs["allow_origins"]
    assert "*" not in cors.kwargs["allow_methods"]
    assert "*" not in cors.kwargs["allow_headers"]


def test_cors_e_o_middleware_mais_externo():
    # O CORS precisa embrulhar os limites para que o 413 e o 429 levem os cabeçalhos.
    from starlette.middleware.cors import CORSMiddleware

    assert app.user_middleware[0].cls is CORSMiddleware


# ── CORS_ORIGINS lida do ambiente (processo novo, com a aplicação real) ───────

_SCRIPT = """
import json
from fastapi.testclient import TestClient
from app.main import app

cliente = TestClient(app)
saida = {}
for origem in ("https://app.exemplo.com", "https://painel.exemplo.com:8443",
               "http://localhost:3000", "https://outra.exemplo.com"):
    resp = cliente.get("/api/v1/health", headers={"Origin": origem})
    saida[origem] = resp.headers.get("access-control-allow-origin")
print(json.dumps(saida))
"""


def _rodar_com_cors(valor: str, tmp_path) -> subprocess.CompletedProcess:
    ambiente = {
        **os.environ,
        "CORS_ORIGINS": valor,
        "DATABASE_URL": f"sqlite:///{tmp_path}/cors.db",
        "DB_PATH": str(tmp_path / "jobs.db"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=BACKEND,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cors_origins_do_ambiente_vale_na_aplicacao(tmp_path):
    resultado = _rodar_com_cors(
        " https://app.exemplo.com ,, https://painel.exemplo.com:8443 ,", tmp_path
    )
    assert resultado.returncode == 0, resultado.stderr
    saida = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert saida["https://app.exemplo.com"] == "https://app.exemplo.com"
    assert saida["https://painel.exemplo.com:8443"] == "https://painel.exemplo.com:8443"
    # O padrão deixa de valer quando a variável é definida.
    assert saida["http://localhost:3000"] is None
    assert saida["https://outra.exemplo.com"] is None


def test_aplicacao_nao_sobe_com_curinga_no_cors(tmp_path):
    resultado = _rodar_com_cors("*", tmp_path)
    assert resultado.returncode != 0
    assert "CORS_ORIGINS" in resultado.stderr
    assert "credenciais" in resultado.stderr
