"""Geração em grafo (LangGraph): roteador, pesquisador, redator e crítico com revisões.

Ligada por ``GERACAO_MULTIAGENTE``. O fluxo:

    roteador -> pesquisador -> redator -> crítico -> fim (aprovado ou parada)
                     ^                        |
                     +------- revisar --------+

- **Roteador** (sem LLM): monta o plano com formato, perfil e ``tem_diagrama``
  (sempre ``False`` por enquanto; reserva para a etapa de diagramas).
- **Pesquisador**: na rodada 1, a mesma recuperação da passada única
  (consulta padrão, k=6). Nas revisões, uma busca dirigida com o texto dos
  itens mal ancorados do rascunho, juntando os trechos novos aos já usados,
  sem repetir e com teto de ``MAX_TRECHOS_CONTEXTO``.
- **Redator**: ``pipeline._montar_prompt`` e ``_gerar_conteudo`` (com a
  repetição por JSON inválido), pelo ``ProvedorLLM`` da geração. Na rodada 1 o
  prompt é o da passada única; nas revisões ganha o retorno do crítico
  (itens fracos e termos do próprio rascunho que não aparecem na fonte, nunca
  texto do documento).
- **Crítico** (sem LLM): a mesma avaliação que grava ``ancoragem_fonte_score``
  (``pipeline._avaliar_qualidade``). Aprova com ancoragem >= limiar; senão para
  quando as revisões acabam, quando a ancoragem não melhora ou quando o prazo
  do job não comporta outra rodada.

Entrega sempre o rascunho de maior ancoragem, nunca falha só por não chegar
ao limiar. Qualquer falha do grafo cai na passada única (exceto cancelamento,
prazo e erro de configuração), assim como a falta de vaga
(``GRAFO_MAX_SIMULTANEOS``). O log tem só nomes, contagens, tempos, notas e
tipos de erro: nada do documento, do rascunho nem das consultas.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypedDict, get_args

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.llm import limites_da_geracao
from app.llm.erros import ErroConfiguracao
from app.models import EtapaJob
from app.services import ancoragem, pipeline

logger = logging.getLogger(__name__)

MAX_ITENS_FRACOS = 5  # itens indicados no retorno do crítico
MIN_ITENS_FRACOS = 3  # se nenhum item fica abaixo do limiar, os mais fracos mesmo assim
MAX_TERMOS_POR_ITEM = 8
MAX_CARACTERES_TERMO = 40
MAX_CARACTERES_CONSULTA = 1_000  # consulta dirigida (texto dos itens do rascunho)
K_REVISAO = 6  # trechos buscados por revisão
MAX_TRECHOS_CONTEXTO = 12  # teto de trechos no prompt: o dobro da primeira rodada
LIMITE_RECURSAO = 25  # passos do LangGraph; 3 rodadas usam 10

# Percentual por rodada: (pesquisador, redator, crítico). A rodada 1 repete a
# passada única (55 e 65; 82 quando chega a primeira resposta).
_PERCENTUAL = {1: (55, 65, 85), 2: (86, 88, 90), 3: (92, 94, 96)}

# Relógio monotônico (o mesmo do prazo do job); os testes trocam.
_relogio: Callable[[], float] = time.monotonic

Progresso = Callable[[str, int, str], None]


# ── Vagas ─────────────────────────────────────────────────────────────────────

_trava_vagas = threading.Lock()
_vagas: tuple[int, threading.BoundedSemaphore] | None = None


def _semaforo() -> threading.BoundedSemaphore:
    """Semáforo de ``GRAFO_MAX_SIMULTANEOS``, recriado se a configuração mudar."""
    global _vagas
    with _trava_vagas:
        total = settings.grafo_max_simultaneos
        if _vagas is None or _vagas[0] != total:
            _vagas = (total, threading.BoundedSemaphore(total))
        return _vagas[1]


# ── Apoio ─────────────────────────────────────────────────────────────────────


# Ordem das etapas do job: a do enum EtapaJob, a mesma do job_worker e do
# ETAPAS do frontend (frontend/src/lib/constants.ts).
_ORDEM_ETAPAS = {etapa: posicao for posicao, etapa in enumerate(get_args(EtapaJob))}


class _ProgressoMonotonico:
    """Repassa o progresso sem nunca deixar a etapa nem o percentual voltarem.

    Uma etapa anterior à mais avançada já emitida (o "gerando" das revisões e
    do fallback depois de um "revisando") sai como a mais avançada, com a
    mensagem de quem chamou.
    """

    def __init__(self, progresso: Progresso):
        self._progresso = progresso
        self.ultimo = 0
        self.etapa: str | None = None

    def __call__(self, etapa: str, percentual: int, mensagem: str) -> None:
        if self.etapa is None or _ORDEM_ETAPAS.get(etapa, -1) > _ORDEM_ETAPAS.get(self.etapa, -1):
            self.etapa = etapa
        self.ultimo = max(self.ultimo, percentual)
        self._progresso(self.etapa, self.ultimo, mensagem)


class _ProvedorContado:
    """Conta as chamadas ao provedor (para saber se o JSON veio válido na primeira)."""

    def __init__(self, base):
        self.base = base
        self.nome = base.nome
        self.chamadas = 0

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        self.chamadas += 1
        return self.base.gerar(mensagens, timeout_segundos=timeout_segundos)


@dataclass(frozen=True)
class Rascunho:
    rodada: int
    resultado: pipeline.ResultadoGeracao
    nota: float


class EstadoGrafo(TypedDict, total=False):
    plano: dict
    rodada: int
    trechos: list  # app.rag.modelos.Trecho
    retorno_revisor: str | None
    consulta: str | None
    pendente: tuple  # (conteudo, conceitos_do_llm, textos_trechos, relevancia_media)
    rascunhos: list[Rascunho]
    motivo_parada: str | None


def _e_configuracao(exc: BaseException) -> bool:
    """Erro de chave ou configuração (o pipeline o embrulha em RuntimeError)."""
    atual: BaseException | None = exc
    vistos = 0
    while atual is not None and vistos < 10:
        if isinstance(atual, ErroConfiguracao):
            return True
        atual = atual.__cause__ or atual.__context__
        vistos += 1
    return isinstance(exc, RuntimeError) and str(exc) == pipeline._MSG_CONFIGURACAO


def _sem_fallback(exc: BaseException) -> bool:
    """Cancelamento, prazo do job e configuração não vão para a passada única."""
    from app.workers.job_worker import PrazoExcedido  # importação tardia: evita ciclo

    return isinstance(exc, (InterruptedError, PrazoExcedido)) or _e_configuracao(exc)


def _cabe_uma_chamada(prazo: float | None) -> bool:
    return prazo is None or _relogio() + settings.llm_timeout_segundos <= prazo


def _log_no(no: str, rodada: int, inicio: float, **campos) -> None:
    extras = " ".join(f"{chave}={valor}" for chave, valor in campos.items())
    logger.info("Grafo: no=%s rodada=%d duracao=%.2fs %s", no, rodada, _relogio() - inicio, extras)


# ── Retorno do crítico ────────────────────────────────────────────────────────

_PALAVRA = re.compile(r"[^\W\d_][\w-]*|\d+")


def termos_ausentes(item: str, fonte: set[str]) -> list[str]:
    """Palavras relevantes do item cuja raiz não aparece na fonte (na grafia do rascunho)."""
    vistos: dict[str, str] = {}
    for palavra in _PALAVRA.findall(item):
        raizes = ancoragem.termos(palavra)
        if raizes and not (raizes & fonte):
            vistos.setdefault(palavra.casefold(), palavra[:MAX_CARACTERES_TERMO])
        if len(vistos) >= MAX_TERMOS_POR_ITEM:
            break
    return list(vistos.values())


def _rotulo(indice: int) -> str:
    return {0: "título", 1: "introdução"}.get(indice, f"item {indice - 1}")


def itens_fracos(conteudo, texto_fonte: str, limiar: float) -> list[tuple[int, str, list[str]]]:
    """(índice em ``itens_medidos``, texto do item, termos ausentes) dos itens mais fracos."""
    fonte = ancoragem.vocabulario_da_fonte(texto_fonte)
    notas = []
    for indice, item in enumerate(ancoragem.itens_medidos(conteudo)):
        cobertura = ancoragem.cobertura(item, fonte)
        if cobertura is not None:
            notas.append((ancoragem.nota_do_item(cobertura), indice, item))
    notas.sort(key=lambda n: (n[0], n[1]))
    abaixo = [n for n in notas if n[0] < limiar]
    escolhidos = (abaixo or notas[:MIN_ITENS_FRACOS])[:MAX_ITENS_FRACOS]
    return [(i, item, termos_ausentes(item, fonte)) for _n, i, item in sorted(escolhidos, key=lambda n: n[1])]


def montar_retorno(fracos: list[tuple[int, str, list[str]]]) -> str:
    """Bloco curto para o redator: só rótulos dos itens e palavras do próprio rascunho."""
    linhas = []
    for indice, _item, termos in fracos:
        if termos:
            linhas.append(f"- {_rotulo(indice)}: termos que não aparecem nos trechos: {', '.join(termos)}")
        else:
            linhas.append(f"- {_rotulo(indice)}: pouco apoio nos trechos")
    return "\n".join(linhas)


def consulta_dirigida(fracos: list[tuple[int, str, list[str]]]) -> str:
    return " ".join(item for _i, item, _t in fracos)[:MAX_CARACTERES_CONSULTA]


def juntar_trechos(usados: list, novos: list) -> list:
    """Os já usados primeiro, depois os novos que ainda não estavam, até o teto."""
    vistos = {(t.indice, t.texto) for t in usados}
    juntos = list(usados)
    for trecho in novos:
        if len(juntos) >= MAX_TRECHOS_CONTEXTO:
            break
        chave = (trecho.indice, trecho.texto)
        if chave not in vistos:
            vistos.add(chave)
            juntos.append(trecho)
    return juntos[:MAX_TRECHOS_CONTEXTO]


# ── Grafo ─────────────────────────────────────────────────────────────────────


@dataclass
class _Execucao:
    documento_id: str
    titulo: str
    texto: str
    perfil: str
    formato: str
    nicho: str
    nivel: str
    progresso: _ProgressoMonotonico
    prazo: float | None
    verificar_interrupcao: Callable[[], None] | None
    limiar: float
    max_revisoes: int
    recuperar: Callable | None = None  # padrão: rag.servico.recuperar
    provedor_base: object | None = None  # padrão: o provedor da geração (obter_provedor)
    provedor: _ProvedorContado | None = None
    inicio: float = 0.0
    chamadas_rodada1: int = 0
    duracao_rodada1: float | None = None

    @property
    def total_rodadas(self) -> int:
        return 1 + self.max_revisoes

    def verificar(self) -> None:
        if self.verificar_interrupcao:
            self.verificar_interrupcao()

    def cabe_outra_rodada(self) -> bool:
        return _cabe_uma_chamada(self.prazo)


def _tolerar_na_revisao(no: str, rodada: int, exc: Exception) -> dict:
    """Falha numa revisão: para e entrega o melhor rascunho que já existe."""
    if rodada == 1 or _sem_fallback(exc):
        raise exc
    logger.warning("Grafo: no=%s rodada=%d falhou (%s); entregando o melhor rascunho.",
                   no, rodada, type(exc).__name__)
    return {"motivo_parada": f"falha_na_revisao:{type(exc).__name__}"}


def _montar_grafo(ex: _Execucao):
    from app.rag import servico as rag_servico  # importação tardia, como no pipeline

    def buscar(**kw):
        return (ex.recuperar or rag_servico.recuperar)(**kw)

    def roteador(_estado: EstadoGrafo) -> dict:
        inicio = _relogio()
        ex.verificar()
        plano = {"formato": ex.formato, "perfil": ex.perfil, "tem_diagrama": False}
        _log_no("roteador", 1, inicio, formato=ex.formato, perfil=ex.perfil, tem_diagrama=False)
        return {"plano": plano, "rodada": 1, "trechos": [], "rascunhos": [],
                "retorno_revisor": None, "consulta": None, "motivo_parada": None}

    def pesquisador(estado: EstadoGrafo) -> dict:
        inicio = _relogio()
        rodada = estado["rodada"]
        ex.verificar()
        try:
            if rodada == 1:
                ex.progresso("gerando", 55, "Recuperando trechos relevantes...")
                trechos = buscar(
                    documento_id=ex.documento_id, consulta=pipeline._consulta_padrao(ex.titulo, ex.perfil), k=6
                )
            else:
                ex.progresso("gerando", _PERCENTUAL[rodada][0],
                             f"Buscando trechos para a revisão (rodada {rodada} de {ex.total_rodadas})...")
                novos = buscar(documento_id=ex.documento_id, consulta=estado["consulta"], k=K_REVISAO)
                trechos = juntar_trechos(estado["trechos"], novos)
        except Exception as exc:
            return _tolerar_na_revisao("pesquisador", rodada, exc)
        _log_no("pesquisador", rodada, inicio, trechos=len(trechos),
                caracteres=sum(len(t.texto) for t in trechos))
        return {"trechos": trechos}

    def redator(estado: EstadoGrafo) -> dict:
        inicio = _relogio()
        rodada = estado["rodada"]
        ex.verificar()
        if rodada == 1:
            ex.progresso("gerando", 65, "Redigindo material didático...")
            avisar = lambda: ex.progresso("revisando", 82, "Revisando fidelidade...")  # noqa: E731
        else:
            ex.progresso("gerando", _PERCENTUAL[rodada][1],
                         f"Reescrevendo o material (rodada {rodada} de {ex.total_rodadas})...")
            avisar = lambda: None  # noqa: E731
        textos = [t.texto for t in estado["trechos"]]
        prompt = pipeline._montar_prompt(
            ex.titulo, textos, ex.perfil, ex.formato, ex.nicho, ex.nivel,
            retorno_revisor=estado.get("retorno_revisor"),
        )
        if ex.provedor is None:
            ex.provedor = _ProvedorContado(ex.provedor_base or pipeline._obter_provedor_da_geracao())
        antes = ex.provedor.chamadas
        try:
            with limites_da_geracao(ex.prazo, ex.verificar_interrupcao):
                _texto, conteudo, conceitos = pipeline._gerar_conteudo(
                    ex.provedor, prompt, ex.formato, avisar_revisao=avisar
                )
        except Exception as exc:
            _log_no("redator", rodada, inicio, caracteres_prompt=len(prompt),
                    chamadas=ex.provedor.chamadas - antes, erro=type(exc).__name__)
            return _tolerar_na_revisao("redator", rodada, exc)
        chamadas = ex.provedor.chamadas - antes
        _log_no("redator", rodada, inicio, trechos=len(textos), caracteres_prompt=len(prompt),
                chamadas=chamadas, json_valido_na_primeira=chamadas == 1)
        relevancia = pipeline._relevancia_media(estado["trechos"])
        return {"pendente": (conteudo, conceitos, textos, relevancia)}

    def critico(estado: EstadoGrafo) -> dict:
        inicio = _relogio()
        rodada = estado["rodada"]
        ex.verificar()
        ex.progresso("revisando", _PERCENTUAL[rodada][2],
                     f"Revisando fidelidade (rodada {rodada} de {ex.total_rodadas})...")
        conteudo, conceitos, textos, relevancia = estado["pendente"]
        avaliacao = pipeline._avaliar_qualidade(relevancia, conteudo, ex.texto)
        nota = avaliacao.ancoragem_fonte_score
        rascunhos = [*estado["rascunhos"],
                     Rascunho(rodada, pipeline.ResultadoGeracao(conteudo, conceitos, avaliacao, textos), nota)]
        if rodada == 1:  # a rodada 1 é a passada única: guardada à parte para a medição
            ex.chamadas_rodada1 = ex.provedor.chamadas if ex.provedor else 0
            ex.duracao_rodada1 = _relogio() - ex.inicio
        atualizacao: dict = {"rascunhos": rascunhos}
        if nota >= ex.limiar:
            atualizacao["motivo_parada"] = "aprovado"
        elif rodada >= ex.total_rodadas:
            atualizacao["motivo_parada"] = "rodadas_esgotadas"
        elif len(rascunhos) >= 2 and nota <= rascunhos[-2].nota:
            atualizacao["motivo_parada"] = "sem_progresso"
        elif not ex.cabe_outra_rodada():
            atualizacao["motivo_parada"] = "prazo"
        else:
            fracos = itens_fracos(conteudo, ex.texto, ex.limiar)
            atualizacao.update(rodada=rodada + 1, retorno_revisor=montar_retorno(fracos),
                               consulta=consulta_dirigida(fracos))
        _log_no("critico", rodada, inicio, ancoragem=f"{nota:.4f}", clareza=avaliacao.clareza_pedagogica,
                decisao=atualizacao.get("motivo_parada") or "revisar")
        return atualizacao

    def depois_da_busca(estado: EstadoGrafo) -> str:
        return "fim" if estado.get("motivo_parada") else "redator"

    def depois_da_redacao(estado: EstadoGrafo) -> str:
        return "fim" if estado.get("motivo_parada") else "critico"

    def depois_da_critica(estado: EstadoGrafo) -> str:
        return "fim" if estado.get("motivo_parada") else "revisar"

    grafo = StateGraph(EstadoGrafo)
    grafo.add_node("roteador", roteador)
    grafo.add_node("pesquisador", pesquisador)
    grafo.add_node("redator", redator)
    grafo.add_node("critico", critico)
    grafo.add_edge(START, "roteador")
    grafo.add_edge("roteador", "pesquisador")
    grafo.add_conditional_edges("pesquisador", depois_da_busca, {"redator": "redator", "fim": END})
    grafo.add_conditional_edges("redator", depois_da_redacao, {"critico": "critico", "fim": END})
    grafo.add_conditional_edges("critico", depois_da_critica, {"revisar": "pesquisador", "fim": END})
    return grafo.compile()


@dataclass(frozen=True)
class DetalhesGrafo:
    """O que aconteceu numa execução do grafo (para a medição; sem texto no log)."""

    rascunhos: tuple[Rascunho, ...]  # um por rodada, na ordem
    motivo_parada: str | None
    melhor_rodada: int
    chamadas_total: int
    chamadas_rodada1: int
    duracao_total_s: float
    duracao_rodada1_s: float | None


def _executar_grafo(ex: _Execucao) -> tuple[pipeline.ResultadoGeracao, DetalhesGrafo]:
    ex.inicio = inicio = _relogio()
    final = _montar_grafo(ex).invoke({}, {"recursion_limit": LIMITE_RECURSAO})
    rascunhos: list[Rascunho] = final.get("rascunhos") or []
    if not rascunhos:  # só acontece se a revisão falhar sem rascunho, o que a rodada 1 impede
        raise RuntimeError(pipeline._MSG_RESPOSTA_INVALIDA)
    melhor = max(rascunhos, key=lambda r: (r.nota, -r.rodada))
    chamadas = ex.provedor.chamadas if ex.provedor else 0
    duracao = _relogio() - inicio
    logger.info(
        "Grafo: fim rodadas=%d motivo=%s melhor_rodada=%d ancoragem=%.4f chamadas=%d duracao=%.2fs",
        len(rascunhos), final.get("motivo_parada"), melhor.rodada, melhor.nota, chamadas, duracao,
    )
    detalhes = DetalhesGrafo(
        rascunhos=tuple(rascunhos),
        motivo_parada=final.get("motivo_parada"),
        melhor_rodada=melhor.rodada,
        chamadas_total=chamadas,
        chamadas_rodada1=ex.chamadas_rodada1,
        duracao_total_s=duracao,
        duracao_rodada1_s=ex.duracao_rodada1,
    )
    return melhor.resultado, detalhes


def executar_grafo_com_detalhes(
    *,
    documento_id: str,
    titulo: str,
    texto: str,
    perfil,
    formato,
    nicho,
    nivel,
    progresso: Progresso = lambda _e, _p, _m: None,
    prazo: float | None = None,
    verificar_interrupcao: Callable[[], None] | None = None,
    limiar: float | None = None,
    max_revisoes: int | None = None,
    recuperar: Callable | None = None,
    provedor=None,
) -> tuple[pipeline.ResultadoGeracao, DetalhesGrafo]:
    """Roda só o grafo (sem semáforo nem fallback) e devolve o resultado e os detalhes.

    ``limiar`` e ``max_revisoes`` (padrão: os de ``settings``), ``recuperar``
    (padrão: ``rag.servico.recuperar``) e ``provedor`` (padrão: o da geração)
    existem para a medição (scripts/medir_geracao.py). Erros sobem como estão.
    """
    execucao = _Execucao(
        documento_id=documento_id, titulo=titulo, texto=texto, perfil=perfil, formato=formato,
        nicho=nicho, nivel=nivel,
        progresso=progresso if isinstance(progresso, _ProgressoMonotonico) else _ProgressoMonotonico(progresso),
        prazo=prazo, verificar_interrupcao=verificar_interrupcao,
        limiar=settings.grafo_limiar_ancoragem if limiar is None else limiar,
        max_revisoes=settings.grafo_max_revisoes if max_revisoes is None else max_revisoes,
        recuperar=recuperar, provedor_base=provedor,
    )
    return _executar_grafo(execucao)


def executar_pipeline_grafo(
    *,
    documento_id: str,
    titulo: str,
    texto: str,
    perfil,
    formato,
    nicho,
    nivel,
    progresso: Progresso,
    prazo: float | None = None,
    verificar_interrupcao: Callable[[], None] | None = None,
) -> pipeline.ResultadoGeracao:
    """Mesma assinatura e retorno de ``pipeline._gerar_passada_unica``, que é o fallback."""
    monotonico = _ProgressoMonotonico(progresso)
    argumentos = dict(
        documento_id=documento_id, titulo=titulo, texto=texto, perfil=perfil, formato=formato,
        nicho=nicho, nivel=nivel, progresso=monotonico, prazo=prazo,
        verificar_interrupcao=verificar_interrupcao,
    )
    semaforo = _semaforo()
    if not semaforo.acquire(blocking=False):
        logger.info("Grafo: sem vaga (GRAFO_MAX_SIMULTANEOS=%d); seguindo pela passada única.",
                    settings.grafo_max_simultaneos)
        return pipeline._gerar_passada_unica(**argumentos)

    try:
        resultado, _detalhes = executar_grafo_com_detalhes(**argumentos)
        return resultado
    except Exception as exc:
        if _sem_fallback(exc):
            raise
        if not _cabe_uma_chamada(prazo):
            logger.warning("Grafo: falhou (%s) e o prazo não comporta a passada única.", type(exc).__name__)
            raise
        erro = exc
    finally:
        semaforo.release()
    logger.warning("Grafo: falhou (%s); seguindo pela passada única (fallback).", type(erro).__name__)
    return pipeline._gerar_passada_unica(**argumentos)
