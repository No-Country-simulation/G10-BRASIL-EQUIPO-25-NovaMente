"""Rotas do chat (app/api/v1/routers/chat.py) com provedor falso, sem rede."""

from __future__ import annotations

import logging
import threading

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import chat as rotas_chat
from app.core.config import settings
from app.core.limite_taxa import LimiteDeTaxa, segundos_para_cabecalho
from app.llm import (
    ErroAutenticacao,
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
    ErroRespostaInvalida,
    ErroTimeout,
    ErroTransitorio,
    fabrica,
)
from app.models.db import AlunoDB, MaterialDB
from app.services import fonte
from app.services.contexto_chat import carregar_fontes, limpar_cache, tamanho_cache

SEGREDO_MATERIAL = "zorbaxilmarcador"
SEGREDO_PERGUNTA = "quintafolhamarcador"
SEGREDO_HISTORICO = "historicomarcador"
SEGREDO_RESPOSTA = "vermelhoazulmarcador"
SEGREDO_PROVEDOR = "detalheinternodoprovedor"

TEXTO = "\n\n".join(
    f"Seção {i}. Uma VCN é a rede virtual privada da nuvem, dividida em subnets. "
    f"As tabelas de roteamento definem o caminho do tráfego e o {SEGREDO_MATERIAL} "
    "liga a VCN à internet por meio de um gateway de internet na subnet pública."
    for i in range(6)
)
PERGUNTA = {"pergunta": f"O que é uma VCN e o {SEGREDO_PERGUNTA}?"}


class _Falso:
    """Provedor falso; o roteiro é compartilhado e o último item se repete."""

    nome = "falso"
    roteiro: list = []
    chamadas: list = []

    def __init__(self, modelo: str):
        self.modelo = modelo

    def gerar(self, mensagens, *, timeout_segundos):
        _Falso.chamadas.append(self.modelo)
        item = _Falso.roteiro[min(len(_Falso.chamadas), len(_Falso.roteiro)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


class _Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


@pytest.fixture
def modelo(monkeypatch):
    _Falso.roteiro = [f"A VCN é a rede privada e o {SEGREDO_RESPOSTA} vem do material [F1] [P1]."]
    _Falso.chamadas = []
    monkeypatch.setattr(fabrica, "_criar_base_do_chat", lambda nome, modelo, raciocinio: _Falso(modelo))
    for campo, valor in {
        "chat_llm_provider": "nvidia",
        "chat_llm_modelo": "org/padrao",
        "chat_modelos_permitidos": "org/outro, org/padrao",
        "chat_llm_raciocinio": "desligado",
        "chat_llm_timeout_segundos": 45,
        "chat_max_pergunta_caracteres": 1000,
        "chat_max_mensagens_historico": 10,
        "chat_max_contexto_caracteres": 24_000,
        "chat_limite_por_minuto": 12,
    }.items():
        monkeypatch.setattr(settings, campo, valor)
    relogio = _Relogio()
    monkeypatch.setattr(rotas_chat.limite_chat, "relogio", relogio)
    rotas_chat.limite_chat.limpar()
    limpar_cache()
    yield relogio
    rotas_chat.limite_chat.limpar()
    limpar_cache()


@pytest.fixture
def material(db_session, semear_material):
    def _criar(visibilidade="publicado", com_fonte=True):
        mid = semear_material(visibilidade=visibilidade)
        if com_fonte:
            fonte.salvar_fonte(db_session, mid, TEXTO)
            db_session.commit()
        return mid

    return _criar


@pytest.fixture
def aluno_com_material(semear_aluno, material, vincular):
    aluno = semear_aluno()
    mid = vincular(aluno, material())
    return aluno, mid


def _url_aluno(mid, aluno):
    return f"/api/v1/aluno/materiais/{mid}/chat?aluno_id={aluno}"


# ── Caminho feliz ─────────────────────────────────────────────────────────────


def test_aluno_pergunta_sobre_material_publicado_e_vinculado(cliente, modelo, aluno_com_material):
    aluno, mid = aluno_com_material
    resp = cliente.post(_url_aluno(mid, aluno), json=PERGUNTA)
    assert resp.status_code == 200
    corpo = resp.json()
    assert set(corpo) == {
        "resposta", "citacoes", "base", "recusou", "fundamentada", "ancoragem", "modelo", "trechos_usados",
    }
    assert [(c["id"], c["origem"]) for c in corpo["citacoes"]] == [("F1", "documento"), ("P1", "pacote")]
    assert all(c["excerto"] for c in corpo["citacoes"])
    assert corpo["base"] == "documento_e_pacote"
    assert corpo["fundamentada"] is True and corpo["recusou"] is False
    assert corpo["modelo"] == "org/padrao"
    assert corpo["trechos_usados"] > 0
    assert 0 <= corpo["ancoragem"] <= 1


def test_empresa_pergunta_sobre_rascunho(cliente, modelo, material):
    mid = material(visibilidade="rascunho", com_fonte=False)
    resp = cliente.post(f"/api/v1/materiais/{mid}/chat", json=PERGUNTA)
    assert resp.status_code == 200
    assert resp.json()["base"] == "pacote"


# ── Aluno: visibilidade, vínculo e identificação ──────────────────────────────


def test_aluno_recebe_o_mesmo_404_para_rascunho_nao_vinculado_e_inexistente(
    cliente, modelo, semear_aluno, material, vincular
):
    aluno = semear_aluno()
    rascunho = vincular(aluno, material(visibilidade="rascunho"))
    de_outro = vincular(semear_aluno(), material())
    respostas = [
        cliente.post(_url_aluno(mid, aluno), json=PERGUNTA)
        for mid in (rascunho, de_outro, "NAO_EXISTE")
    ]
    assert {r.status_code for r in respostas} == {404}
    assert respostas[0].json() == respostas[1].json() == respostas[2].json() == {
        "erro": {"codigo": "MATERIAL_NAO_ENCONTRADO", "mensagem": "Material não encontrado."}
    }
    assert _Falso.chamadas == []


def test_aluno_nao_identificado_segue_as_outras_rotas_do_aluno(cliente, modelo, aluno_com_material, db_session):
    _aluno, mid = aluno_com_material
    sem_id = cliente.post(f"/api/v1/aluno/materiais/{mid}/chat", json=PERGUNTA)
    assert sem_id.status_code == 422
    assert sem_id.json()["erro"]["codigo"] == "VALIDACAO"
    assert "aluno_id" in sem_id.json()["erro"]["campos"]

    inexistente = cliente.post(_url_aluno(mid, "NAO_EXISTE"), json=PERGUNTA)
    assert inexistente.status_code == 404
    assert inexistente.json()["erro"]["codigo"] == "ALUNO_NAO_ENCONTRADO"
    assert cliente.get("/api/v1/aluno/materiais?aluno_id=NAO_EXISTE").json() == inexistente.json()

    agora = "2026-11-18T00:00:00+00:00"
    db_session.add(AlunoDB(aluno_id="INATIVO", nome="X", email="x@exemplo.com", status="inativo",
                           criado_em=agora, atualizado_em=agora))
    db_session.commit()
    inativo = cliente.post(_url_aluno(mid, "INATIVO"), json=PERGUNTA)
    assert inativo.status_code == 403
    assert inativo.json()["erro"]["codigo"] == "ALUNO_INATIVO"


# ── Validação ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "corpo,campo",
    [
        ({"pergunta": "oi", "historico": [{"papel": "system", "conteudo": "x"}]}, "historico.0.papel"),
        ({"pergunta": "oi", "historico": [{"papel": "user", "conteudo": "x"}] * 51}, "historico"),
        ({"historico": []}, "pergunta"),
        ({"pergunta": "x" * 10_001}, "pergunta"),
        ({"pergunta": "oi", "modelo": "m" * 201}, "modelo"),
    ],
)
def test_corpo_invalido_da_422_no_formato_do_projeto(cliente, modelo, material, corpo, campo):
    resp = cliente.post(f"/api/v1/materiais/{material()}/chat", json=corpo)
    assert resp.status_code == 422
    erro = resp.json()["erro"]
    assert erro["codigo"] == "VALIDACAO"
    assert campo in erro["campos"]


@pytest.mark.parametrize(
    "pergunta,codigo", [("   ", "PERGUNTA_VAZIA"), ("x" * 1001, "PERGUNTA_LONGA")]
)
def test_pergunta_vazia_ou_longa(cliente, modelo, material, pergunta, codigo):
    resp = cliente.post(f"/api/v1/materiais/{material()}/chat", json={"pergunta": pergunta})
    assert resp.status_code == 422
    erro = resp.json()["erro"]
    assert erro["codigo"] == codigo
    assert "pergunta" in erro["campos"]
    assert "x" * 50 not in resp.text


# ── Modelos ───────────────────────────────────────────────────────────────────


def test_modelo_fora_da_lista(cliente, modelo, material):
    resp = cliente.post(f"/api/v1/materiais/{material()}/chat", json={**PERGUNTA, "modelo": "org/x"})
    assert resp.status_code == 422
    erro = resp.json()["erro"]
    assert erro["codigo"] == "CHAT_MODELO_NAO_PERMITIDO"
    assert "modelo" in erro["campos"]
    assert erro["detalhes"]["modelos_permitidos"] == ["org/padrao", "org/outro"]


def test_modelo_da_lista_e_usado(cliente, modelo, material):
    resp = cliente.post(f"/api/v1/materiais/{material()}/chat", json={**PERGUNTA, "modelo": "org/outro"})
    assert resp.status_code == 200
    assert resp.json()["modelo"] == "org/outro"
    assert _Falso.chamadas == ["org/outro"]


def test_lista_de_modelos(cliente, modelo):
    resp = cliente.get("/api/v1/chat/modelos")
    assert resp.status_code == 200
    assert resp.json() == {"padrao": "org/padrao", "modelos": ["org/padrao", "org/outro"]}


# ── Mapeamento de erros ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "falha,status,codigo,retry_after",
    [
        (ErroRespostaInvalida(SEGREDO_PROVEDOR), 502, "CHAT_RESPOSTA_INVALIDA", None),
        (ErroTimeout(SEGREDO_PROVEDOR), 504, "CHAT_TEMPO_ESGOTADO", None),
        (ErroLimiteTaxa(SEGREDO_PROVEDOR), 429, "CHAT_PROVEDOR_OCUPADO", "10"),
        (ErroIndisponivel(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        (ErroTransitorio(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        (ErroAutenticacao(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        (ErroModeloIndisponivel(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        (ErroRequisicaoRecusada(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        (ErroConfiguracao(SEGREDO_PROVEDOR), 503, "CHAT_INDISPONIVEL", None),
        ("", 502, "CHAT_RESPOSTA_VAZIA", None),
    ],
)
def test_erros_do_provedor(cliente, modelo, material, caplog, falha, status, codigo, retry_after):
    _Falso.roteiro = [falha]
    with caplog.at_level(logging.DEBUG):
        resp = cliente.post(f"/api/v1/materiais/{material()}/chat", json=PERGUNTA)
    assert resp.status_code == status
    assert resp.json()["erro"]["codigo"] == codigo
    assert resp.headers.get("Retry-After") == retry_after
    for segredo in (SEGREDO_PROVEDOR, SEGREDO_PERGUNTA, SEGREDO_MATERIAL):
        assert segredo not in resp.text
        assert segredo not in caplog.text


def test_pacote_corrompido_tem_o_tratamento_do_detalhe(cliente, modelo, material, db_session):
    mid = material()
    db_session.get(MaterialDB, mid).pacote_json = "{quebrado"
    db_session.commit()
    resp = cliente.post(f"/api/v1/materiais/{mid}/chat", json=PERGUNTA)
    detalhe = cliente.get(f"/api/v1/materiais/{mid}")
    assert resp.status_code == detalhe.status_code == 500
    assert resp.json()["erro"]["codigo"] == detalhe.json()["erro"]["codigo"] == "INTERNO"
    assert resp.json()["erro"]["mensagem"] == detalhe.json()["erro"]["mensagem"]


def test_outra_excecao_cai_no_handler_generico(db_session, modelo, material):
    from app.core.db import get_db
    from app.main import app

    _Falso.roteiro = [RuntimeError(SEGREDO_PROVEDOR)]
    mid = material()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(f"/api/v1/materiais/{mid}/chat", json=PERGUNTA)
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 500
    assert resp.json()["erro"]["codigo"] == "INTERNO"
    assert SEGREDO_PROVEDOR not in resp.text


# ── Limite por aluno ──────────────────────────────────────────────────────────


def test_limite_por_aluno(cliente, modelo, semear_aluno, material, vincular, monkeypatch):
    monkeypatch.setattr(settings, "chat_limite_por_minuto", 2)
    aluno, outro = semear_aluno(), semear_aluno()
    mid = material()
    vincular(aluno, mid)
    vincular(outro, mid)

    # Corpo inválido não consome o limite.
    for _ in range(3):
        assert cliente.post(_url_aluno(mid, aluno), json={"historico": []}).status_code == 422
    # Uma pergunta aceita pelo limite conta mesmo que dê erro depois (404).
    assert cliente.post(_url_aluno("NAO_EXISTE", aluno), json=PERGUNTA).status_code == 404
    assert cliente.post(_url_aluno(mid, aluno), json=PERGUNTA).status_code == 200

    modelo.agora += 15
    excedeu = cliente.post(_url_aluno(mid, aluno), json=PERGUNTA)
    assert excedeu.status_code == 429
    assert excedeu.json()["erro"]["codigo"] == "CHAT_LIMITE_EXCEDIDO"
    assert excedeu.headers["Retry-After"] == "45"
    chamadas = len(_Falso.chamadas)

    assert cliente.post(_url_aluno(mid, outro), json=PERGUNTA).status_code == 200  # outro aluno
    assert len(_Falso.chamadas) == chamadas + 1

    modelo.agora += 46  # a janela passou
    assert cliente.post(_url_aluno(mid, aluno), json=PERGUNTA).status_code == 200


def test_limite_da_empresa_e_um_balde_so(cliente, modelo, material, monkeypatch):
    monkeypatch.setattr(settings, "chat_limite_por_minuto", 1)
    a, b = material(), material()
    assert cliente.post(f"/api/v1/materiais/{a}/chat", json=PERGUNTA).status_code == 200
    resp = cliente.post(f"/api/v1/materiais/{b}/chat", json=PERGUNTA)
    assert resp.status_code == 429
    assert resp.json()["erro"]["codigo"] == "CHAT_LIMITE_EXCEDIDO"
    assert resp.headers["Retry-After"] == "60"


def test_limite_e_thread_safe():
    limite = LimiteDeTaxa(100, relogio=lambda: 5.0)
    aceitas = []
    trava = threading.Lock()

    def trabalhar():
        for _ in range(50):
            if limite.registrar("mesma") is None:
                with trava:
                    aceitas.append(1)

    threads = [threading.Thread(target=trabalhar) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(aceitas) == 100


def test_limite_descarta_chaves_ociosas_e_tem_teto():
    relogio = _Relogio()
    limite = LimiteDeTaxa(5, janela_segundos=60, relogio=relogio, max_chaves=50)
    for i in range(40):
        limite.registrar(f"aluno-{i}")
    assert len(limite) == 40
    relogio.agora += 61
    limite.registrar("novo")
    assert len(limite) == 1  # as ociosas saíram
    for i in range(500):
        limite.registrar(f"outro-{i}")
    assert len(limite) == 50


def test_retry_after_arredonda_para_cima():
    assert segundos_para_cabecalho(0.2) == 1
    assert segundos_para_cabecalho(44.01) == 45


# ── Privacidade ───────────────────────────────────────────────────────────────


def test_log_sem_pergunta_historico_material_nem_resposta(cliente, modelo, aluno_com_material, caplog):
    aluno, mid = aluno_com_material
    corpo = {
        **PERGUNTA,
        "historico": [
            {"papel": "user", "conteudo": f"antes {SEGREDO_HISTORICO}"},
            {"papel": "assistant", "conteudo": f"{SEGREDO_HISTORICO} [F1]"},
        ],
    }
    with caplog.at_level(logging.DEBUG):
        assert cliente.post(_url_aluno(mid, aluno), json=corpo).status_code == 200
        for falha in (ErroTimeout(SEGREDO_PROVEDOR), ErroConfiguracao(SEGREDO_PROVEDOR), ""):
            _Falso.roteiro = [falha]
            assert cliente.post(_url_aluno(mid, aluno), json=corpo).status_code >= 500
        assert cliente.post(_url_aluno(mid, aluno), json={"pergunta": SEGREDO_PERGUNTA * 100}).status_code == 422
    assert "Chat: material=" in caplog.text
    for segredo in (SEGREDO_PERGUNTA, SEGREDO_HISTORICO, SEGREDO_MATERIAL, SEGREDO_RESPOSTA, SEGREDO_PROVEDOR):
        assert segredo not in caplog.text


# ── Cache e remoção ───────────────────────────────────────────────────────────


def test_apagar_material_invalida_o_cache(cliente, modelo, material, monkeypatch):
    monkeypatch.setattr("app.api.v1.routers.materiais.remover_objeto", lambda _: True)
    mid = material()
    assert cliente.post(f"/api/v1/materiais/{mid}/chat", json=PERGUNTA).status_code == 200
    assert tamanho_cache() == 1
    assert cliente.delete(f"/api/v1/materiais/{mid}").status_code == 200
    assert tamanho_cache() == 0
    resp = cliente.post(f"/api/v1/materiais/{mid}/chat", json=PERGUNTA)
    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "MATERIAL_NAO_ENCONTRADO"
    assert tamanho_cache() == 0


# ── OpenAPI ───────────────────────────────────────────────────────────────────


def test_rotas_documentadas_no_openapi(cliente):
    esquema = cliente.get("/openapi.json").json()
    caminhos = esquema["paths"]
    assert "post" in caminhos["/api/v1/aluno/materiais/{material_id}/chat"]
    assert "post" in caminhos["/api/v1/materiais/{material_id}/chat"]
    assert "get" in caminhos["/api/v1/chat/modelos"]
    componentes = esquema["components"]["schemas"]
    for nome in ("PerguntaChat", "RespostaChatSaida", "CitacaoChat", "MensagemHistorico", "ModelosChat"):
        assert nome in componentes
    assert componentes["PerguntaChat"]["examples"]
    respostas = caminhos["/api/v1/aluno/materiais/{material_id}/chat"]["post"]["responses"]
    assert {"200", "404", "422", "429", "502", "503", "504"} <= set(respostas)
