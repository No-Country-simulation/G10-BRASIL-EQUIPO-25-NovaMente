"""Testes da chamada ao LLM (timeout, indisponibilidade, retentativa) e do worker.

Nada acessa a rede: o Gemini, o RAG e o OCI são substituídos por falsos
definidos neste arquivo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from google.api_core import exceptions as google_exc

from app.core.config import settings
from app.models import ArmazenamentoOci, JobResposta
from app.rag.modelos import Trecho
from app.services import pipeline, repositorio
from app.workers import job_worker

TEXTO_CRU = "detalhe-interno-do-sdk-123"

RESPOSTA_VALIDA = json.dumps(
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

SEM_TITULO = json.dumps(
    {
        "tipo": "flashcards",
        "introducao_contextualizada": "Sem título.",
        "itens": [{"frente": "a", "verso": "b"}] * 3,
    }
)


# ── Falsos ────────────────────────────────────────────────────────────────────


class _RespostaFalsa:
    def __init__(self, texto: str | None):
        self._texto = texto

    @property
    def text(self) -> str:
        if self._texto is None:
            # Mesmo comportamento do SDK quando não há candidatos (ex.: bloqueio).
            raise ValueError(f"sem candidatos {TEXTO_CRU}")
        return self._texto


class _ModeloFalso:
    """Devolve, em ordem, os itens de ``roteiro``: texto, None (bloqueio) ou exceção."""

    roteiro: list = []
    chamadas: list[dict] = []

    def __init__(self, nome_modelo: str):
        self.nome_modelo = nome_modelo

    def generate_content(self, prompt, request_options=None):
        _ModeloFalso.chamadas.append({"prompt": prompt, "request_options": request_options})
        item = _ModeloFalso.roteiro[min(len(_ModeloFalso.chamadas), len(_ModeloFalso.roteiro)) - 1]
        if isinstance(item, BaseException):
            raise item
        return _RespostaFalsa(item)


@pytest.fixture
def modelo(monkeypatch):
    import google.generativeai as genai

    _ModeloFalso.roteiro = [RESPOSTA_VALIDA]
    _ModeloFalso.chamadas = []
    monkeypatch.setattr(genai, "configure", lambda **_kw: None)
    monkeypatch.setattr(genai, "GenerativeModel", _ModeloFalso)
    return _ModeloFalso


@pytest.fixture(autouse=True)
def rag_e_oci_falsos(monkeypatch):
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
            Trecho(texto="O código 404 indica recurso não encontrado.", indice=0,
                   relevancia=0.9, documento_id=kw["documento_id"])
        ],
    )
    monkeypatch.setattr(
        oci,
        "fazer_upload",
        lambda pacote, objeto_id: ArmazenamentoOci(
            bucket="teste", objeto_id=objeto_id, status_upload="falha"
        ),
    )


def _executar(etapas: list | None = None):
    return pipeline.executar_pipeline(
        documento_id="doc-llm",
        titulo="APIs REST",
        texto="texto já indexado pelo RAG falso",
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil="Iniciante",
        formato="Flashcards",
        nicho="Geral",
        nivel="Didatico",
        on_progresso=(lambda e, _p, _m: etapas.append(e)) if etapas is not None else None,
    )


# ── Chamada ao LLM ────────────────────────────────────────────────────────────


def test_caminho_feliz_uma_chamada_com_timeout(modelo, monkeypatch):
    monkeypatch.setattr(settings, "llm_timeout_segundos", 45)
    etapas = []
    pacote = _executar(etapas)
    assert len(modelo.chamadas) == 1
    assert modelo.chamadas[0]["request_options"] == {"timeout": 45}
    assert pacote.conteudo_adaptado.titulo == "APIs REST"
    assert etapas == ["chunking", "embeddings", "gerando", "gerando", "revisando", "armazenando"]


def test_timeout_vira_runtime_error_sem_texto_cru(modelo, monkeypatch):
    monkeypatch.setattr(settings, "llm_timeout_segundos", 30)
    modelo.roteiro = [google_exc.DeadlineExceeded(TEXTO_CRU)]
    with pytest.raises(RuntimeError) as erro:
        _executar()
    mensagem = str(erro.value)
    assert "demorou demais" in mensagem
    assert "30 segundos" in mensagem
    assert TEXTO_CRU not in mensagem
    assert len(modelo.chamadas) == 1  # timeout não é retentado


MSG_LIMITE = "O limite de uso da IA foi atingido. Tente novamente em alguns minutos."
MSG_CONFIGURACAO = (
    "O serviço de IA não está configurado corretamente (modelo ou chave de API). "
    "Avise a equipe."
)
MSG_INDISPONIVEL = "O serviço de IA está indisponível no momento. Tente novamente em instantes."


@pytest.mark.parametrize(
    "excecao,mensagem",
    [
        (google_exc.ResourceExhausted(TEXTO_CRU), MSG_LIMITE),
        (google_exc.NotFound(TEXTO_CRU), MSG_CONFIGURACAO),
        (google_exc.InvalidArgument(TEXTO_CRU), MSG_CONFIGURACAO),
        (google_exc.PermissionDenied(TEXTO_CRU), MSG_CONFIGURACAO),
        (google_exc.Unauthenticated(TEXTO_CRU), MSG_CONFIGURACAO),
        (google_exc.ServiceUnavailable(TEXTO_CRU), MSG_INDISPONIVEL),
        (google_exc.InternalServerError(TEXTO_CRU), MSG_INDISPONIVEL),
    ],
    ids=[
        "limite-429",
        "config-modelo-inexistente",
        "config-argumento-invalido",
        "config-sem-permissao",
        "config-nao-autenticado",
        "indisponivel-503",
        "indisponivel-500",
    ],
)
def test_erros_de_api_por_grupo_sem_texto_cru(modelo, excecao, mensagem):
    modelo.roteiro = [excecao]
    with pytest.raises(RuntimeError) as erro:
        _executar()
    assert str(erro.value) == mensagem
    assert TEXTO_CRU not in str(erro.value)
    assert len(modelo.chamadas) == 1  # erros de API não são retentados


def test_resposta_bloqueada_e_retentada(modelo):
    modelo.roteiro = [None, RESPOSTA_VALIDA]
    pacote = _executar()
    assert len(modelo.chamadas) == 2
    assert pacote.conteudo_adaptado.tipo == "flashcards"


def test_resposta_vazia_duas_vezes_falha(modelo):
    modelo.roteiro = [None, None]
    with pytest.raises(RuntimeError, match="após duas tentativas") as erro:
        _executar()
    assert TEXTO_CRU not in str(erro.value)
    assert len(modelo.chamadas) == 2


def test_json_invalido_depois_valido(modelo):
    modelo.roteiro = ['{"titulo": "quebrado", ', RESPOSTA_VALIDA]
    etapas = []
    pacote = _executar(etapas)
    assert len(modelo.chamadas) == 2
    assert pacote.conteudo_adaptado.titulo == "APIs REST"
    assert etapas.count("revisando") == 1


def test_json_invalido_nas_duas_tentativas(modelo):
    modelo.roteiro = ["isto não é json", '{"a": ']
    with pytest.raises(RuntimeError) as erro:
        _executar()
    assert str(erro.value) == (
        "A IA não devolveu um conteúdo válido após duas tentativas. Tente novamente."
    )
    assert len(modelo.chamadas) == 2


def test_estrutura_sem_titulo_cai_no_mesmo_fluxo(modelo):
    modelo.roteiro = [SEM_TITULO, SEM_TITULO]
    with pytest.raises(RuntimeError, match="após duas tentativas"):
        _executar()
    assert len(modelo.chamadas) == 2


def test_estrutura_sem_titulo_depois_valida(modelo):
    modelo.roteiro = [SEM_TITULO, RESPOSTA_VALIDA]
    assert _executar().conteudo_adaptado.titulo == "APIs REST"
    assert len(modelo.chamadas) == 2


# ── Worker ────────────────────────────────────────────────────────────────────


def _criar_job(job_id: str) -> None:
    agora = datetime.now(timezone.utc).isoformat()
    repositorio.salvar_job(
        JobResposta(job_id=job_id, status="queued", iniciado_em=agora, atualizado_em=agora)
    )


def _rodar_worker(job_id: str) -> JobResposta:
    job_worker._executar(
        job_id, f"doc_{job_id}", "APIs REST", "texto", "texto", None, None,
        "Iniciante", "Flashcards", "Geral", "Didatico",
    )
    return repositorio.obter_job(job_id)


def test_worker_etapas_concluidas_progressivas(modelo, monkeypatch):
    job_id = "JOB_ETAPAS_PROGRESSIVAS"
    _criar_job(job_id)
    instantaneos = []
    executar_real = pipeline.executar_pipeline

    def executar_espiando(**kwargs):
        callback = kwargs["on_progresso"]

        def espiar(etapa, pct, msg=""):
            callback(etapa, pct, msg)
            job = repositorio.obter_job(job_id)
            instantaneos.append((etapa, list(job.etapas_concluidas)))

        return executar_real(**{**kwargs, "on_progresso": espiar})

    monkeypatch.setattr(pipeline, "executar_pipeline", executar_espiando)
    job = _rodar_worker(job_id)

    assert instantaneos == [
        ("chunking", ["extraindo"]),
        ("embeddings", ["extraindo", "chunking"]),
        ("gerando", ["extraindo", "chunking", "embeddings"]),
        ("gerando", ["extraindo", "chunking", "embeddings"]),
        ("revisando", ["extraindo", "chunking", "embeddings", "gerando"]),
        ("armazenando", ["extraindo", "chunking", "embeddings", "gerando", "revisando"]),
    ]
    assert job.status == "succeeded"
    assert job.etapas_concluidas == [
        "extraindo", "chunking", "embeddings", "gerando", "revisando", "armazenando"
    ]


def test_worker_prazo_estourado_vira_failed(modelo, monkeypatch):
    monkeypatch.setattr(settings, "job_timeout_segundos", -1)
    job_id = "JOB_PRAZO_ESTOURADO"
    _criar_job(job_id)
    job = _rodar_worker(job_id)
    assert job.status == "failed"
    assert job.mensagem.startswith("A geração excedeu o tempo limite de")
    assert job.erro.codigo == "INTERNO"
    assert job.erro.mensagem == job.mensagem
    assert len(modelo.chamadas) == 0  # parou no primeiro aviso de progresso


def test_worker_excecao_inesperada_mensagem_generica(monkeypatch):
    def quebra(**_kwargs):
        raise KeyError(TEXTO_CRU)

    monkeypatch.setattr(pipeline, "executar_pipeline", quebra)
    job_id = "JOB_EXCECAO_INESPERADA"
    _criar_job(job_id)
    job = _rodar_worker(job_id)
    assert job.status == "failed"
    assert job.mensagem == "Erro interno ao gerar o material."
    assert TEXTO_CRU not in job.erro.mensagem
    assert job.erro.codigo == "INTERNO"
    assert job.erro.request_id


def test_worker_validation_error_vira_mensagem_generica(monkeypatch):
    from pydantic import ValidationError

    def quebra(**_kwargs):
        ArmazenamentoOci(bucket=TEXTO_CRU, objeto_id="x", status_upload="talvez")

    monkeypatch.setattr(pipeline, "executar_pipeline", quebra)
    with pytest.raises(ValidationError):
        quebra()  # confirma que o falso levanta um ValidationError real
    job_id = "JOB_VALIDATION_ERROR"
    _criar_job(job_id)
    job = _rodar_worker(job_id)
    assert job.status == "failed"
    assert job.mensagem == "Erro interno ao gerar o material."
    assert "status_upload" not in job.erro.mensagem


def test_worker_timeout_de_outra_origem_nao_vira_prazo(monkeypatch):
    def quebra(**_kwargs):
        raise TimeoutError(TEXTO_CRU)

    monkeypatch.setattr(pipeline, "executar_pipeline", quebra)
    job_id = "JOB_TIMEOUT_OUTRA_ORIGEM"
    _criar_job(job_id)
    job = _rodar_worker(job_id)
    assert job.status == "failed"
    assert job.mensagem == "Erro interno ao gerar o material."
    assert "tempo limite" not in job.mensagem


def test_worker_mantem_mensagem_de_runtime_error(modelo):
    modelo.roteiro = [google_exc.ServiceUnavailable(TEXTO_CRU)]
    job_id = "JOB_RUNTIME_ERROR"
    _criar_job(job_id)
    job = _rodar_worker(job_id)
    assert job.status == "failed"
    assert job.mensagem.startswith("O serviço de IA está indisponível")
