"""Mede a geração multiagente (grafo com revisões) contra a passada única, no mesmo job.

Desenho pareado: a rodada 1 do grafo é a passada única (mesmo prompt, mesmos
trechos). Para cada documento de ``data/exemplos/``, formato, perfil e
repetição, o grafo roda uma vez (``geracao_grafo.executar_grafo_com_detalhes``)
e o script compara a rodada 1 com o resultado final:

- ancoragem e clareza da rodada 1 e do final; rodadas; motivo da parada;
- chamadas ao LLM (total e só da rodada 1) e tempo (total e da rodada 1);
- se o JSON veio válido na primeira chamada;
- cópia literal: fração dos 8-gramas de palavras do conteúdo que aparecem no
  documento, para ver se as revisões sobem a ancoragem copiando o texto.

Provedor: o configurado (``LLM_PROVIDER`` e o modelo dele); ``--modelo`` troca
o modelo só neste processo. Cada chamada respeita ``--intervalo``; um limite
de taxa (429) que sobrar depois da retentativa do próprio provedor espera
``ESPERA_LIMITE_TAXA_S`` e repete a combinação uma vez. Chave recusada
interrompe tudo e grava o relatório parcial.

Recuperação (``--recuperacao``): ``real`` usa o RAG da geração (embeddings do
Gemini, precisa de ``GOOGLE_API_KEY``) num Chroma temporário, limpo a cada
combinação; ``lexical`` usa o BM25 (app/services/busca_lexical.py) sobre os
trechos do mesmo splitter, sem rede. Muda o resultado, e o relatório diz qual
foi usada.

O relatório (Markdown e JSON) vai para ``data/relatorios/`` e não traz texto
do documento nem do conteúdo gerado, nem chaves.

Uso (no container, a partir de /app):
    python scripts/medir_geracao.py --listar
    python scripts/medir_geracao.py --simulado
    python scripts/medir_geracao.py --recuperacao lexical --limiar 0.9
    python scripts/medir_geracao.py --documentos http_apis_rest.md --formatos Quiz --repeticoes 2
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import get_args

BACKEND = Path(__file__).resolve().parents[1]
for caminho in (BACKEND, BACKEND / "scripts"):
    if str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))

from comparar_modelos import EXEMPLOS, RELATORIOS, Ritmo, carregar_documento  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.llm.erros import ErroConfiguracao, ErroLimiteTaxa  # noqa: E402
from app.models import FormatoSaida, PerfilDestinatario  # noqa: E402
from app.rag.chunking import dividir_texto  # noqa: E402
from app.rag.modelos import Trecho  # noqa: E402
from app.services import geracao_grafo  # noqa: E402
from app.services.ancoragem import itens_medidos, normalizar  # noqa: E402
from app.services.busca_lexical import IndiceBM25  # noqa: E402

# ── Limites do veredito sobre ligar o grafo por padrão ────────────────────────
# RECOMENDADO só se todos valem; com menos revisados que o mínimo, INCONCLUSIVO.
MIN_REVISADOS = 5  # jobs em que o grafo chegou a revisar
GANHO_MINIMO = 0.05  # ganho médio de ancoragem nos revisados (final - rodada 1)
AUMENTO_MAXIMO_COPIA = 0.10  # cópia literal final - rodada 1, média nos revisados
CHAMADAS_EXTRAS_MAXIMAS = 2.0  # chamadas além da rodada 1, média por job
ERROS_MAXIMOS = 0.10  # fração de combinações com erro
# p95 do tempo total: JOB_TIMEOUT_SEGUNDOS, lido na hora.

NOTA = (
    "Amostra pequena e ancoragem lexical: o resultado serve para decidir entre a passada única "
    "e o grafo, não como prova estatística. Jobs que aprovam na rodada 1 não têm ganho a medir."
)

FORMATOS_PADRAO = ["Flashcards", "Quiz", "Tutorial"]
PERFIL_PADRAO = "Desenvolvedor"  # o mais usado nos testes; nível e nicho fixos abaixo
NIVEL, NICHO = "Tecnico", "Geral"
INTERVALO_PADRAO_SEGUNDOS = 3.0  # a cota gratuita é compartilhada com o chat
ESPERA_LIMITE_TAXA_S = 20.0
N_GRAMA = 8  # palavras por sequência na medida de cópia literal
CHAMADAS_POR_ESCRITA_MAX = 2  # a escrita e a repetição por JSON inválido

OK, FALHA = "ok", "falha"
_PALAVRA = re.compile(r"[a-z0-9]+")


@dataclass
class Medicao:
    documento: str
    formato: str
    perfil: str
    repeticao: int
    status: str
    erro: str | None = None
    tentativas: int = 0
    rodadas: int = 0
    motivo_parada: str | None = None
    melhor_rodada: int | None = None
    ancoragem_rodada1: float | None = None
    ancoragem_final: float | None = None
    clareza_rodada1: str | None = None
    clareza_final: str | None = None
    chamadas_total: int = 0
    chamadas_rodada1: int = 0
    json_valido_na_primeira: bool | None = None
    duracao_total_s: float | None = None
    duracao_rodada1_s: float | None = None
    copia_rodada1: float | None = None
    copia_final: float | None = None

    @property
    def revisado(self) -> bool:
        return self.status == OK and self.rodadas > 1


@dataclass
class Agregado:
    grupo: str
    n: int = 0
    erros: int = 0
    aprovados_rodada1: float | None = None
    revisados: int = 0
    taxa_revisados: float | None = None
    ancoragem_rodada1_revisados: float | None = None
    ancoragem_final_revisados: float | None = None
    ganho_medio_revisados: float | None = None
    melhorou_revisados: float | None = None
    chamadas_medias: float | None = None
    chamadas_extras_medias: float | None = None
    tempo_medio_s: float | None = None
    tempo_p50_s: float | None = None
    tempo_p95_s: float | None = None
    tempo_extra_medio_s: float | None = None
    copia_rodada1: float | None = None
    copia_final: float | None = None
    aumento_copia_revisados: float | None = None
    motivos: dict | None = None


class MedicaoInterrompida(Exception):
    def __init__(self, motivo: str, medicoes: list[Medicao]):
        super().__init__(motivo)
        self.medicoes = medicoes


# ── Cópia literal ─────────────────────────────────────────────────────────────


def ngramas(texto: str, n: int = N_GRAMA) -> set[tuple[str, ...]]:
    palavras = _PALAVRA.findall(normalizar(texto))
    return {tuple(palavras[i:i + n]) for i in range(len(palavras) - n + 1)}


def copia_literal(conteudo, documento: str, n: int = N_GRAMA) -> float | None:
    """Fração dos n-gramas do conteúdo (itens medidos) que aparecem no documento."""
    gerados = set().union(*(ngramas(item, n) for item in itens_medidos(conteudo))) if conteudo else set()
    if not gerados:
        return None
    return len(gerados & ngramas(documento, n)) / len(gerados)


# ── Recuperação lexical ───────────────────────────────────────────────────────


def recuperacao_lexical(texto: str) -> Callable:
    """``recuperar(documento_id, consulta, k)`` com BM25 sobre os trechos do mesmo splitter.

    Completa com os primeiros trechos (relevância 0) quando a busca acha menos de k.
    """
    trechos = dividir_texto(texto)
    indice = IndiceBM25([(str(i), t) for i, t in enumerate(trechos)])

    def recuperar(documento_id: str, consulta: str, k: int = 4) -> list[Trecho]:
        achados = indice.buscar(consulta, k)
        maior = achados[0][1] if achados else 1.0
        saida = [Trecho(texto=t, indice=int(i), relevancia=min(1.0, p / maior), documento_id=documento_id)
                 for (i, t), p in achados]
        usados = {t.indice for t in saida}
        for i, t in enumerate(trechos):
            if len(saida) >= k:
                break
            if i not in usados:
                saida.append(Trecho(texto=t, indice=i, relevancia=0.0, documento_id=documento_id))
        return saida

    return recuperar


class RecuperacaoReal:
    """RAG da geração num Chroma temporário; o índice de cada combinação é apagado no fim."""

    def __enter__(self):
        from app.rag import armazenamento, config

        self._config, self._armazenamento = config, armazenamento
        self._anterior = config.CHROMA_DIR
        self.pasta = tempfile.mkdtemp(prefix="medir-geracao-chroma-")
        config.CHROMA_DIR = self.pasta
        armazenamento.definir_cliente(None)
        return self

    def preparar(self, documento_id: str, titulo: str, texto: str) -> Callable:
        from app.rag import servico

        servico.indexar_documento(documento_id=documento_id, titulo=titulo, texto=texto)
        return servico.recuperar

    def limpar(self, documento_id: str) -> None:
        from app.services import limpeza_indice

        limpeza_indice.remover_indice(documento_id)

    def __exit__(self, *_exc):
        self._armazenamento.definir_cliente(None)
        self._config.CHROMA_DIR = self._anterior
        shutil.rmtree(self.pasta, ignore_errors=True)


# ── Provedores ────────────────────────────────────────────────────────────────


class ProvedorRitmado:
    """Respeita o intervalo mínimo entre chamadas (o grafo conta as chamadas)."""

    def __init__(self, base, ritmo: Ritmo):
        self.base = base
        self.nome = getattr(base, "nome", "provedor")
        self.ritmo = ritmo

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        self.ritmo.aguardar()
        try:
            return self.base.gerar(mensagens, timeout_segundos=timeout_segundos)
        finally:
            self.ritmo.marcar()


_TRECHOS_NO_PROMPT = re.compile(r"TRECHOS RELEVANTES DO DOCUMENTO:\n(.*?)\n\nTAREFA:", re.DOTALL)
_INVENTADAS = [
    "Zorbax orquestra contêineres efêmeros em nuvens distantes de baixa latência.",
    "O protocolo Quasar sincroniza filas zorbaxianas entre regiões remotas.",
    "Cada nó zorbaxiano replica estados voláteis numa malha elástica.",
]


class ProvedorSimulado:
    """Provedor determinístico para ``--simulado`` e testes, sem rede.

    Monta o conteúdo com frases dos trechos do prompt. Na rodada 1, Flashcards e
    Tutorial misturam frases inventadas (ancoragem baixa, o grafo revisa) e
    Quiz sai só com frases dos trechos (aprova). Nas revisões, só frases dos
    trechos: a ancoragem sobe e a cópia literal também.
    """

    nome = "simulado"
    modelo = "simulado"

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        prompt = mensagens[-1].conteudo
        achado = _TRECHOS_NO_PROMPT.search(prompt)
        texto = achado.group(1) if achado else ""
        frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", texto)
                  if len(f.strip()) > 40 and not f.strip().startswith("#") and f.strip() != "---"]
        frases = (frases or ["O documento descreve o assunto principal com exemplos práticos."]) * 3
        revisao = "REVISÃO DA VERSÃO ANTERIOR:" in prompt
        if '"tipo":"quiz"' in prompt:
            return self._quiz(frases)
        if not revisao:
            frases = [_INVENTADAS[i % 3] if i % 2 else f for i, f in enumerate(frases)]
        if '"tipo":"flashcards"' in prompt:
            return json.dumps({
                "tipo": "flashcards", "titulo": "Revisão do documento",
                "introducao_contextualizada": frases[0],
                "itens": [{"frente": f"Conceito {i + 1}", "verso": f, "dica_didatica": None}
                          for i, f in enumerate(frases[1:5])],
                "conceitos_chave": ["documento"],
            })
        corpo = "\n".join(f"## Passo {i + 1}\n{f}" for i, f in enumerate(frases[1:5]))
        return json.dumps({"tipo": "markdown", "titulo": "Passo a passo do documento",
                           "introducao_contextualizada": frases[0], "itens": corpo,
                           "conceitos_chave": ["documento"]})

    @staticmethod
    def _quiz(frases: list[str]) -> str:
        itens = [{"pergunta": f"Qual afirmação aparece no material ({i + 1})?",
                  "opcoes": [f, "Nenhuma das anteriores"], "resposta_correta": 0, "explicacao": f}
                 for i, f in enumerate(frases[:4])]
        return json.dumps({"tipo": "quiz", "titulo": "Quiz do documento",
                           "introducao_contextualizada": frases[0], "itens": itens,
                           "conceitos_chave": ["documento"]})


def provedor_e_modelo() -> tuple[str, str]:
    nome = settings.llm_provider.strip().lower()
    modelo = settings.nvidia_nim_modelo if nome == "nvidia" else settings.modelo_llm if nome == "gemini" else "—"
    return nome, modelo


def trocar_modelo(modelo: str) -> None:
    """Só neste processo: troca o modelo do provedor configurado e recria o provedor."""
    from app.llm import redefinir_provedor

    if settings.llm_provider.strip().lower() == "nvidia":
        settings.nvidia_nim_modelo = modelo
    else:
        settings.modelo_llm = modelo
    redefinir_provedor()


def _na_cadeia(exc: BaseException, tipo: type) -> bool:
    atual, vistos = exc, 0
    while atual is not None and vistos < 10:
        if isinstance(atual, tipo):
            return True
        atual, vistos = atual.__cause__ or atual.__context__, vistos + 1
    return False


# ── Medição ───────────────────────────────────────────────────────────────────


def medir_combinacao(
    documento, formato: str, perfil: str, repeticao: int, *, provedor, preparar_recuperacao: Callable,
    limpar_recuperacao: Callable, limiar: float, max_revisoes: int,
    relogio=time.monotonic, dormir=time.sleep,
) -> Medicao:
    """Uma combinação, com uma nova tentativa depois de um 429. Só levanta chave recusada."""
    medicao = Medicao(documento.nome, formato, perfil, repeticao, OK)
    for tentativa in (1, 2):
        medicao.tentativas = tentativa
        documento_id = f"medicao_{Path(documento.nome).stem}_{formato}_{repeticao}_{tentativa}"
        try:
            recuperar = preparar_recuperacao(documento_id, documento.titulo, documento.texto)
            resultado, detalhes = geracao_grafo.executar_grafo_com_detalhes(
                documento_id=documento_id, titulo=documento.titulo, texto=documento.texto, perfil=perfil,
                formato=formato, nicho=NICHO, nivel=NIVEL,
                prazo=relogio() + settings.job_timeout_segundos,
                limiar=limiar, max_revisoes=max_revisoes, recuperar=recuperar, provedor=provedor,
            )
        except Exception as exc:
            if _na_cadeia(exc, ErroConfiguracao):
                raise
            if _na_cadeia(exc, ErroLimiteTaxa) and tentativa == 1:
                dormir(ESPERA_LIMITE_TAXA_S)
                continue
            medicao.status, medicao.erro = FALHA, type(exc).__name__
            return medicao
        finally:
            try:
                limpar_recuperacao(documento_id)
            except Exception:  # noqa: BLE001 - a limpeza não decide a medição
                pass
        primeira = detalhes.rascunhos[0]
        medicao.rodadas = len(detalhes.rascunhos)
        medicao.motivo_parada = detalhes.motivo_parada
        medicao.melhor_rodada = detalhes.melhor_rodada
        medicao.ancoragem_rodada1 = primeira.nota
        medicao.ancoragem_final = resultado.avaliacao.ancoragem_fonte_score
        medicao.clareza_rodada1 = primeira.resultado.avaliacao.clareza_pedagogica
        medicao.clareza_final = resultado.avaliacao.clareza_pedagogica
        medicao.chamadas_total = detalhes.chamadas_total
        medicao.chamadas_rodada1 = detalhes.chamadas_rodada1
        medicao.json_valido_na_primeira = detalhes.chamadas_rodada1 == 1
        medicao.duracao_total_s = detalhes.duracao_total_s
        medicao.duracao_rodada1_s = detalhes.duracao_rodada1_s
        medicao.copia_rodada1 = copia_literal(primeira.resultado.conteudo, documento.texto)
        medicao.copia_final = copia_literal(resultado.conteudo, documento.texto)
        return medicao
    return medicao  # pragma: no cover


def medir(combinacoes: Iterable[tuple], avisar: Callable[[Medicao], None] = lambda _m: None, **kw) -> list[Medicao]:
    medicoes: list[Medicao] = []
    try:
        for documento, formato, perfil, repeticao in combinacoes:
            medicao = medir_combinacao(documento, formato, perfil, repeticao, **kw)
            medicoes.append(medicao)
            avisar(medicao)
    except Exception as exc:
        if not _na_cadeia(exc, ErroConfiguracao):
            raise
        raise MedicaoInterrompida(f"chave ou configuração recusada ({type(exc).__name__})", medicoes) from None
    return medicoes


# ── Agregação e veredito ──────────────────────────────────────────────────────


def percentil(valores: list[float], p: float) -> float | None:
    """Posto mais próximo (com poucos valores, o p95 é o máximo)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    return ordenados[max(1, math.ceil(p / 100 * len(ordenados))) - 1]


def _media(valores) -> float | None:
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if valores else None


def _fracao(sim: int, total: int) -> float | None:
    return sim / total if total else None


def agregar(medicoes: list[Medicao], grupo: str = "total") -> Agregado:
    ok = [m for m in medicoes if m.status == OK]
    revisados = [m for m in ok if m.revisado]
    tempos = [m.duracao_total_s for m in ok if m.duracao_total_s is not None]
    return Agregado(
        grupo=grupo,
        n=len(ok),
        erros=len(medicoes) - len(ok),
        aprovados_rodada1=_fracao(sum(1 for m in ok if m.rodadas == 1 and m.motivo_parada == "aprovado"), len(ok)),
        revisados=len(revisados),
        taxa_revisados=_fracao(len(revisados), len(ok)),
        ancoragem_rodada1_revisados=_media(m.ancoragem_rodada1 for m in revisados),
        ancoragem_final_revisados=_media(m.ancoragem_final for m in revisados),
        ganho_medio_revisados=_media(m.ancoragem_final - m.ancoragem_rodada1 for m in revisados),
        melhorou_revisados=_fracao(sum(1 for m in revisados if m.ancoragem_final > m.ancoragem_rodada1),
                                   len(revisados)),
        chamadas_medias=_media(m.chamadas_total for m in ok),
        chamadas_extras_medias=_media(m.chamadas_total - m.chamadas_rodada1 for m in ok),
        tempo_medio_s=_media(tempos),
        tempo_p50_s=percentil(tempos, 50),
        tempo_p95_s=percentil(tempos, 95),
        tempo_extra_medio_s=_media(
            m.duracao_total_s - m.duracao_rodada1_s for m in ok
            if m.duracao_total_s is not None and m.duracao_rodada1_s is not None
        ),
        copia_rodada1=_media(m.copia_rodada1 for m in ok),
        copia_final=_media(m.copia_final for m in ok),
        aumento_copia_revisados=_media(
            m.copia_final - m.copia_rodada1 for m in revisados
            if m.copia_final is not None and m.copia_rodada1 is not None
        ),
        motivos=dict(sorted(Counter(m.motivo_parada for m in ok).items())),
    )


def veredito(total: Agregado, prazo_s: float | None = None) -> tuple[str, list[str]]:
    """RECOMENDADO, NÃO RECOMENDADO ou INCONCLUSIVO, com os motivos."""
    prazo = settings.job_timeout_segundos if prazo_s is None else prazo_s
    motivos = []
    if total.ganho_medio_revisados is None or total.ganho_medio_revisados < GANHO_MINIMO:
        motivos.append(f"ganho médio de ancoragem nos revisados abaixo de {GANHO_MINIMO:.2f}")
    if total.aumento_copia_revisados is not None and total.aumento_copia_revisados > AUMENTO_MAXIMO_COPIA:
        motivos.append(f"cópia literal subiu mais de {AUMENTO_MAXIMO_COPIA:.2f} nas revisões")
    if total.chamadas_extras_medias is None or total.chamadas_extras_medias > CHAMADAS_EXTRAS_MAXIMAS:
        motivos.append(f"chamadas extras médias acima de {CHAMADAS_EXTRAS_MAXIMAS:g} por job")
    if total.tempo_p95_s is None or total.tempo_p95_s > prazo:
        motivos.append(f"p95 do tempo total acima de {prazo:g} s")
    combinacoes = total.n + total.erros
    if combinacoes and total.erros / combinacoes > ERROS_MAXIMOS:
        motivos.append(f"erros acima de {ERROS_MAXIMOS:.0%}")
    if total.revisados < MIN_REVISADOS:
        return "INCONCLUSIVO", [f"só {total.revisados} job(s) revisado(s); o mínimo é {MIN_REVISADOS}", *motivos]
    return ("RECOMENDADO", []) if not motivos else ("NÃO RECOMENDADO", motivos)


# ── Relatório ─────────────────────────────────────────────────────────────────


def _n(valor, casas: int = 3) -> str:
    return "—" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def _pct(valor) -> str:
    return "—" if valor is None else f"{valor * 100:.0f}%"


def tabela_combinacoes(medicoes: list[Medicao]) -> str:
    linhas = [
        "| Documento | Formato | Perfil | Rep. | Situação | Rodadas | Motivo | Ancoragem r1 → final "
        "| Clareza r1 → final | Chamadas (r1) | JSON na 1ª | Tempo r1 / total (s) | Cópia r1 → final |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in medicoes:
        situacao = m.status if not m.erro else f"{m.status} ({m.erro})"
        linhas.append(
            f"| {m.documento} | {m.formato} | {m.perfil} | {m.repeticao} | {situacao} | {m.rodadas or '—'} "
            f"| {m.motivo_parada or '—'} | {_n(m.ancoragem_rodada1)} → {_n(m.ancoragem_final)} "
            f"| {m.clareza_rodada1 or '—'} → {m.clareza_final or '—'} | {m.chamadas_total} ({m.chamadas_rodada1}) "
            f"| {'—' if m.json_valido_na_primeira is None else ('sim' if m.json_valido_na_primeira else 'não')} "
            f"| {_n(m.duracao_rodada1_s, 1)} / {_n(m.duracao_total_s, 1)} "
            f"| {_n(m.copia_rodada1)} → {_n(m.copia_final)} |"
        )
    return "\n".join(linhas)


def tabela_agregados(agregados: list[Agregado]) -> str:
    linhas = [
        "| Grupo | n | Aprovou na r1 | Revisados | Ancoragem r1 → final (revisados) | Ganho médio | Melhorou "
        "| Chamadas (extras) | Tempo médio / p50 / p95 (s) | Tempo extra (s) | Cópia r1 → final | Motivos | Erros |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a in agregados:
        motivos = ", ".join(f"{k} ×{v}" for k, v in (a.motivos or {}).items()) or "—"
        linhas.append(
            f"| {a.grupo} | {a.n} | {_pct(a.aprovados_rodada1)} | {a.revisados} ({_pct(a.taxa_revisados)}) "
            f"| {_n(a.ancoragem_rodada1_revisados)} → {_n(a.ancoragem_final_revisados)} "
            f"| {_n(a.ganho_medio_revisados)} | {_pct(a.melhorou_revisados)} "
            f"| {_n(a.chamadas_medias, 1)} ({_n(a.chamadas_extras_medias, 1)}) "
            f"| {_n(a.tempo_medio_s, 1)} / {_n(a.tempo_p50_s, 1)} / {_n(a.tempo_p95_s, 1)} "
            f"| {_n(a.tempo_extra_medio_s, 1)} | {_n(a.copia_rodada1)} → {_n(a.copia_final)} | {motivos} | {a.erros} |"
        )
    return "\n".join(linhas)


def agregados_por_formato(medicoes: list[Medicao]) -> list[Agregado]:
    formatos = list(dict.fromkeys(m.formato for m in medicoes))
    return [agregar([m for m in medicoes if m.formato == f], f) for f in formatos] + [agregar(medicoes)]


def montar_relatorio(medicoes: list[Medicao], config: dict, quando: datetime, interrompido: str | None = None) -> str:
    agregados = agregados_por_formato(medicoes)
    total = agregados[-1]
    decisao, motivos = veredito(total)
    linhas = [f"# Medição da geração multiagente, {quando:%Y-%m-%d %H:%M}", ""]
    if interrompido:
        linhas += [f"> **Relatório parcial:** medição interrompida ({interrompido}).", ""]
    linhas += [
        f"- Provedor: {config['provedor']}; modelo: `{config['modelo']}`",
        f"- Recuperação: {config['recuperacao']}",
        f"- Limiar de ancoragem: {config['limiar']}; revisões no máximo: {config['max_revisoes']}",
        f"- Perfil {config['perfil']}, nível {NIVEL}, nicho {NICHO}; repetições: {config['repeticoes']}",
        f"- Documentos: {', '.join(config['documentos'])}; formatos: {', '.join(config['formatos'])}",
        f"- **{total.n - total.revisados} de {total.n} jobs aprovaram na rodada 1** (sem ganho a medir); "
        f"{total.revisados} foram revisados.",
        "",
        f"> {NOTA}",
        "",
        f"## Veredito sobre ligar o grafo por padrão: {decisao}",
        "",
        *([f"- {m}" for m in motivos] or ["- Todos os critérios foram atendidos."]),
        "",
        f"Critérios: pelo menos {MIN_REVISADOS} jobs revisados; ganho médio de ancoragem nos revisados "
        f">= {GANHO_MINIMO:.2f}; cópia literal final no máximo {AUMENTO_MAXIMO_COPIA:.2f} acima da rodada 1; "
        f"no máximo {CHAMADAS_EXTRAS_MAXIMAS:g} chamadas extras por job; p95 do tempo total <= "
        f"{settings.job_timeout_segundos} s; erros <= {ERROS_MAXIMOS:.0%}.",
        "",
        "## Agregados (por formato e total)",
        "",
        tabela_agregados(agregados),
        "",
        "## Combinações",
        "",
        tabela_combinacoes(medicoes),
        "",
    ]
    return "\n".join(linhas)


def montar_json(medicoes: list[Medicao], config: dict, quando: datetime, interrompido: str | None = None) -> dict:
    agregados = agregados_por_formato(medicoes)
    decisao, motivos = veredito(agregados[-1])
    return {
        "quando": quando.isoformat(timespec="seconds"),
        "interrompido": interrompido,
        "nota": NOTA,
        "configuracao": config,
        "limites": {
            "min_revisados": MIN_REVISADOS, "ganho_minimo": GANHO_MINIMO,
            "aumento_maximo_copia": AUMENTO_MAXIMO_COPIA, "chamadas_extras_maximas": CHAMADAS_EXTRAS_MAXIMAS,
            "p95_maximo_s": settings.job_timeout_segundos, "erros_maximos": ERROS_MAXIMOS,
        },
        "veredito": {"decisao": decisao, "motivos": motivos},
        "agregados": [asdict(a) for a in agregados],
        "medicoes": [asdict(m) for m in medicoes],
    }


def gravar_relatorios(markdown: str, dados: dict, quando: datetime, pasta: Path = RELATORIOS) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    base = pasta / f"medicao_geracao_{quando:%Y%m%d_%H%M%S}"
    md, js = base.with_suffix(".md"), base.with_suffix(".json")
    md.write_text(markdown, encoding="utf-8")
    js.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return md, js


# ── Linha de comando ──────────────────────────────────────────────────────────


def _lista(valor: str) -> list[str]:
    return [item.strip() for item in valor.split(",") if item.strip()]


def documentos_disponiveis() -> list[str]:
    return sorted(p.name for p in EXEMPLOS.glob("*.md"))


def plano(n_combinacoes: int, max_revisoes: int, intervalo: float) -> dict:
    minimo = n_combinacoes  # todas aprovam na rodada 1, JSON válido na primeira
    maximo = n_combinacoes * (1 + max_revisoes) * CHAMADAS_POR_ESCRITA_MAX
    return {
        "combinacoes": n_combinacoes,
        "chamadas_min": minimo,
        "chamadas_max": maximo,
        "minutos_min": minimo * intervalo / 60,
        "minutos_max": maximo * intervalo / 60,
    }


def main(argv: list[str] | None = None, *, provedor=None, pasta_relatorios: Path = RELATORIOS,
         relogio=time.monotonic, dormir=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Mede a geração multiagente contra a passada única.")
    parser.add_argument("--documentos", type=_lista, default=None, help="arquivos de data/exemplos/ (padrão: todos)")
    parser.add_argument("--formatos", type=_lista, default=FORMATOS_PADRAO,
                        help=f"{', '.join(get_args(FormatoSaida))}")
    parser.add_argument("--perfil", default=PERFIL_PADRAO, help=", ".join(get_args(PerfilDestinatario)))
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--modelo", default=None, help="troca o modelo do provedor só neste processo")
    parser.add_argument("--recuperacao", choices=("real", "lexical"), default="real")
    parser.add_argument("--limiar", type=float, default=None, help="padrão: GRAFO_LIMIAR_ANCORAGEM")
    parser.add_argument("--max-revisoes", type=int, default=None, help="padrão: GRAFO_MAX_REVISOES")
    parser.add_argument("--intervalo", type=float, default=None,
                        help=f"segundos entre chamadas (padrão {INTERVALO_PADRAO_SEGUNDOS:g}; 0 no simulado)")
    parser.add_argument("--listar", action="store_true", help="mostra o plano e sai, sem chamar ninguém")
    parser.add_argument("--simulado", action="store_true", help="provedor falso e recuperação lexical, sem rede")
    args = parser.parse_args(argv)

    disponiveis = documentos_disponiveis()
    documentos = args.documentos or disponiveis
    limiar = settings.grafo_limiar_ancoragem if args.limiar is None else args.limiar
    max_revisoes = settings.grafo_max_revisoes if args.max_revisoes is None else args.max_revisoes
    intervalo = args.intervalo if args.intervalo is not None else (0.0 if args.simulado else INTERVALO_PADRAO_SEGUNDOS)
    invalidos = [d for d in documentos if d not in disponiveis]
    invalidos += [f for f in args.formatos if f not in get_args(FormatoSaida)]
    invalidos += [args.perfil] if args.perfil not in get_args(PerfilDestinatario) else []
    if (invalidos or not args.formatos or args.repeticoes < 1 or not 0 <= limiar <= 1
            or not 0 <= max_revisoes <= 2 or intervalo < 0):
        print(f"Opção inválida: {', '.join(invalidos) or 'repetições, limiar, revisões ou intervalo'}. "
              f"Documentos: {', '.join(disponiveis)}; formatos: {', '.join(get_args(FormatoSaida))}; "
              f"perfis: {', '.join(get_args(PerfilDestinatario))}; limiar entre 0 e 1; revisões de 0 a 2.",
              file=sys.stderr)
        return 2
    combinacoes_nomes = [(d, f, r) for d in documentos for f in args.formatos for r in range(1, args.repeticoes + 1)]

    if args.listar:
        p = plano(len(combinacoes_nomes), max_revisoes, intervalo)
        print(f"Combinações: {p['combinacoes']} ({len(documentos)} documentos × {len(args.formatos)} formatos × "
              f"{args.repeticoes} repetições)")
        print(f"Chamadas ao LLM: de {p['chamadas_min']} (todas aprovam na rodada 1) a {p['chamadas_max']} "
              f"(todas as revisões, com a repetição por JSON inválido)")
        print(f"Tempo só de intervalo ({intervalo:g} s): de {_n(p['minutos_min'], 1)} a {_n(p['minutos_max'], 1)} min, "
              "mais a latência do modelo")
        if args.recuperacao == "real" and not args.simulado:
            print(f"Embeddings: {p['combinacoes']} indexações e de {p['combinacoes']} a "
                  f"{p['combinacoes'] * (1 + max_revisoes)} consultas")
        return 0

    recuperacao = "lexical" if args.simulado else args.recuperacao
    if provedor is None:
        if args.simulado:
            provedor = ProvedorSimulado()
        else:
            nome, _modelo = provedor_e_modelo()
            if nome == "nvidia" and not settings.nvidia_nim_api_key.get_secret_value():
                print("NVIDIA_NIM_API_KEY não definida no ambiente. Use --simulado para testar sem chave.",
                      file=sys.stderr)
                return 2
            if (nome == "gemini" or recuperacao == "real") and not settings.google_api_key:
                print("GOOGLE_API_KEY não definida no ambiente (necessária para o gemini ou a recuperação real). "
                      "Use --recuperacao lexical ou --simulado.", file=sys.stderr)
                return 2
            if args.modelo:
                trocar_modelo(args.modelo)
            from app.llm import obter_provedor

            provedor = obter_provedor()
    nome_provedor, nome_modelo = ("simulado", "simulado") if args.simulado else provedor_e_modelo()
    ritmado = ProvedorRitmado(provedor, Ritmo(intervalo, dormir=dormir, relogio=relogio))
    config = {
        "provedor": nome_provedor, "modelo": nome_modelo, "recuperacao": recuperacao, "limiar": limiar,
        "max_revisoes": max_revisoes, "perfil": args.perfil, "nivel": NIVEL, "nicho": NICHO,
        "repeticoes": args.repeticoes, "documentos": documentos, "formatos": args.formatos,
        "intervalo_s": intervalo,
    }
    carregados = {d: carregar_documento(EXEMPLOS / d) for d in documentos}
    combinacoes = [(carregados[d], f, args.perfil, r) for d, f, r in combinacoes_nomes]

    def avisar(m: Medicao) -> None:
        print(f"{m.documento} | {m.formato} | rep {m.repeticao} | {m.status} {m.erro or ''}| rodadas {m.rodadas} "
              f"| {m.motivo_parada or '—'} | ancoragem {_n(m.ancoragem_rodada1)} → {_n(m.ancoragem_final)} "
              f"| {_n(m.duracao_total_s, 1)} s", flush=True)

    interrompido = None
    real = RecuperacaoReal() if recuperacao == "real" else None
    try:
        if real:
            real.__enter__()
            preparar, limpar = real.preparar, real.limpar
        else:
            def preparar(_id, _titulo, texto):
                return recuperacao_lexical(texto)

            def limpar(_id):
                return None
        medicoes = medir(combinacoes, avisar, provedor=ritmado, preparar_recuperacao=preparar,
                         limpar_recuperacao=limpar, limiar=limiar, max_revisoes=max_revisoes,
                         relogio=relogio, dormir=dormir)
    except MedicaoInterrompida as exc:
        medicoes, interrompido = exc.medicoes, str(exc)
    finally:
        if real:
            real.__exit__(None, None, None)

    agora = datetime.now()
    md, js = gravar_relatorios(montar_relatorio(medicoes, config, agora, interrompido),
                               montar_json(medicoes, config, agora, interrompido), agora, pasta_relatorios)
    agregados = agregados_por_formato(medicoes)
    decisao, motivos = veredito(agregados[-1])
    print()
    print(tabela_agregados(agregados))
    print(f"\nVeredito: {decisao}" + (f" ({'; '.join(motivos)})" if motivos else ""))
    print(f"\n{NOTA}")
    print(f"\nRelatórios: {md} e {js}")
    if interrompido:
        print(f"Interrompido: {interrompido}. Relatório parcial gravado.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
