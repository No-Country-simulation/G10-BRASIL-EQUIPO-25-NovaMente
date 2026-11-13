"""Conceitos-chave: validação dos que vêm do LLM, fallback e uso no pipeline.

Nada acessa a rede: o provedor de LLM, o RAG e o OCI são falsos.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.llm import Mensagem, registrar_provedor
from app.models import ArmazenamentoOci, JobResposta, MetadadosAdaptacao
from app.rag.modelos import Trecho
from app.services import pipeline, repositorio
from app.services.conceitos import (
    MAX_CARACTERES,
    MAX_CONCEITOS,
    PALAVRAS_GENERICAS,
    conceitos_fallback,
    escolher_conceitos,
    normalizar,
    validar_conceitos,
)
from app.workers import job_worker

TITULO = "Introdução a APIs REST com HTTP"
TEXTO = (
    "# Introdução a APIs REST com HTTP\n\n"
    "Texto simulado para testes do NovaMente.\n\n"
    "## O que é HTTP\n\n"
    "O HTTP é o protocolo da web. Cada troca tem uma requisição e uma resposta.\n"
    "Um método é idempotente quando repetir a requisição produz o mesmo resultado.\n"
    "A idempotência vale para GET, PUT e DELETE. POST cria um recurso.\n"
    "APIs REST usam códigos de status: 404 indica recurso não encontrado.\n"
    "O cabeçalho Content-Type informa o formato do corpo, como JSON.\n"
)


def _validar(candidatos, titulo=TITULO, texto=TEXTO):
    return validar_conceitos(candidatos, titulo=titulo, texto_origem=texto)


# ── normalizar ────────────────────────────────────────────────────────────────


def test_normalizar_ignora_maiusculas_acentos_e_espacos():
    assert normalizar("  Idempotência\n  de   Métodos ") == "idempotencia de metodos"


def test_lista_generica_esta_normalizada():
    assert all(p == normalizar(p) and " " not in p for p in PALAVRAS_GENERICAS)
    assert {"introducao", "texto", "cada", "um", "uma", "resumo", "capitulo", "secao"} <= (
        PALAVRAS_GENERICAS
    )


# ── validar_conceitos ─────────────────────────────────────────────────────────


def test_validos_mantem_a_ordem_do_llm():
    candidatos = ["idempotência", "HTTP", "Content-Type", "códigos de status", "requisição"]
    assert _validar(candidatos) == candidatos


def test_no_maximo_oito_na_ordem_recebida():
    candidatos = ["HTTP", "GET", "PUT", "DELETE", "POST", "JSON", "recurso", "protocolo",
                  "requisição", "resposta"]
    assert _validar(candidatos) == candidatos[:MAX_CONCEITOS]


def test_apara_e_colapsa_espacos_mantendo_a_forma_exibida():
    assert _validar(["  códigos   de\n status "]) == ["códigos de status"]


def test_duplicados_por_maiusculas_acentos_e_plural_sao_descartados():
    candidatos = ["Idempotência", "idempotencia", "IDEMPOTÊNCIA", "API", "APIs", "apis"]
    assert _validar(candidatos) == ["Idempotência", "API"]


@pytest.mark.parametrize(
    "item",
    ["a", "X", " ", "", "Introdução", "Texto", "Cada", "Um", "uma", "Introdução a", "O que é"],
)
def test_vazios_curtos_e_genericos_sao_descartados(item):
    assert _validar([item, "HTTP"]) == ["HTTP"]


def test_item_longo_demais_e_descartado_mesmo_presente_no_texto():
    longo = "protocolo " * 7  # 70 caracteres, presente no texto abaixo
    texto = TEXTO + longo
    assert len(longo.strip()) > MAX_CARACTERES
    assert _validar([longo, "HTTP"], texto=texto) == ["HTTP"]


@pytest.mark.parametrize("variante", [TITULO, TITULO.upper(), "introducao a apis rest com http"])
def test_item_igual_ao_titulo_e_descartado(variante):
    assert _validar([variante, "REST"]) == ["REST"]


def test_fora_do_texto_de_origem_e_descartado():
    assert _validar(["GraphQL", "HTTP", "gRPC", "OAuth"]) == ["HTTP"]


def test_procura_no_texto_inteiro_e_por_palavra_inteira():
    # "Content-Type" só aparece no fim do texto; "TP" está dentro de "HTTP", mas não sozinho.
    assert _validar(["Content-Type", "TP", "ttp"]) == ["Content-Type"]


def test_plural_simples_nos_dois_sentidos_mas_nao_em_siglas():
    texto = "As APIs usam o método GET. A rede local e o HTTP."
    assert _validar(["API", "Métodos", "Redes", "HTTPS"], texto=texto) == ["API", "Métodos", "Redes"]


@pytest.mark.parametrize(
    "valor",
    [None, "HTTP, REST", 42, 3.5, True, {"conceito": "HTTP"}, [1, None, ["HTTP"], {"a": "b"}], []],
    ids=["none", "string", "int", "float", "bool", "dict", "itens-nao-string", "vazia"],
)
def test_tipo_errado_devolve_vazio(valor):
    assert _validar(valor) == []


# ── conceitos_fallback ────────────────────────────────────────────────────────


def test_fallback_ordena_por_frequencia_e_depois_por_aparicao():
    trechos = [
        "O HTTP define métodos. GET busca e POST cria.",
        "No HTTP, GET é idempotente. HTTP usa códigos de status.",
    ]
    # "Guia" vem do título e não aparece nos trechos: frequência 0, vai para o fim.
    assert conceitos_fallback("Guia", trechos) == ["HTTP", "GET", "POST", "Guia"]


def test_fallback_sem_duplicados_genericos_nem_um_caractere():
    trechos = [
        "Introdução. Texto simulado. Cada API tem um contrato. Um exemplo: A, B e C.",
        "As APIs REST usam HTTP. Api e apis são a mesma coisa. Cada REST é REST.",
    ]
    resultado = conceitos_fallback("Introdução ao Tema", trechos)
    normalizados = [normalizar(c) for c in resultado]
    assert resultado[:3] == ["API", "REST", "HTTP"]
    assert len({n.rstrip("s") for n in normalizados}) == len(resultado)
    assert not any(n in PALAVRAS_GENERICAS for n in normalizados)
    assert all(len(n) > 1 for n in normalizados)


def test_fallback_no_maximo_oito():
    trechos = [" ".join(f"Termo{i}" for i in range(20))]
    assert len(conceitos_fallback("Guia", trechos)) == MAX_CONCEITOS


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        ("o guia de bolso", ["o guia de bolso"]),
        ("  muito   " + "longo " * 20, [("muito " + "longo " * 20)[:MAX_CARACTERES].strip()]),
    ],
    ids=["titulo", "titulo-aparado"],
)
def test_fallback_usa_o_titulo_quando_nada_sobra(titulo, esperado):
    resultado = conceitos_fallback(titulo, ["Introdução. Cada texto tem um resumo."])
    assert resultado == esperado
    assert 1 <= len(resultado[0]) <= MAX_CARACTERES


def test_escolher_usa_o_fallback_se_todos_os_do_llm_forem_descartados():
    trechos = ["O HTTP usa GET e POST. HTTP é simples."]
    assert escolher_conceitos(
        ["Introdução", "GraphQL", TITULO], titulo=TITULO, texto_origem=TEXTO, trechos=trechos
    ) == conceitos_fallback(TITULO, trechos)


# ── Pipeline (provedor falso) ─────────────────────────────────────────────────

TRECHOS_RECUPERADOS = [
    "# Introdução a APIs REST com HTTP\n\nTexto simulado para testes do NovaMente.",
    "## O que é HTTP\n\nO HTTP é o protocolo da web. Cada troca tem uma requisição.",
    "A idempotência vale para GET, PUT e DELETE. O HTTP define métodos. APIs REST.",
]

CONTEUDOS = {
    "Flashcards": {
        "tipo": "flashcards", "titulo": "Cartões", "introducao_contextualizada": "Intro.",
        "itens": [{"frente": f"F{i}", "verso": f"V{i}", "dica_didatica": None} for i in range(3)],
    },
    "Quiz": {
        "tipo": "quiz", "titulo": "Quiz", "introducao_contextualizada": "Intro.",
        "itens": [{"pergunta": "O que é 404?", "opcoes": ["Sucesso", "Não encontrado"],
                   "resposta_correta": 1, "explicacao": "404 é Not Found."}],
    },
    "Tutorial": {
        "tipo": "markdown", "titulo": "Tutorial", "introducao_contextualizada": "Intro.",
        "itens": "## Passo 1\n\nFaça a requisição GET e confira o código de status.",
    },
    "ResumoExecutivo": {
        "tipo": "markdown", "titulo": "Resumo", "introducao_contextualizada": "Intro.",
        "itens": "## Pontos-chave\n\n- HTTP usa métodos e códigos de status.",
    },
}

AUSENTE = object()


class _ProvedorConceitos:
    nome = "conceitos"
    respostas: list[str] = []
    mensagens: list[list[Mensagem]] = []

    def gerar(self, mensagens, *, timeout_segundos):
        _ProvedorConceitos.mensagens.append(mensagens)
        indice = min(len(_ProvedorConceitos.mensagens), len(_ProvedorConceitos.respostas)) - 1
        return _ProvedorConceitos.respostas[indice]


def _resposta(formato="Flashcards", conceitos=AUSENTE) -> str:
    corpo = dict(CONTEUDOS[formato])
    if conceitos is not AUSENTE:
        corpo["conceitos_chave"] = conceitos
    return json.dumps(corpo)


@pytest.fixture
def provedor(monkeypatch):
    from app.rag import servico
    from app.services import oci

    def indexar(**kw):
        kw["on_etapa"]("chunking")
        kw["on_etapa"]("embeddings")

    monkeypatch.setattr(servico, "indexar_documento", indexar)
    monkeypatch.setattr(
        servico,
        "recuperar",
        lambda **kw: [
            Trecho(texto=t, indice=i, relevancia=0.9, documento_id=kw["documento_id"])
            for i, t in enumerate(TRECHOS_RECUPERADOS)
        ],
    )
    monkeypatch.setattr(
        oci,
        "fazer_upload",
        lambda pacote, objeto_id: ArmazenamentoOci(
            bucket="teste", objeto_id=objeto_id, status_upload="falha"
        ),
    )
    _ProvedorConceitos.respostas = [_resposta()]
    _ProvedorConceitos.mensagens = []
    registrar_provedor("conceitos", _ProvedorConceitos)
    monkeypatch.setattr(settings, "llm_provider", "conceitos")
    return _ProvedorConceitos


def _executar(formato="Flashcards"):
    return pipeline.executar_pipeline(
        documento_id="doc-conceitos",
        titulo=TITULO,
        texto=TEXTO,
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil="Desenvolvedor",
        formato=formato,
        nicho="Geral",
        nivel="Tecnico",
    )


def _rodar_worker(job_id: str, formato="Flashcards") -> JobResposta:
    agora = datetime.now(timezone.utc).isoformat()
    repositorio.salvar_job(
        JobResposta(job_id=job_id, status="queued", iniciado_em=agora, atualizado_em=agora)
    )
    job_worker._executar(
        job_id, f"doc_{job_id}", TITULO, TEXTO, "texto", None, None,
        "Desenvolvedor", formato, "Geral", "Tecnico",
    )
    return repositorio.obter_job(job_id)


def test_prompt_pede_os_conceitos_em_todos_os_formatos():
    for formato, instrucoes in pipeline._INSTRUCOES_FORMATO.items():
        assert '"conceitos_chave":["..."]' in instrucoes
        prompt = pipeline._montar_prompt(TITULO, ["trecho"], "Iniciante", formato, "Geral", "Didatico")
        assert pipeline._INSTRUCAO_CONCEITOS in prompt
    assert "5 a 8" in pipeline._INSTRUCAO_CONCEITOS
    assert f"{MAX_CARACTERES} caracteres" in pipeline._INSTRUCAO_CONCEITOS


def test_caso_real_so_os_termos_bons_sobrevivem(provedor):
    provedor.respostas = [_resposta(conceitos=[
        "Introdução", "APIs", "Texto", "REST", "Cada", "HTTP", "Um", "idempotência",
        "NovaMente", TITULO, "GraphQL",
    ])]
    pacote = _executar()
    assert pacote.metadados.conceitos_chave == ["APIs", "REST", "HTTP", "idempotência"]
    assert len(provedor.mensagens) == 1


def test_conceitos_validos_do_llm_sao_usados_como_vieram(provedor):
    conceitos = ["idempotência", "códigos de status", "HTTP", "GET", "PUT", "DELETE", "POST",
                 "Content-Type", "JSON", "requisição"]
    provedor.respostas = [_resposta(conceitos=conceitos)]
    assert _executar().metadados.conceitos_chave == conceitos[:MAX_CONCEITOS]


@pytest.mark.parametrize(
    "conceitos",
    [AUSENTE, [], None, "HTTP, REST", 7, [1, 2.5, None, {"x": "HTTP"}], ["GraphQL", "Introdução"]],
    ids=["ausente", "vazia", "null", "string", "numero", "itens-nao-string", "todos-descartados"],
)
def test_conceitos_inaproveitaveis_usam_fallback_sem_retentar(provedor, conceitos):
    provedor.respostas = [_resposta(conceitos=conceitos), _resposta(conceitos=["REST"])]
    job = _rodar_worker("JOB_CONCEITOS_FALLBACK")
    assert job.status == "succeeded"
    assert len(provedor.mensagens) == 1  # a retentativa de resposta inválida não foi usada
    fallback = conceitos_fallback(TITULO, TRECHOS_RECUPERADOS)
    assert job.resultado.metadados.conceitos_chave == fallback
    assert fallback[0] == "HTTP"  # o termo mais frequente nos trechos


def test_json_invalido_continua_sendo_retentado(provedor):
    provedor.respostas = ['{"titulo": "quebrado", ', _resposta(conceitos=["REST", "HTTP"])]
    pacote = _executar()
    assert len(provedor.mensagens) == 2
    assert pacote.metadados.conceitos_chave == ["REST", "HTTP"]


@pytest.mark.parametrize("formato", list(CONTEUDOS))
@pytest.mark.parametrize("conceitos", [AUSENTE, ["HTTP", "REST", "idempotência"]],
                         ids=["fallback", "do-llm"])
def test_pacote_respeita_o_esquema_nos_quatro_formatos(provedor, formato, conceitos):
    provedor.respostas = [_resposta(formato, conceitos)]
    pacote = _executar(formato)
    metadados = MetadadosAdaptacao.model_validate(pacote.metadados.model_dump())
    assert 1 <= len(metadados.conceitos_chave) <= 12
    assert all(isinstance(c, str) and c for c in metadados.conceitos_chave)
    if conceitos is not AUSENTE:
        assert metadados.conceitos_chave == conceitos
