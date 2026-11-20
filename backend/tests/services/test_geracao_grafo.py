"""Geração em grafo (app/services/geracao_grafo.py) com provedor, RAG e OCI falsos, sem rede."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.llm import ErroAutenticacao, Mensagem, registrar_provedor
from app.models import ArmazenamentoOci
from app.rag.modelos import Trecho
from app.services import geracao_grafo, pipeline

TEXTO = (Path(__file__).resolve().parents[2] / "data" / "exemplos" / "http_apis_rest.md").read_text(encoding="utf-8")
PARAGRAFOS = [p for p in TEXTO.split("\n\n") if len(p) > 80]
FRASE_DO_DOCUMENTO = "cada mensagem precisa carregar tudo o que o servidor precisa para entendê-la"


def _flashcards(titulo, introducao, cartoes):
    return json.dumps({
        "tipo": "flashcards",
        "titulo": titulo,
        "introducao_contextualizada": introducao,
        "itens": [{"frente": f, "verso": v, "dica_didatica": None} for f, v in cartoes],
        "conceitos_chave": ["GET", "POST"],
    })


FIEL = _flashcards(
    "Métodos do protocolo HTTP",
    "Os métodos dizem ao servidor qual ação o cliente quer realizar.",
    [("GET", "GET busca um recurso sem alterá-lo."),
     ("POST", "POST cria um recurso novo e leva os dados no corpo da requisição."),
     ("DELETE", "DELETE remove o recurso.")],
)
MEDIO = _flashcards(
    "Métodos do protocolo HTTP",
    "Os métodos dizem ao servidor qual ação o cliente quer realizar.",
    [("GET", "GET busca um recurso sem alterá-lo."),
     ("Kubernetes", "Kubernetes agenda contêineres zorbaxianos em nós de um cluster elástico."),
     ("Helm", "Helm empacota gráficos zorbaxianos para implantação contínua em nuvem.")],
)
FRACO = _flashcards(
    "Orquestração zorbaxiana de contêineres",
    "Kubernetes agenda contêineres zorbaxianos em nós de um cluster elástico.",
    [("Pod", "Pod agrupa contêineres zorbaxianos que compartilham rede efêmera."),
     ("Helm", "Helm empacota gráficos zorbaxianos para implantação contínua em nuvem."),
     ("Kubelet", "Kubelet vigia contêineres zorbaxianos em cada nó elástico.")],
)


def _nota(resposta: str) -> float:
    conteudo = pipeline._parsear_conteudo(pipeline._extrair_json(resposta), "Flashcards")
    return pipeline._avaliar_qualidade(0.9, conteudo, TEXTO).ancoragem_fonte_score


class _Modelo:
    nome = "falso"
    roteiro: list = []
    prompts: list[str] = []

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        _Modelo.prompts.append(mensagens[0].conteudo)
        item = _Modelo.roteiro[min(len(_Modelo.prompts), len(_Modelo.roteiro)) - 1]
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def modelo(monkeypatch):
    _Modelo.roteiro = [FIEL]
    _Modelo.prompts = []
    registrar_provedor("falso-grafo", _Modelo)
    monkeypatch.setattr(settings, "llm_provider", "falso-grafo")
    monkeypatch.setattr(settings, "geracao_multiagente", True)
    monkeypatch.setattr(settings, "grafo_max_revisoes", 2)
    monkeypatch.setattr(settings, "grafo_limiar_ancoragem", 0.75)
    monkeypatch.setattr(settings, "grafo_max_simultaneos", 2)
    monkeypatch.setattr(settings, "llm_timeout_segundos", 120)
    monkeypatch.setattr(geracao_grafo, "_vagas", None)
    return _Modelo


@pytest.fixture
def rag(monkeypatch):
    """RAG falso: a consulta padrão devolve os 2 primeiros parágrafos; outras, os seguintes."""
    from app.rag import servico
    from app.services import oci

    consultas: list[str] = []
    falhas: list = []

    def indexar(**kw):
        kw["on_etapa"]("chunking")
        kw["on_etapa"]("embeddings")

    def recuperar(documento_id, consulta, k=4):
        consultas.append(consulta)
        if falhas:
            erro = falhas.pop(0)
            if erro is not None:
                raise erro
        inicio = 0 if consulta.startswith("Conteúdo educacional sobre") else 1
        return [Trecho(texto=p, indice=i, relevancia=0.8, documento_id=documento_id)
                for i, p in enumerate(PARAGRAFOS[inicio:inicio + 2], start=inicio)]

    monkeypatch.setattr(servico, "indexar_documento", indexar)
    monkeypatch.setattr(servico, "recuperar", recuperar)
    monkeypatch.setattr(oci, "fazer_upload", lambda pacote, objeto_id: ArmazenamentoOci(
        bucket="teste", objeto_id=objeto_id, status_upload="falha"))
    return {"consultas": consultas, "falhas": falhas}


def _executar(progresso=None, **kw):
    return pipeline.executar_pipeline(
        documento_id="doc-grafo", titulo="APIs REST", texto=TEXTO, origem="texto",
        nome_arquivo=None, tamanho_bytes=None, perfil="Desenvolvedor", formato="Flashcards",
        nicho="Geral", nivel="Tecnico",
        on_progresso=(lambda e, p, m: progresso.append((e, p, m))) if progresso is not None else None,
        **kw,
    )


def _prompt_da_passada_unica() -> str:
    return pipeline._montar_prompt(
        "APIs REST", PARAGRAFOS[0:2], "Desenvolvedor", "Flashcards", "Geral", "Tecnico"
    )


def test_respostas_de_teste_tem_a_ordem_de_ancoragem_esperada():
    assert _nota(FIEL) >= 0.75 > _nota(MEDIO) > _nota(FRACO)


# ── Laço ──────────────────────────────────────────────────────────────────────


def test_aprova_de_primeira_com_uma_escrita(modelo, rag):
    pacote = _executar()
    assert len(modelo.prompts) == 1
    assert modelo.prompts[0] == _prompt_da_passada_unica()  # a rodada 1 é a passada única
    assert rag["consultas"] == ["Conteúdo educacional sobre APIs REST para Desenvolvedor"]
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FIEL)


def test_aprova_na_segunda_rodada(modelo, rag):
    modelo.roteiro = [FRACO, FIEL]
    pacote = _executar()
    assert len(modelo.prompts) == 2
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FIEL)
    revisao = modelo.prompts[1]
    assert revisao.startswith(_prompt_da_passada_unica()[:200])
    bloco = revisao.split(pipeline._TITULO_REVISAO, 1)[1]
    assert "zorbaxianos" in bloco and "item" in bloco
    assert FRASE_DO_DOCUMENTO not in bloco  # o retorno não traz texto do documento
    # Busca dirigida com o texto do rascunho, nunca do documento, e trechos sem repetição.
    consulta = rag["consultas"][1]
    assert "zorbaxianos" in consulta and FRASE_DO_DOCUMENTO not in consulta
    assert revisao.count(PARAGRAFOS[1][:60]) == 1
    assert PARAGRAFOS[2][:60] in revisao


def test_esgota_as_rodadas_e_entrega_o_melhor_nao_o_ultimo(modelo, rag, caplog):
    modelo.roteiro = [FRACO, MEDIO, FRACO]
    with caplog.at_level(logging.INFO):
        pacote = _executar()
    assert len(modelo.prompts) == 3
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(MEDIO)
    assert pacote.conteudo_adaptado.itens[1].frente == "Kubernetes"
    assert "motivo=rodadas_esgotadas melhor_rodada=2" in caplog.text


def test_sem_progresso_para_cedo(modelo, rag, caplog):
    modelo.roteiro = [MEDIO, FRACO, FIEL]
    with caplog.at_level(logging.INFO):
        pacote = _executar()
    assert len(modelo.prompts) == 2
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(MEDIO)
    assert "motivo=sem_progresso" in caplog.text


def test_max_revisoes_zero_faz_uma_escrita(modelo, rag, monkeypatch):
    monkeypatch.setattr(settings, "grafo_max_revisoes", 0)
    modelo.roteiro = [FRACO, FIEL]
    pacote = _executar()
    assert len(modelo.prompts) == 1
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FRACO)  # não falha abaixo do limiar


def test_json_invalido_na_primeira_rodada_usa_a_repeticao(modelo, rag):
    modelo.roteiro = ["sem json", FIEL]
    pacote = _executar()
    assert len(modelo.prompts) == 2
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FIEL)


def test_json_invalido_numa_revisao_entrega_o_melhor(modelo, rag, caplog):
    modelo.roteiro = [FRACO, "sem json", "sem json", FIEL]
    with caplog.at_level(logging.INFO):
        pacote = _executar()
    assert len(modelo.prompts) == 3  # rodada 1 + as duas tentativas da revisão; sem fallback
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FRACO)
    assert "motivo=falha_na_revisao:RuntimeError" in caplog.text


# ── Fallback, cancelamento, prazo e vagas ─────────────────────────────────────


def _sem_grafo(monkeypatch, modelo, roteiro):
    monkeypatch.setattr(settings, "geracao_multiagente", False)
    modelo.roteiro, modelo.prompts = roteiro, []
    pacote = _executar()
    monkeypatch.setattr(settings, "geracao_multiagente", True)
    modelo.prompts = []
    return pacote


def test_excecao_num_no_cai_na_passada_unica_com_o_mesmo_resultado(modelo, rag, monkeypatch, caplog):
    esperado = _sem_grafo(monkeypatch, modelo, [FRACO])
    modelo.roteiro = [FRACO]
    rag["consultas"].clear()
    rag["falhas"].append(RuntimeError("falha no pesquisador"))
    with caplog.at_level(logging.INFO):
        pacote = _executar()
    assert pacote.conteudo_adaptado == esperado.conteudo_adaptado
    assert pacote.avaliacao_qualidade == esperado.avaliacao_qualidade
    assert pacote.metadados.conceitos_chave == esperado.metadados.conceitos_chave
    assert len(modelo.prompts) == 1 and modelo.prompts[0] == _prompt_da_passada_unica()
    assert "passada única (fallback)" in caplog.text


def test_excecao_sem_prazo_para_o_fallback_propaga(modelo, rag, monkeypatch):
    monkeypatch.setattr(geracao_grafo, "_relogio", lambda: 1000.0)
    rag["falhas"].append(RuntimeError("falha no pesquisador"))
    with pytest.raises(RuntimeError, match="falha no pesquisador"):
        _executar(prazo=1000.0 + 60)  # LLM_TIMEOUT_SEGUNDOS=120 não cabe
    assert modelo.prompts == []


def test_erro_de_configuracao_nao_faz_fallback(modelo, rag):
    modelo.roteiro = [ErroAutenticacao("401")]
    with pytest.raises(RuntimeError) as erro:
        _executar()
    assert str(erro.value) == pipeline._MSG_CONFIGURACAO
    assert len(modelo.prompts) == 1


def test_cancelamento_no_meio_interrompe_sem_fallback(modelo, rag):
    modelo.roteiro = [FRACO, FIEL]
    verificacoes = []

    def verificar():
        verificacoes.append(1)
        if len(modelo.prompts) >= 1 and len(verificacoes) > 4:
            raise InterruptedError("Cancelado pelo usuário.")

    with pytest.raises(InterruptedError):
        _executar(verificar_interrupcao=verificar)
    assert len(modelo.prompts) == 1


def test_prazo_que_nao_comporta_outra_rodada(modelo, rag, monkeypatch, caplog):
    monkeypatch.setattr(geracao_grafo, "_relogio", lambda: 1000.0)
    modelo.roteiro = [FRACO, FIEL]
    with caplog.at_level(logging.INFO):
        pacote = _executar(prazo=1000.0 + 100)
    assert len(modelo.prompts) == 1
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FRACO)
    assert "motivo=prazo" in caplog.text


def test_sem_vaga_vai_para_a_passada_unica(modelo, rag, monkeypatch, caplog):
    monkeypatch.setattr(settings, "grafo_max_simultaneos", 1)
    vaga = geracao_grafo._semaforo()
    assert vaga.acquire(blocking=False)
    try:
        modelo.roteiro = [FRACO, FIEL]
        with caplog.at_level(logging.INFO):
            pacote = _executar()
    finally:
        vaga.release()
    assert len(modelo.prompts) == 1
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FRACO)
    assert "sem vaga (GRAFO_MAX_SIMULTANEOS=1)" in caplog.text
    assert "Grafo: no=" not in caplog.text
    assert vaga.acquire(blocking=False)  # a vaga não foi consumida pela passada única
    vaga.release()


def test_vaga_e_devolvida_depois_do_grafo(modelo, rag, monkeypatch):
    monkeypatch.setattr(settings, "grafo_max_simultaneos", 1)
    _executar()
    rag["falhas"].append(RuntimeError("x"))
    _executar()  # com fallback
    vaga = geracao_grafo._semaforo()
    assert vaga.acquire(blocking=False)
    vaga.release()


# ── Configuração desligada e prompt ───────────────────────────────────────────


def test_desligado_nao_usa_o_grafo(modelo, rag, monkeypatch):
    monkeypatch.setattr(settings, "geracao_multiagente", False)

    def proibido(**_kw):
        raise AssertionError("o grafo não deveria rodar")

    monkeypatch.setattr(geracao_grafo, "executar_pipeline_grafo", proibido)
    modelo.roteiro = [FRACO, FIEL]
    progresso = []
    _executar(progresso)
    assert len(modelo.prompts) == 1 and modelo.prompts[0] == _prompt_da_passada_unica()
    assert [(e, p) for e, p, _m in progresso] == [
        ("chunking", 25), ("embeddings", 45), ("gerando", 55), ("gerando", 65),
        ("revisando", 82), ("armazenando", 100),
    ]


def test_prompt_sem_retorno_e_identico_ao_original():
    argumentos = ("APIs REST", ["trecho um", "trecho dois"], "Gestor", "Quiz", "Saude", "Executivo")
    original = (
        f"Você é um especialista em educação técnica.\n"
        f"Público-alvo: {pipeline._PERFIL_DESC['Gestor']}.\n"
        f"Setor / nicho: Saude.\n"
        f"Tom: {pipeline._NIVEL_DESC['Executivo']}.\n\n"
        f"DOCUMENTO: APIs REST\n\n"
        f"TRECHOS RELEVANTES DO DOCUMENTO:\ntrecho um\n\n---\n\ntrecho dois\n\n"
        f"TAREFA:\n{pipeline._INSTRUCOES_FORMATO['Quiz']}\n{pipeline._INSTRUCAO_CONCEITOS}"
    )
    assert pipeline._montar_prompt(*argumentos) == original
    assert pipeline._montar_prompt(*argumentos, retorno_revisor=None) == original
    assert pipeline._montar_prompt(*argumentos, retorno_revisor="") == original
    com_retorno = pipeline._montar_prompt(*argumentos, retorno_revisor="- item 2: termos x")
    assert com_retorno.startswith(original) and "- item 2: termos x" in com_retorno


# ── Progresso e log ───────────────────────────────────────────────────────────


ORDEM_ETAPAS = ["extraindo", "chunking", "embeddings", "gerando", "revisando", "armazenando"]


def _nao_decrescente(etapas):
    posicoes = [ORDEM_ETAPAS.index(e) for e in etapas]
    return posicoes == sorted(posicoes)


def test_involucro_nao_deixa_a_etapa_voltar():
    recebidos = []
    progresso = geracao_grafo._ProgressoMonotonico(lambda e, p, m: recebidos.append((e, p, m)))
    progresso("gerando", 55, "um")
    progresso("revisando", 85, "dois")
    progresso("gerando", 60, "tres")
    progresso("armazenando", 100, "quatro")
    assert recebidos == [
        ("gerando", 55, "um"), ("revisando", 85, "dois"), ("revisando", 85, "tres"), ("armazenando", 100, "quatro"),
    ]


def test_ordem_das_etapas_e_a_do_enum():
    from typing import get_args

    from app.models import EtapaJob

    assert list(get_args(EtapaJob)) == ORDEM_ETAPAS
    assert list(geracao_grafo._ORDEM_ETAPAS) == ORDEM_ETAPAS


def test_percentual_monotonico_e_etapas_existentes(modelo, rag):
    modelo.roteiro = [FRACO, MEDIO, FRACO]
    progresso = []
    _executar(progresso)
    percentuais = [p for _e, p, _m in progresso]
    assert percentuais == sorted(percentuais)
    assert {e for e, _p, _m in progresso} <= {"chunking", "embeddings", "gerando", "revisando", "armazenando"}
    mensagens = [m for _e, _p, m in progresso]
    assert "Revisando fidelidade (rodada 2 de 3)..." in mensagens
    assert "Revisando fidelidade (rodada 3 de 3)..." in mensagens
    # As etapas só avançam: depois do primeiro "revisando", as revisões saem como "revisando".
    assert _nao_decrescente([e for e, _p, _m in progresso])
    assert [e for e, _p, m in progresso if "(rodada 2 de 3)" in m] == ["revisando"] * 3
    for texto in ("Buscando trechos para a revisão (rodada 2 de 3)...",
                  "Reescrevendo o material (rodada 2 de 3)...",
                  "Buscando trechos para a revisão (rodada 3 de 3)...",
                  "Reescrevendo o material (rodada 3 de 3)..."):
        assert texto in mensagens


def test_falha_do_pesquisador_numa_revisao_entrega_o_melhor(modelo, rag, caplog):
    rag["falhas"].extend([None, RuntimeError("falha na revisão")])
    modelo.roteiro = [FRACO, FIEL]
    progresso = []
    with caplog.at_level(logging.INFO):
        pacote = _executar(progresso)
    assert len(modelo.prompts) == 1
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FRACO)
    assert "motivo=falha_na_revisao:RuntimeError" in caplog.text
    percentuais = [p for _e, p, _m in progresso]
    assert percentuais == sorted(percentuais)


def test_percentual_nao_volta_no_fallback(modelo, rag, monkeypatch):
    original = pipeline._avaliar_qualidade
    chamadas = []

    def falha_no_critico(*args):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise ValueError("falha no crítico")
        return original(*args)

    monkeypatch.setattr(pipeline, "_avaliar_qualidade", falha_no_critico)
    modelo.roteiro = [FIEL]
    progresso = []
    pacote = _executar(progresso)
    assert pacote.avaliacao_qualidade.ancoragem_fonte_score == _nota(FIEL)
    percentuais = [p for _e, p, _m in progresso]
    assert 85 in percentuais  # o crítico chegou a anunciar a rodada antes de falhar
    assert percentuais == sorted(percentuais)  # a passada única do fallback não voltou para 55
    etapas = [e for e, _p, _m in progresso]
    assert _nao_decrescente(etapas)  # nem a etapa voltou para "gerando"
    assert etapas[-2:] == ["revisando", "armazenando"]
    assert len(modelo.prompts) == 2  # grafo + fallback


def test_log_nao_tem_conteudo(modelo, rag, caplog):
    modelo.roteiro = [FRACO, MEDIO, FRACO]
    with caplog.at_level(logging.DEBUG):
        _executar()
        rag["falhas"].append(RuntimeError("falha"))
        _executar()  # fallback
    assert "Grafo: no=critico" in caplog.text and "Grafo: fim" in caplog.text
    proibidos = [FRASE_DO_DOCUMENTO, "zorbaxianos", "Kubernetes agenda", "GET busca um recurso",
                 *[p[:50] for p in PARAGRAFOS]]
    for trecho in proibidos:
        assert trecho not in caplog.text, trecho


def test_o_que_nao_vai_para_o_fallback():
    from app.workers.job_worker import PrazoExcedido

    assert geracao_grafo._sem_fallback(InterruptedError("cancelado"))
    assert geracao_grafo._sem_fallback(PrazoExcedido("prazo"))
    assert geracao_grafo._sem_fallback(RuntimeError(pipeline._MSG_CONFIGURACAO))
    try:
        raise RuntimeError("embrulho") from ErroAutenticacao("401")
    except RuntimeError as embrulhado:
        assert geracao_grafo._sem_fallback(embrulhado)
    assert not geracao_grafo._sem_fallback(RuntimeError("O modelo demorou demais"))
    assert not geracao_grafo._sem_fallback(ValueError("x"))


# ── Funções do crítico ────────────────────────────────────────────────────────


def test_itens_fracos_e_retorno_usam_so_o_rascunho():
    conteudo = pipeline._parsear_conteudo(pipeline._extrair_json(MEDIO), "Flashcards")
    fracos = geracao_grafo.itens_fracos(conteudo, TEXTO, 0.75)
    assert [i for i, _item, _t in fracos] == [3, 4]  # os dois cartões inventados
    retorno = geracao_grafo.montar_retorno(fracos)
    assert retorno.startswith("- item 2: termos que não aparecem nos trechos:")
    assert "zorbaxianos" in retorno and "GET" not in retorno
    assert FRASE_DO_DOCUMENTO not in retorno


def test_juntar_trechos_sem_repetir_e_com_teto():
    def t(i):
        return Trecho(texto=f"trecho {i}", indice=i, relevancia=0.5, documento_id="d")

    juntos = geracao_grafo.juntar_trechos([t(0), t(1)], [t(1), t(2), t(0), t(3)])
    assert [x.indice for x in juntos] == [0, 1, 2, 3]
    grandes = geracao_grafo.juntar_trechos([t(i) for i in range(10)], [t(i) for i in range(5, 30)])
    assert len(grandes) == geracao_grafo.MAX_TRECHOS_CONTEXTO


# ── Configuração ──────────────────────────────────────────────────────────────

VARIAVEIS = ["GERACAO_MULTIAGENTE", "GRAFO_MAX_REVISOES", "GRAFO_LIMIAR_ANCORAGEM", "GRAFO_MAX_SIMULTANEOS"]


def _settings(monkeypatch, **variaveis) -> Settings:
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)
    for nome, valor in variaveis.items():
        monkeypatch.setenv(nome, valor)
    return Settings(_env_file=None)


def test_padroes_da_geracao_multiagente(monkeypatch):
    s = _settings(monkeypatch)
    assert (s.geracao_multiagente, s.grafo_max_revisoes, s.grafo_limiar_ancoragem, s.grafo_max_simultaneos) == (
        False, 2, 0.75, 2,
    )


def test_vazio_vale_o_padrao(monkeypatch):
    s = _settings(monkeypatch, **{nome: "" for nome in VARIAVEIS})
    assert (s.geracao_multiagente, s.grafo_max_revisoes, s.grafo_limiar_ancoragem, s.grafo_max_simultaneos) == (
        False, 2, 0.75, 2,
    )


def test_valores_configurados(monkeypatch):
    s = _settings(monkeypatch, GERACAO_MULTIAGENTE="true", GRAFO_MAX_REVISOES="0",
                  GRAFO_LIMIAR_ANCORAGEM="0.9", GRAFO_MAX_SIMULTANEOS="4")
    assert (s.geracao_multiagente, s.grafo_max_revisoes, s.grafo_limiar_ancoragem, s.grafo_max_simultaneos) == (
        True, 0, 0.9, 4,
    )


@pytest.mark.parametrize(
    "variavel,valor",
    [("GRAFO_MAX_REVISOES", "3"), ("GRAFO_MAX_REVISOES", "-1"), ("GRAFO_LIMIAR_ANCORAGEM", "1.5"),
     ("GRAFO_LIMIAR_ANCORAGEM", "-0.1"), ("GRAFO_MAX_SIMULTANEOS", "0"), ("GERACAO_MULTIAGENTE", "talvez")],
)
def test_valores_invalidos(monkeypatch, variavel, valor):
    with pytest.raises(ValidationError) as erro:
        _settings(monkeypatch, **{variavel: valor})
    assert variavel.lower() in str(erro.value)


# ── Detalhes (executar_grafo_com_detalhes, usados pela medição) ──────────────


def _com_detalhes(**kw):
    return geracao_grafo.executar_grafo_com_detalhes(
        documento_id="doc-grafo", titulo="APIs REST", texto=TEXTO, perfil="Desenvolvedor",
        formato="Flashcards", nicho="Geral", nivel="Tecnico", **kw,
    )


def test_detalhes_por_rodada(modelo, rag):
    modelo.roteiro = [FRACO, MEDIO, FRACO]
    resultado, detalhes = _com_detalhes()
    assert [r.rodada for r in detalhes.rascunhos] == [1, 2, 3]
    assert [r.nota for r in detalhes.rascunhos] == [_nota(FRACO), _nota(MEDIO), _nota(FRACO)]
    assert detalhes.motivo_parada == "rodadas_esgotadas"
    assert detalhes.melhor_rodada == 2
    assert resultado is detalhes.rascunhos[1].resultado
    assert (detalhes.chamadas_total, detalhes.chamadas_rodada1) == (3, 1)
    assert 0 <= detalhes.duracao_rodada1_s <= detalhes.duracao_total_s
    # A rodada 1 é a passada única: mesmo prompt.
    assert modelo.prompts[0] == _prompt_da_passada_unica()


def test_detalhes_contam_a_repeticao_por_json_invalido_na_rodada1(modelo, rag):
    modelo.roteiro = ["sem json", FIEL]
    _resultado, detalhes = _com_detalhes()
    assert (detalhes.chamadas_total, detalhes.chamadas_rodada1, len(detalhes.rascunhos)) == (2, 2, 1)
    assert detalhes.motivo_parada == "aprovado"


def test_detalhes_aceitam_limiar_revisoes_recuperacao_e_provedor_proprios(modelo, rag):
    class Proprio:
        nome = "proprio"
        prompts: list = []

        def gerar(self, mensagens, *, timeout_segundos):
            Proprio.prompts.append(mensagens[0].conteudo)
            return FRACO

    consultas = []

    def recuperar(documento_id, consulta, k=4):
        consultas.append((documento_id, consulta, k))
        return [Trecho(texto=PARAGRAFOS[0], indice=0, relevancia=1.0, documento_id=documento_id)]

    _resultado, detalhes = _com_detalhes(limiar=0.99, max_revisoes=1, recuperar=recuperar, provedor=Proprio())
    assert modelo.prompts == [] and rag["consultas"] == []  # nada do provedor nem do RAG configurados
    assert len(Proprio.prompts) == 2 and len(consultas) == 2
    assert detalhes.motivo_parada == "rodadas_esgotadas"  # max_revisoes=1: 2 rodadas
    assert len(detalhes.rascunhos) == 2


def test_detalhes_sao_imutaveis_e_erros_sobem_sem_fallback(modelo, rag):
    import dataclasses

    _resultado, detalhes = _com_detalhes()
    with pytest.raises(dataclasses.FrozenInstanceError):
        detalhes.motivo_parada = "outro"
    rag["falhas"].append(RuntimeError("falha no pesquisador"))
    modelo.prompts = []
    with pytest.raises(RuntimeError, match="falha no pesquisador"):
        _com_detalhes()
    assert modelo.prompts == []
