"""Garante que perfil, formato, nicho e nível chegam ao prompt do modelo.

Nenhum teste acessa a rede: o modelo de linguagem é substituído por um
falso que guarda o prompt recebido, e os embeddings usam o falso do RAG.
"""

import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm import Mensagem, registrar_provedor
from app.main import app
from app.models import FormatoSaida, NichoSetor, NivelDetalhe, PerfilDestinatario
from app.services import pipeline
from app.services.pipeline import (
    _INSTRUCOES_FORMATO,
    _NIVEL_DESC,
    _PERFIL_DESC,
    _montar_prompt,
    executar_pipeline,
)

PERFIS = get_args(PerfilDestinatario)
FORMATOS = get_args(FormatoSaida)
NICHOS = get_args(NichoSetor)
NIVEIS = get_args(NivelDetalhe)

TITULO = "Introdução a APIs REST"
TRECHOS = [
    "O método GET busca um recurso sem alterá-lo.",
    "O código 404 indica que o recurso não foi encontrado.",
]


# ── _montar_prompt ────────────────────────────────────────────────────────────


def test_dicionarios_cobrem_todos_os_valores():
    assert set(_PERFIL_DESC) == set(PERFIS)
    assert set(_NIVEL_DESC) == set(NIVEIS)
    assert set(_INSTRUCOES_FORMATO) == set(FORMATOS)


@pytest.mark.parametrize("nivel", NIVEIS)
@pytest.mark.parametrize("formato", FORMATOS)
@pytest.mark.parametrize("perfil", PERFIS)
def test_prompt_contem_parametros_escolhidos(perfil, formato, nivel):
    nicho = "Fintech"
    prompt = _montar_prompt(TITULO, TRECHOS, perfil, formato, nicho, nivel)

    assert _PERFIL_DESC[perfil] in prompt
    assert _NIVEL_DESC[nivel] in prompt
    assert f"Setor / nicho: {nicho}." in prompt
    assert TITULO in prompt
    for trecho in TRECHOS:
        assert trecho in prompt

    assert _INSTRUCOES_FORMATO[formato] in prompt
    for outro, instrucoes in _INSTRUCOES_FORMATO.items():
        if outro != formato:
            assert instrucoes not in prompt


@pytest.mark.parametrize("nicho", NICHOS)
def test_prompt_contem_cada_nicho(nicho):
    prompt = _montar_prompt(TITULO, TRECHOS, "Iniciante", "Quiz", nicho, "Didatico")
    assert f"Setor / nicho: {nicho}." in prompt


def test_perfis_diferentes_geram_prompts_diferentes():
    prompts = {
        _montar_prompt(TITULO, TRECHOS, p, "Quiz", "Geral", "Tecnico") for p in PERFIS
    }
    assert len(prompts) == len(PERFIS)


# ── executar_pipeline com modelo falso ───────────────────────────────────────

RESPOSTA_FLASHCARDS = json.dumps(
    {
        "tipo": "flashcards",
        "titulo": "APIs REST",
        "introducao_contextualizada": "Revisão rápida de HTTP.",
        "itens": [
            {"frente": "GET", "verso": "Busca um recurso.", "dica_didatica": None},
            {"frente": "POST", "verso": "Cria um recurso.", "dica_didatica": None},
            {"frente": "404", "verso": "Recurso não encontrado.", "dica_didatica": None},
        ],
    }
)

TEXTO_DOCUMENTO = "\n\n".join(
    [
        "O protocolo HTTP define métodos como GET, POST, PUT e DELETE para "
        "manipular recursos em uma API REST.",
        "Os códigos de status informam o resultado: 200 para sucesso, 404 "
        "para recurso não encontrado e 500 para erro interno do servidor.",
    ]
    * 3
)


class _ModeloFalso:
    """Provedor de LLM falso que guarda os prompts recebidos."""

    nome = "falso"
    prompts: list[str] = []

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        assert [m.papel for m in mensagens] == ["user"]
        _ModeloFalso.prompts.append(mensagens[0].conteudo)
        return RESPOSTA_FLASHCARDS


@pytest.fixture
def modelo_falso(monkeypatch):
    _ModeloFalso.prompts = []
    registrar_provedor("falso", _ModeloFalso)
    monkeypatch.setattr(settings, "llm_provider", "falso")
    return _ModeloFalso


@pytest.fixture
def oci_desligado(monkeypatch):
    # Sem namespace o serviço OCI entra no modo degradado e não acessa a rede.
    monkeypatch.setattr(settings, "oci_namespace", "")


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario", "oci_desligado")
def test_pipeline_envia_parametros_ao_modelo(modelo_falso):
    etapas = []
    pacote = executar_pipeline(
        documento_id="doc-parametros",
        titulo=TITULO,
        texto=TEXTO_DOCUMENTO,
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil="LiderTecnico",
        formato="Flashcards",
        nicho="Saude",
        nivel="Executivo",
        on_progresso=lambda etapa, pct, _msg: etapas.append((etapa, pct)),
    )

    assert len(modelo_falso.prompts) == 1
    prompt = modelo_falso.prompts[0]
    assert _PERFIL_DESC["LiderTecnico"] in prompt
    assert _NIVEL_DESC["Executivo"] in prompt
    assert "Setor / nicho: Saude." in prompt
    assert TITULO in prompt
    assert _INSTRUCOES_FORMATO["Flashcards"] in prompt
    assert _INSTRUCOES_FORMATO["Quiz"] not in prompt
    assert "404 para recurso não encontrado" in prompt  # trecho recuperado do documento

    assert pacote.metadados.perfil_aplicado == "LiderTecnico"
    assert pacote.metadados.formato_gerado == "Flashcards"
    assert pacote.metadados.nivel_detalhe_aplicado == "Executivo"
    assert pacote.conteudo_adaptado.tipo == "flashcards"
    assert pacote.armazenamento_oci.status_upload == "falha"
    assert [e for e, _ in etapas] == [
        "chunking", "embeddings", "gerando", "gerando", "revisando", "armazenando"
    ]


# ── Validação na rota ────────────────────────────────────────────────────────

client = TestClient(app)

CORPO_VALIDO = {
    "documento_titulo": TITULO,
    "documento_conteudo": TEXTO_DOCUMENTO,
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("perfil_destinatario", "Estagiario"),
        ("perfil_destinatario", "iniciante"),
        ("formato_saida", "Podcast"),
        ("formato_saida", ""),
        ("nicho_setor", "Varejo"),
        ("nivel_detalhe", "Avancado"),
    ],
)
def test_rota_rejeita_valor_invalido(campo, valor, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        "app.api.v1.routers.adaptacoes.criar_job", lambda **kw: chamadas.append(kw)
    )
    resp = client.post("/api/v1/adaptacoes", json={**CORPO_VALIDO, campo: valor})

    assert resp.status_code == 422
    erro = resp.json()["erro"]
    assert erro["codigo"] == "VALIDACAO"
    assert campo in erro["campos"]
    assert chamadas == []
