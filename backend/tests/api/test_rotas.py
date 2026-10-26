"""Testes de integração da API — verificam os contratos da spec do frontend."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────


def test_health_retorna_200():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "versao" in data
    assert data["oci"] in ("ok", "indisponivel")
    assert data["llm"] in ("ok", "indisponivel")
    assert "verificado_em" in data


# ── OCI Status ────────────────────────────────────────────────────────────────


def test_oci_status_retorna_200():
    resp = client.get("/api/v1/oci/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "configurado" in data
    assert "verificado_em" in data


# ── Job não encontrado ────────────────────────────────────────────────────────


def test_job_nao_encontrado():
    resp = client.get("/api/v1/jobs/JOB_INEXISTENTE_000")
    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "JOB_NAO_ENCONTRADO"


# ── Adaptação não encontrada ──────────────────────────────────────────────────


def test_adaptacao_nao_encontrada():
    resp = client.get("/api/v1/adaptacoes/ID_INEXISTENTE")
    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ADAPTACAO_NAO_ENCONTRADA"


# ── Validação de entrada (POST /adaptacoes) ───────────────────────────────────


def test_criar_adaptacao_validacao_campos_obrigatorios():
    resp = client.post("/api/v1/adaptacoes", json={})
    assert resp.status_code == 422


def test_criar_adaptacao_conteudo_curto():
    resp = client.post(
        "/api/v1/adaptacoes",
        json={
            "documento_titulo": "Teste",
            "documento_conteudo": "curto",  # < 200 chars
            "perfil_destinatario": "Iniciante",
            "formato_saida": "Flashcards",
            "nicho_setor": "Geral",
            "nivel_detalhe": "Didatico",
        },
    )
    assert resp.status_code == 422


# ── Histórico — lista vazia por padrão ───────────────────────────────────────


def test_listar_adaptacoes_vazio():
    resp = client.get("/api/v1/adaptacoes")
    assert resp.status_code == 200
    data = resp.json()
    assert "itens" in data
    assert "total" in data
    assert "pagina" in data


# ── Exportação de formato desconhecido ───────────────────────────────────────


def test_exportar_formato_desconhecido():
    # Primeiro precisaria de um pacote real; aqui só testamos o 404 pelo ID
    resp = client.get("/api/v1/adaptacoes/NAO_EXISTE/exportacao?formato=xml")
    # Pode ser 400 (formato) ou 404 (id) — ambos são erros esperados
    assert resp.status_code in (400, 404)


# ── Parâmetros inválidos de listagem ─────────────────────────────────────────


def test_listar_adaptacoes_pagina_invalida():
    resp = client.get("/api/v1/adaptacoes?pagina=-1")
    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"


def test_listar_adaptacoes_tamanho_invalido():
    resp = client.get("/api/v1/adaptacoes?tamanho_pagina=100")
    assert resp.status_code == 422
