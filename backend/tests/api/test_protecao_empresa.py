"""Testes da chave de API das rotas da empresa (cabeçalho X-API-Key)."""

from __future__ import annotations

import logging

import pytest
from fastapi.routing import APIRoute

from app.api.v1.routers import adaptacoes as adaptacoes_router
from app.core import seguranca
from app.core.config import settings
from app.main import app
from app.models import JobResposta

BASE = "/api/v1"
CHAVE = "chave-de-teste-empresa"
CHAVE_ERRADA = "chave-errada-de-teste"

_CORPO_ADAPTACAO = {
    "documento_titulo": "Manual de Redes",
    "documento_conteudo": "x" * 300,
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}

# (método, caminho, argumentos do request) de cada rota protegida.
ROTAS_PROTEGIDAS = [
    ("GET", f"{BASE}/alunos", {}),
    ("POST", f"{BASE}/alunos", {"json": {"nome": "Ana Silva", "email": "ana@exemplo.com"}}),
    ("GET", f"{BASE}/alunos/ID", {}),
    ("PATCH", f"{BASE}/alunos/ID", {"json": {"nome": "Ana Souza"}}),
    ("DELETE", f"{BASE}/alunos/ID", {}),
    ("GET", f"{BASE}/alunos/ID/materiais", {}),
    ("PUT", f"{BASE}/alunos/ID/materiais", {"json": {"material_ids": []}}),
    ("POST", f"{BASE}/alunos/ID/materiais/MAT", {}),
    ("DELETE", f"{BASE}/alunos/ID/materiais/MAT", {}),
    ("GET", f"{BASE}/materiais", {}),
    ("GET", f"{BASE}/materiais/MAT", {}),
    ("PATCH", f"{BASE}/materiais/MAT", {"json": {"titulo": "Novo título"}}),
    ("DELETE", f"{BASE}/materiais/MAT", {}),
    ("POST", f"{BASE}/adaptacoes", {"json": _CORPO_ADAPTACAO}),
    (
        "POST",
        f"{BASE}/adaptacoes/upload",
        {
            "files": {"arquivo": ("a.txt", b"conteudo", "text/plain")},
            "data": {
                "documento_titulo": "Manual de Redes",
                "perfil_destinatario": "Iniciante",
                "formato_saida": "Flashcards",
                "nicho_setor": "Geral",
                "nivel_detalhe": "Didatico",
            },
        },
    ),
    ("DELETE", f"{BASE}/jobs/JOB", {}),
]

# Rotas que continuam abertas mesmo com a chave configurada.
ROTAS_ABERTAS = [
    ("GET", f"{BASE}/health"),
    ("GET", f"{BASE}/oci/status"),
    ("GET", f"{BASE}/aluno/identificacao"),
    ("GET", f"{BASE}/aluno/materiais"),
    ("GET", f"{BASE}/aluno/materiais/MAT"),
    ("GET", f"{BASE}/adaptacoes"),
    ("GET", f"{BASE}/adaptacoes/ID"),
    ("GET", f"{BASE}/jobs/JOB"),
    ("GET", "/docs"),
    ("GET", "/redoc"),
    ("GET", "/openapi.json"),
]


def _id(rota) -> str:
    metodo, caminho, _ = rota
    return f"{metodo} {caminho}"


@pytest.fixture(autouse=True)
def _estado_limpo(monkeypatch):
    """Cada teste começa sem chave configurada e com o aviso único rearmado."""
    monkeypatch.setattr(settings, "api_key_empresa", "")
    seguranca._reiniciar_aviso()
    yield
    seguranca._reiniciar_aviso()


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setattr(settings, "api_key_empresa", CHAVE)
    return CHAVE


def _chamar(cliente, metodo, caminho, args, chave=None):
    cabecalhos = {"X-API-Key": chave} if chave is not None else {}
    return cliente.request(metodo, caminho, headers=cabecalhos, **args)


def _mensagens_do_log(caplog) -> str:
    return "\n".join(r.getMessage() for r in caplog.records)


def _aviso_emitido(caplog) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.name == "app.core.seguranca" and r.levelno == logging.WARNING
    ]


# ── Com a chave configurada ───────────────────────────────────────────────────


@pytest.mark.parametrize("rota", ROTAS_PROTEGIDAS, ids=_id)
def test_sem_chave_responde_401_com_envelope(cliente, com_chave, rota):
    metodo, caminho, args = rota
    resp = _chamar(cliente, metodo, caminho, args)

    assert resp.status_code == 401
    erro = resp.json()["erro"]
    assert set(resp.json()) == {"erro"}
    assert erro["codigo"] == "NAO_AUTORIZADO"
    assert "X-API-Key" in erro["mensagem"]
    assert CHAVE not in resp.text


@pytest.mark.parametrize("rota", ROTAS_PROTEGIDAS, ids=_id)
def test_chave_errada_responde_401_com_envelope(cliente, com_chave, rota):
    metodo, caminho, args = rota
    resp = _chamar(cliente, metodo, caminho, args, chave=CHAVE_ERRADA)

    assert resp.status_code == 401
    assert resp.json()["erro"]["codigo"] == "NAO_AUTORIZADO"
    assert CHAVE not in resp.text
    assert CHAVE_ERRADA not in resp.text


def test_resposta_igual_para_chave_ausente_e_errada(cliente, com_chave):
    ausente = cliente.get(f"{BASE}/alunos")
    errada = cliente.get(f"{BASE}/alunos", headers={"X-API-Key": CHAVE_ERRADA})
    vazia = cliente.get(f"{BASE}/alunos", headers={"X-API-Key": ""})

    assert ausente.status_code == errada.status_code == vazia.status_code == 401
    assert ausente.json() == errada.json() == vazia.json()


def test_chave_com_prefixo_ou_sufixo_extra_e_recusada(cliente, com_chave):
    for enviada in (CHAVE + "x", CHAVE[:-1], f" {CHAVE}", CHAVE.upper()):
        resp = cliente.get(f"{BASE}/alunos", headers={"X-API-Key": enviada})
        assert resp.status_code == 401, enviada


def test_chave_nao_ascii_e_recusada_sem_erro_interno(cliente, com_chave):
    resp = cliente.get(
        f"{BASE}/alunos", headers={"X-API-Key": "chave-é-ã".encode("latin-1")}
    )
    assert resp.status_code == 401
    assert resp.json()["erro"]["codigo"] == "NAO_AUTORIZADO"


def test_chave_certa_nas_rotas_de_alunos(cliente, com_chave):
    h = {"X-API-Key": com_chave}

    criado = cliente.post(
        f"{BASE}/alunos", headers=h, json={"nome": "Ana Silva", "email": "ana@exemplo.com"}
    )
    assert criado.status_code == 201
    aluno_id = criado.json()["aluno_id"]

    lista = cliente.get(f"{BASE}/alunos", headers=h)
    assert lista.status_code == 200
    assert lista.json()["total"] == 1

    assert cliente.get(f"{BASE}/alunos/{aluno_id}", headers=h).status_code == 200
    editado = cliente.patch(
        f"{BASE}/alunos/{aluno_id}", headers=h, json={"nome": "Ana Souza"}
    )
    assert editado.status_code == 200
    assert editado.json()["nome"] == "Ana Souza"
    assert cliente.get(f"{BASE}/alunos/{aluno_id}/materiais", headers=h).status_code == 200
    assert cliente.delete(f"{BASE}/alunos/{aluno_id}", headers=h).status_code == 204


def test_chave_certa_nas_rotas_de_materiais_e_vinculos(
    cliente, com_chave, semear_aluno, semear_material
):
    h = {"X-API-Key": com_chave}
    aluno_id = semear_aluno()
    material_id = semear_material()

    assert cliente.get(f"{BASE}/materiais", headers=h).status_code == 200
    assert cliente.get(f"{BASE}/materiais/{material_id}", headers=h).status_code == 200
    assert (
        cliente.patch(
            f"{BASE}/materiais/{material_id}", headers=h, json={"titulo": "Novo título"}
        ).status_code
        == 200
    )

    vinculo = cliente.post(f"{BASE}/alunos/{aluno_id}/materiais/{material_id}", headers=h)
    assert vinculo.status_code == 201
    assert (
        cliente.put(
            f"{BASE}/alunos/{aluno_id}/materiais",
            headers=h,
            json={"material_ids": [material_id]},
        ).status_code
        == 200
    )
    assert (
        cliente.delete(
            f"{BASE}/alunos/{aluno_id}/materiais/{material_id}", headers=h
        ).status_code
        == 204
    )
    assert cliente.delete(f"{BASE}/materiais/{material_id}", headers=h).status_code == 200


def test_chave_certa_nas_escritas_de_adaptacoes_e_jobs(cliente, com_chave, monkeypatch):
    h = {"X-API-Key": com_chave}
    monkeypatch.setattr(
        adaptacoes_router,
        "criar_job",
        lambda **_: JobResposta(
            job_id="JOB1",
            status="queued",
            iniciado_em="2026-11-09T12:00:00+00:00",
            atualizado_em="2026-11-09T12:00:00+00:00",
        ),
    )

    criado = cliente.post(f"{BASE}/adaptacoes", headers=h, json=_CORPO_ADAPTACAO)
    assert criado.status_code == 202

    # Passou pela chave; o job não existe, então o erro agora é o do domínio.
    cancelado = cliente.delete(f"{BASE}/jobs/JOB_INEXISTENTE", headers=h)
    assert cancelado.status_code == 404
    assert cancelado.json()["erro"]["codigo"] == "JOB_NAO_ENCONTRADO"


def test_chave_ausente_vence_a_validacao_do_corpo(cliente, com_chave):
    resp = cliente.post(f"{BASE}/alunos", json={})
    assert resp.status_code == 401
    assert resp.json()["erro"]["codigo"] == "NAO_AUTORIZADO"


def test_chave_com_espacos_nas_pontas_na_configuracao_e_normalizada(cliente, monkeypatch):
    monkeypatch.setattr(settings, "api_key_empresa", f"  {CHAVE}\n")
    assert cliente.get(f"{BASE}/alunos", headers={"X-API-Key": CHAVE}).status_code == 200
    assert cliente.get(f"{BASE}/alunos").status_code == 401


@pytest.mark.parametrize("metodo,caminho", ROTAS_ABERTAS, ids=lambda v: str(v))
def test_rotas_abertas_nao_exigem_chave(cliente, com_chave, metodo, caminho):
    resp = cliente.request(metodo, caminho)
    assert resp.status_code != 401


def test_area_do_aluno_funciona_sem_chave(cliente, com_chave, semear_aluno):
    semear_aluno(nome="Bia Lima")
    resp = cliente.get(f"{BASE}/aluno/identificacao")
    assert resp.status_code == 200
    assert [i["nome"] for i in resp.json()["itens"]] == ["Bia Lima"]


def test_preflight_cors_nao_e_bloqueado(cliente, com_chave):
    resp = cliente.options(
        f"{BASE}/alunos",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-api-key" in resp.headers["access-control-allow-headers"].lower()


# ── Sem a variável configurada ────────────────────────────────────────────────


@pytest.mark.parametrize("valor", ["", "   ", "\t\n"])
def test_sem_variavel_o_comportamento_atual_continua(cliente, monkeypatch, valor):
    monkeypatch.setattr(settings, "api_key_empresa", valor)

    assert cliente.get(f"{BASE}/alunos").status_code == 200
    criado = cliente.post(
        f"{BASE}/alunos", json={"nome": "Ana Silva", "email": "ana@exemplo.com"}
    )
    assert criado.status_code == 201
    assert cliente.get(f"{BASE}/materiais").status_code == 200
    # Uma chave enviada sem haver chave configurada também não bloqueia.
    resp = cliente.get(f"{BASE}/alunos", headers={"X-API-Key": CHAVE_ERRADA})
    assert resp.status_code == 200


def test_sem_variavel_avisa_no_log_uma_unica_vez(cliente, caplog):
    with caplog.at_level(logging.INFO):
        cliente.get(f"{BASE}/alunos")
        cliente.get(f"{BASE}/materiais")
        cliente.post(f"{BASE}/alunos", json={"nome": "Ana Silva", "email": "ana@exemplo.com"})

    avisos = _aviso_emitido(caplog)
    assert len(avisos) == 1
    assert "API_KEY_EMPRESA" in avisos[0].getMessage()


def test_aviso_nao_sai_na_subida_nem_em_rota_aberta(caplog):
    from fastapi.testclient import TestClient

    with caplog.at_level(logging.INFO):
        with TestClient(app) as c:  # sobe a aplicação (lifespan)
            c.get(f"{BASE}/health")
            c.get(f"{BASE}/aluno/identificacao")

    assert _aviso_emitido(caplog) == []


def test_com_chave_configurada_nao_ha_aviso(cliente, com_chave, caplog):
    with caplog.at_level(logging.INFO):
        cliente.get(f"{BASE}/alunos", headers={"X-API-Key": com_chave})
        cliente.get(f"{BASE}/alunos")

    assert _aviso_emitido(caplog) == []


# ── A chave não vaza ──────────────────────────────────────────────────────────


def test_chave_nao_aparece_em_logs_nem_respostas(cliente, com_chave, caplog):
    with caplog.at_level(logging.DEBUG):
        respostas = [
            cliente.get(f"{BASE}/alunos"),
            cliente.get(f"{BASE}/alunos", headers={"X-API-Key": CHAVE_ERRADA}),
            cliente.get(f"{BASE}/alunos", headers={"X-API-Key": com_chave}),
            cliente.delete(f"{BASE}/jobs/JOB", headers={"X-API-Key": CHAVE_ERRADA}),
        ]

    logs = _mensagens_do_log(caplog)
    assert CHAVE not in logs
    assert CHAVE_ERRADA not in logs
    for r in respostas[:2] + respostas[3:]:
        assert CHAVE not in r.text and CHAVE_ERRADA not in r.text
    assert CHAVE not in respostas[2].text


def test_chave_nao_aparece_no_repr_das_configuracoes(com_chave):
    assert CHAVE not in repr(settings)
    assert CHAVE not in str(settings)


# ── Cobertura das rotas registradas ───────────────────────────────────────────


def _usa_chave(dependant) -> bool:
    for sub in dependant.dependencies:
        if sub.call is seguranca.exigir_chave_empresa or _usa_chave(sub):
            return True
    return False


def _rotas_v1():
    for rota in app.routes:
        if isinstance(rota, APIRoute) and rota.path.startswith(BASE):
            for metodo in sorted(rota.methods - {"HEAD"}):
                yield metodo, rota.path, _usa_chave(rota.dependant)


def test_toda_rota_da_empresa_exige_a_chave():
    """Garante que uma rota nova em /alunos, /materiais ou de escrita não fique aberta."""
    esperadas_protegidas = []
    for metodo, caminho, protegida in _rotas_v1():
        recurso = caminho.removeprefix(BASE).split("/")[1]
        escrita = metodo in {"POST", "PUT", "PATCH", "DELETE"}
        deve_proteger = recurso in {"alunos", "materiais"} or (
            recurso in {"adaptacoes", "jobs"} and escrita
        )
        if deve_proteger:
            esperadas_protegidas.append((metodo, caminho, protegida))
        elif recurso in {"aluno", "health", "oci"}:
            assert not protegida, (metodo, caminho)

    assert esperadas_protegidas, "nenhuma rota da empresa encontrada"
    assert [r for r in esperadas_protegidas if not r[2]] == []


def _forma(caminho: str) -> str:
    """Troca parâmetros ({id} ou valores fictícios do teste) por ``{}``."""
    partes = ["{}" if p.startswith("{") or p in {"ID", "MAT", "JOB"} else p for p in caminho.split("/")]
    return "/".join(partes)


def test_rotas_protegidas_do_teste_cobrem_as_rotas_registradas():
    registradas = {(m, _forma(c)) for m, c, protegida in _rotas_v1() if protegida}
    cobertas = {(m, _forma(c)) for m, c, _ in ROTAS_PROTEGIDAS}
    assert registradas == cobertas
