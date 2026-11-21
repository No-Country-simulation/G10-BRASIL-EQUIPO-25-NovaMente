"""Verificação de que chaves e credenciais não vazam em logs nem em respostas.

A chave de teste abaixo é inventada. Os testes forçam falhas do provedor em
que o texto da exceção traz a chave (como poderia acontecer numa URL ou num
detalhe de erro do SDK) e conferem que ela não aparece nos logs capturados,
no job gravado nem no corpo das respostas. Nada acessa a rede.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.core.config import settings
from app.llm.gemini import ProvedorGemini
from app.main import app
from app.models import ArmazenamentoOci, JobResposta
from app.rag.modelos import Trecho
from app.services import repositorio
from app.workers import job_worker

CHAVE = "chave-de-teste-nao-e-real-0123456789-abc"
APP_DIR = Path(__file__).resolve().parents[1] / "app"


class _ModelosFalsos:
    def __init__(self, erro: Exception) -> None:
        self.erro = erro

    def generate_content(self, **_kw):
        raise self.erro


class _ClienteFalso:
    def __init__(self, erro: Exception) -> None:
        self.models = _ModelosFalsos(erro)


def _erro_api(codigo: int) -> Exception:
    detalhes = {"error": {"message": f"API key not valid ({CHAVE})", "status": "INVALID"}}
    return genai_errors.APIError(codigo, detalhes)


ERROS = {
    "api_401_com_chave_no_detalhe": lambda: _erro_api(401),
    "api_429_com_chave_no_detalhe": lambda: _erro_api(429),
    "api_503_com_chave_no_detalhe": lambda: _erro_api(503),
    "conexao_com_chave_na_url": lambda: httpx.ConnectError(
        f"falha em https://generativelanguage.googleapis.com/v1?key={CHAVE}"
    ),
    "erro_desconhecido_com_chave": lambda: RuntimeError(f"estado inválido, key={CHAVE}"),
}


@pytest.fixture(autouse=True)
def ambiente_com_chave_de_teste(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", CHAVE)
    monkeypatch.setattr(settings, "google_api_key", CHAVE)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_tentativas", 2)


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


@pytest.fixture
def sem_redacao():
    """Desliga a máscara de logs: o teste mede o que o próprio código loga."""
    atual = logging.getLogRecordFactory()
    logging.setLogRecordFactory(logging.LogRecord)
    yield
    logging.setLogRecordFactory(atual)


def _registros(caplog) -> str:
    """Tudo o que os handlers emitiriam: mensagens formatadas e tracebacks (com as causas)."""
    return "\n".join([caplog.text, *(registro.getMessage() for registro in caplog.records)])


def _gerar_com_falha(monkeypatch, erro: Exception, job_id: str) -> JobResposta:
    monkeypatch.setattr(ProvedorGemini, "_obter_cliente", lambda self: _ClienteFalso(erro))
    agora = "2026-11-20T12:00:00+00:00"
    repositorio.salvar_job(JobResposta(job_id=job_id, status="queued", iniciado_em=agora, atualizado_em=agora))
    job_worker._executar(
        job_id, f"doc_{job_id}", "APIs REST", "texto", "texto", None, None,
        "Iniciante", "Flashcards", "Geral", "Didatico",
    )
    return repositorio.obter_job(job_id)


@pytest.mark.parametrize("fabricar", ERROS.values(), ids=ERROS.keys())
def test_falha_do_provedor_nao_vaza_a_chave_nem_no_log_nem_no_job_nem_na_api(
    fabricar, monkeypatch, caplog, sem_redacao
):
    caplog.set_level(logging.DEBUG)
    job = _gerar_com_falha(monkeypatch, fabricar(), "JOB_SEGREDO")

    assert job.status == "failed"
    assert CHAVE not in _registros(caplog)
    assert CHAVE not in job.model_dump_json()

    resposta = TestClient(app).get("/api/v1/jobs/JOB_SEGREDO")
    assert resposta.status_code == 200
    assert CHAVE not in resposta.text


def test_o_teste_enxerga_a_chave_quando_ela_e_logada(caplog, sem_redacao):
    """Controle: sem a máscara, a checagem acima falharia se a chave fosse logada."""
    caplog.set_level(logging.DEBUG)
    logging.getLogger("controle").error("chave=%s", CHAVE)
    assert CHAVE in _registros(caplog)


def test_chave_ausente_nao_expoe_nada_alem_do_nome_da_variavel(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    job = _gerar_com_falha_sem_cliente_falso("JOB_SEM_CHAVE")
    assert job.status == "failed"
    assert CHAVE not in _registros(caplog)


def _gerar_com_falha_sem_cliente_falso(job_id: str) -> JobResposta:
    agora = "2026-11-20T12:00:00+00:00"
    repositorio.salvar_job(JobResposta(job_id=job_id, status="queued", iniciado_em=agora, atualizado_em=agora))
    job_worker._executar(
        job_id, f"doc_{job_id}", "APIs REST", "texto", "texto", None, None,
        "Iniciante", "Flashcards", "Geral", "Didatico",
    )
    return repositorio.obter_job(job_id)


def _falha_de_embeddings(monkeypatch) -> JobResposta:
    from app.rag import config as rag_config, embeddings, servico

    monkeypatch.setattr(rag_config, "EMBEDDING_TENTATIVAS", 2)
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: None)

    def indexar(**_kw):
        def chamada():
            raise _erro_api(503)

        embeddings._com_retentativa(chamada)

    monkeypatch.setattr(servico, "indexar_documento", indexar)
    agora = "2026-11-20T12:00:00+00:00"
    repositorio.salvar_job(JobResposta(job_id="JOB_EMB", status="queued", iniciado_em=agora, atualizado_em=agora))
    job_worker._executar(
        "JOB_EMB", "doc_JOB_EMB", "APIs REST", "texto", "texto", None, None,
        "Iniciante", "Flashcards", "Geral", "Didatico",
    )
    return repositorio.obter_job("JOB_EMB")


def test_falha_de_embeddings_nao_vaza_a_chave_no_log_do_job(monkeypatch, caplog):
    """O traceback do job traz a causa encadeada; a máscara de logs esconde a chave nela."""
    caplog.set_level(logging.DEBUG)
    job = _falha_de_embeddings(monkeypatch)

    assert job.status == "failed"
    assert CHAVE not in job.model_dump_json()
    assert CHAVE not in _registros(caplog)
    assert "***" in caplog.text  # o traceback foi logado, só que mascarado


def test_sem_a_mascara_o_traceback_da_causa_traria_a_chave(monkeypatch, caplog, sem_redacao):
    """Caracterização: o motivo de a máscara existir (a causa encadeada vai ao log)."""
    caplog.set_level(logging.DEBUG)
    _falha_de_embeddings(monkeypatch)
    assert CHAVE in _registros(caplog)


def test_erro_interno_da_api_nao_ecoa_a_excecao_na_resposta(monkeypatch, caplog):
    def quebrar(**_kw):
        raise RuntimeError(f"falha inesperada com {CHAVE}")

    monkeypatch.setattr("app.api.v1.routers.adaptacoes.criar_job", quebrar)
    corpo = {
        "documento_titulo": "Manual de Teste",
        "documento_conteudo": "Texto de teste sobre APIs REST. " * 20,
        "perfil_destinatario": "Iniciante",
        "formato_saida": "Flashcards",
        "nicho_setor": "Geral",
        "nivel_detalhe": "Didatico",
    }
    resposta = TestClient(app, raise_server_exceptions=False).post("/api/v1/adaptacoes", json=corpo)

    assert resposta.status_code == 500
    assert resposta.json()["erro"]["codigo"] == "INTERNO"
    assert CHAVE not in resposta.text
    # O handler loga a exceção; a máscara de logs esconde a chave que veio nela.
    assert CHAVE not in _registros(caplog)
    assert "falha inesperada com ***" in caplog.text


@pytest.mark.parametrize("rota", ["/api/v1/health", "/api/v1/oci/status", "/openapi.json"])
def test_rotas_de_infraestrutura_nao_expoem_a_chave(rota):
    resposta = TestClient(app).get(rota)
    assert resposta.status_code == 200
    assert CHAVE not in resposta.text
    assert "google_api_key" not in json.dumps(resposta.json()).lower()


def test_respostas_dos_limites_novos_nao_expoem_configuracao(monkeypatch):
    """429, 413 e 503 trazem só o envelope, sem valores de configuração."""
    from app.core.limite_geracao import limitador

    limitador.limpar()
    monkeypatch.setattr(settings, "geracao_limite_por_minuto", 1)
    monkeypatch.setattr("app.api.v1.routers.adaptacoes.criar_job", lambda **kw: JobResposta(
        job_id="J", status="queued", iniciado_em="x", atualizado_em="x"))
    cliente = TestClient(app)
    corpo = {
        "documento_titulo": "Manual de Teste",
        "documento_conteudo": "Texto de teste sobre APIs REST. " * 20,
        "perfil_destinatario": "Iniciante",
        "formato_saida": "Flashcards",
        "nicho_setor": "Geral",
        "nivel_detalhe": "Didatico",
    }
    cliente.post("/api/v1/adaptacoes", json=corpo)
    resposta = cliente.post("/api/v1/adaptacoes", json=corpo)
    limitador.limpar()

    assert resposta.status_code == 429
    assert set(resposta.json()) == {"erro"}
    assert set(resposta.json()["erro"]) == {"codigo", "mensagem"}
    assert CHAVE not in resposta.text


# ── Revisão estática do código ────────────────────────────────────────────────

_CHAMADAS_DE_LOG = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def _chamadas_de_log():
    for caminho in sorted(APP_DIR.rglob("*.py")):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr in _CHAMADAS_DE_LOG
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id in {"logger", "logging", "log"}
            ):
                yield caminho, no


def test_nenhum_log_usa_segredos_da_configuracao():
    """Nenhuma chamada de log recebe ``settings`` inteiro, a chave ou o ambiente."""
    proibidos_atributos = {"google_api_key", "environ", "getenv", "oci_config_file"}
    encontrados = []
    for caminho, chamada in _chamadas_de_log():
        for no in ast.walk(chamada):
            if isinstance(no, ast.Attribute) and no.attr in proibidos_atributos:
                encontrados.append(f"{caminho.name}:{no.lineno} usa {no.attr}")
            if isinstance(no, ast.Name) and no.id in {"settings", "config", "chave"}:
                pai_e_atributo = any(
                    isinstance(outro, ast.Attribute) and outro.value is no
                    for outro in ast.walk(chamada)
                )
                if not pai_e_atributo:
                    encontrados.append(f"{caminho.name}:{no.lineno} passa {no.id} inteiro")
    assert encontrados == []


def test_chave_do_gemini_so_e_lida_do_ambiente_nos_adaptadores():
    """A chave é lida em um lugar por adaptador e nunca entra em mensagem de erro."""
    for nome in ("llm/gemini.py", "rag/embeddings.py"):
        arvore = ast.parse((APP_DIR / nome).read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, (ast.Raise,)) and no.exc is not None:
                for sub in ast.walk(no.exc):
                    if isinstance(sub, ast.Name) and sub.id == "chave":
                        pytest.fail(f"{nome}:{no.lineno} põe a chave em uma exceção")
