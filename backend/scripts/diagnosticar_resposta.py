"""Diagnostica por que a resposta do modelo não vira conteúdo válido.

Chama o provedor configurado (``LLM_PROVIDER`` e o modelo dele) N vezes com o
mesmo prompt da geração (``pipeline._montar_prompt``) e a mesma recuperação
lexical da medição (``medir_geracao.recuperacao_lexical``: BM25 sobre os
trechos do splitter, sem embeddings), e passa cada resposta pelos mesmos
passos do pipeline (``_extrair_json`` e ``_parsear_conteudo``).

Para cada resposta grava só metadados, nunca o texto do documento nem o
conteúdo gerado:

- categoria: ``valida``, ``truncado``, ``json_invalido``, ``bloco_markdown``,
  ``campo_ausente``, ``valor_fora_do_intervalo`` ou ``outro``;
- mensagem de validação sem valores (tipo do erro e caminho do campo);
- tamanho da resposta, motivo de término (``finish_reason``) e tokens, quando o
  provedor expõe;
- posição do ponto de falha (caractere e fração da resposta) e sinais como
  cerca de markdown, texto antes ou depois do JSON e chaves desbalanceadas.

Com ``--via-pipeline``, cada geração passa por ``pipeline._gerar_conteudo`` (as
duas tentativas, com o prazo do job em ``limites_da_geracao`` e a contagem de
chamadas do grafo), como o redator na medição. Por tentativa, o relatório traz
o tipo e o motivo que a linha de log do pipeline mostra, o motivo de término,
os tokens, o timeout passado ao provedor e o tempo.

Uso (no container, a partir de /app):
    python scripts/diagnosticar_resposta.py --simulado
    python scripts/diagnosticar_resposta.py --formato Quiz --documento git_versionamento.md --n 5
    python scripts/diagnosticar_resposta.py --via-pipeline --formato Quiz --documento git_versionamento.md
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import get_args

BACKEND = Path(__file__).resolve().parents[1]
for caminho in (BACKEND, BACKEND / "scripts"):
    if str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))

from comparar_modelos import EXEMPLOS, RELATORIOS, Ritmo, carregar_documento  # noqa: E402
from medir_geracao import NICHO, NIVEL, PERFIL_PADRAO, recuperacao_lexical  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.llm import Mensagem  # noqa: E402
from app.llm.erros import ErroLLM, ErroRespostaInvalida  # noqa: E402
from app.models import FormatoSaida  # noqa: E402
from app.services import pipeline  # noqa: E402

VALIDA, TRUNCADO, JSON_INVALIDO, BLOCO_MARKDOWN = "valida", "truncado", "json_invalido", "bloco_markdown"
CAMPO_AUSENTE, FORA_DO_INTERVALO, OUTRO = "campo_ausente", "valor_fora_do_intervalo", "outro"
CATEGORIAS = (VALIDA, TRUNCADO, JSON_INVALIDO, BLOCO_MARKDOWN, CAMPO_AUSENTE, FORA_DO_INTERVALO, OUTRO)

N_PADRAO = 3
INTERVALO_PADRAO_SEGUNDOS = 3.0
FORMATO_PADRAO = "Quiz"
DOCUMENTO_PADRAO = "http_apis_rest.md"
CERCA = "```"
# Tipos de erro do pydantic que indicam valor fora do que o esquema aceita.
_TIPOS_FORA_DO_INTERVALO = {
    "too_short", "too_long", "string_too_short", "string_too_long",
    "greater_than_equal", "greater_than", "less_than", "less_than_equal",
}
_TIPOS_TIPO_ERRADO = {"int_parsing", "int_type", "int_from_float", "string_type", "list_type", "dict_type",
                      "model_type"}


@dataclass
class Diagnostico:
    chamada: int
    categoria: str
    mensagem: str | None = None
    tamanho: int | None = None  # caracteres da resposta (depois de tirar o raciocínio)
    motivo_fim: str | None = None  # finish_reason, se o provedor expõe
    tokens_resposta: int | None = None
    tokens_total: int | None = None
    posicao: int | None = None  # caractere do ponto de falha na resposta
    posicao_relativa: float | None = None  # posicao / tamanho
    caminho: str | None = None  # campo do esquema que falhou (ex.: itens.2.resposta_correta)
    sinais: list[str] = field(default_factory=list)
    duracao_s: float | None = None


# ── Classificação (sem guardar texto) ─────────────────────────────────────────


def _sinais(texto: str) -> list[str]:
    sinais = []
    if CERCA in texto:
        sinais.append("cerca_markdown")
    inicio = texto.find("{")
    if inicio > 0 and texto[:inicio].strip(" \n`json"):
        sinais.append("texto_antes_do_json")
    if inicio != -1:
        # Fim do primeiro objeto completo; sem ele, a última chave do texto.
        try:
            _obj, fim = json.JSONDecoder().raw_decode(texto, inicio)
        except json.JSONDecodeError:
            fim = texto.rfind("}") + 1
        if fim and texto[fim:].strip(" \n`"):
            sinais.append("texto_depois_do_json")
    if texto.count("{") != texto.count("}"):
        sinais.append("chaves_desbalanceadas")
    if "<think>" in texto or "</think>" in texto:
        sinais.append("marca_de_raciocinio")
    return sinais


def _caminho(loc) -> str:
    return ".".join(str(p) for p in loc)


def _categoria_de_validacao(erro: dict) -> str:
    if erro["type"] == "missing":
        return CAMPO_AUSENTE
    if erro["type"] in _TIPOS_FORA_DO_INTERVALO:
        return FORA_DO_INTERVALO
    return OUTRO


def _avisos_do_quiz(raw: dict) -> list[str]:
    """O que o pipeline aceita mas está errado: resposta fora das opções, opções repetidas."""
    avisos = []
    for i, item in enumerate(raw.get("itens") or []):
        if not isinstance(item, dict):
            continue
        opcoes, correta = item.get("opcoes"), item.get("resposta_correta")
        if isinstance(opcoes, list) and isinstance(correta, int) and correta >= len(opcoes):
            avisos.append(f"itens.{i}.resposta_correta_fora_das_opcoes")
        if isinstance(opcoes, list) and len(set(map(str, opcoes))) < len(opcoes):
            avisos.append(f"itens.{i}.opcoes_repetidas")
    return avisos


def classificar(texto: str, formato: str, motivo_fim: str | None = None) -> Diagnostico:
    """Repete os passos do pipeline e diz onde e por que a resposta falharia."""
    d = Diagnostico(chamada=0, categoria=VALIDA, tamanho=len(texto), motivo_fim=motivo_fim, sinais=_sinais(texto))
    limpo = re.sub(r"```(?:json)?\s*", "", texto).replace(CERCA, "")
    inicio, fim = limpo.find("{"), limpo.rfind("}") + 1
    if inicio == -1 or fim == 0:
        d.categoria = TRUNCADO if inicio != -1 or motivo_fim == "length" else OUTRO
        d.mensagem = "sem objeto JSON completo" if inicio != -1 else "nenhum objeto JSON na resposta"
        d.posicao = len(texto)
        return _relativa(d)
    try:
        raw = json.loads(limpo[inicio:fim])
    except json.JSONDecodeError as exc:
        d.mensagem = exc.msg  # o json não põe valores na mensagem, só o tipo do problema
        d.posicao = inicio + exc.pos
        perto_do_fim = fim - (inicio + exc.pos) <= 2
        if motivo_fim == "length" or "chaves_desbalanceadas" in d.sinais and perto_do_fim:
            d.categoria = TRUNCADO
        elif "cerca_markdown" in d.sinais and CERCA in texto[texto.find("{") if "{" in texto else 0:]:
            d.categoria = BLOCO_MARKDOWN  # cerca dentro do objeto: o pipeline a apaga no meio do JSON
        else:
            d.categoria = JSON_INVALIDO
            try:
                json.loads(limpo[inicio:fim], strict=False)
                d.mensagem = f"{exc.msg} (quebra de linha ou controle dentro de string)"
            except json.JSONDecodeError:
                pass
        return _relativa(d)
    if not isinstance(raw, dict):
        d.categoria, d.mensagem = OUTRO, "o JSON não é um objeto"
        return d
    avisos = _avisos_do_quiz(raw) if formato == "Quiz" else []
    try:
        pipeline._parsear_conteudo(raw, formato)
    except KeyError as exc:
        d.categoria, d.mensagem, d.caminho = CAMPO_AUSENTE, "campo obrigatório ausente", str(exc.args[0])
    except TypeError:
        d.categoria, d.mensagem = OUTRO, "item do conteúdo não é um objeto"
    except ValidationError as exc:
        erros = exc.errors()
        primeiro = erros[0]
        d.categoria = _categoria_de_validacao(primeiro)
        d.caminho = _caminho(primeiro["loc"])
        tipos = sorted({e["type"] for e in erros})
        d.mensagem = f"{len(erros)} erro(s) de esquema: {', '.join(tipos)}"
        if primeiro["type"] in _TIPOS_TIPO_ERRADO:
            d.mensagem += " (tipo errado, por exemplo letra em vez de índice)"
    d.sinais += avisos
    return d


def _relativa(d: Diagnostico) -> Diagnostico:
    if d.posicao is not None and d.tamanho:
        d.posicao_relativa = round(min(1.0, d.posicao / d.tamanho), 3)
    return d


# ── Provedores ────────────────────────────────────────────────────────────────


def _base(provedor):
    return getattr(provedor, "base", provedor)


def _metadados_do_provedor(provedor) -> tuple[str | None, int | None, int | None]:
    base = _base(provedor)
    uso = getattr(base, "ultimo_uso", None) or {}
    motivo = getattr(base, "ultimo_motivo_fim", None)
    resposta = uso.get("completion_tokens") if isinstance(uso.get("completion_tokens"), int) else None
    total = uso.get("total_tokens") if isinstance(uso.get("total_tokens"), int) else None
    return motivo, resposta, total


# Mesma mensagem de app/llm/nvidia.py, para o simulado mostrar o que o log real mostra.
MSG_CORTADA_NVIDIA = (
    "NVIDIA NIM: resposta cortada pelo limite de tokens; aumente "
    "NVIDIA_NIM_MAX_TOKENS ou reduza o raciocínio."
)

_QUIZ_VALIDO = {
    "tipo": "quiz", "titulo": "Quiz", "introducao_contextualizada": "Revisão do material.",
    "itens": [{"pergunta": "Qual método cria?", "opcoes": ["GET", "POST"], "resposta_correta": 1,
               "explicacao": "POST cria um recurso."}],
    "conceitos_chave": ["POST"],
}


def respostas_simuladas() -> list:
    """Uma resposta (ou erro) por categoria, na ordem; o simulado repete o ciclo."""
    valido = json.dumps(_QUIZ_VALIDO, ensure_ascii=False)
    sem_explicacao = json.loads(valido)
    del sem_explicacao["itens"][0]["explicacao"]
    letra = json.loads(valido)
    letra["itens"][0]["resposta_correta"] = "B"
    uma_opcao = json.loads(valido)
    uma_opcao["itens"][0]["opcoes"] = ["POST"]
    return [
        ("stop", valido),
        ("length", ErroRespostaInvalida(MSG_CORTADA_NVIDIA)),
        ("stop", valido[: len(valido) // 2]),
        ("stop", valido.replace('"Revisão do material."', '"Revisão\ndo material."')),
        ("stop", "```json\n" + valido + "\n```\n\nExemplo: ```{\"a\": 1}```"),
        ("stop", json.dumps(sem_explicacao, ensure_ascii=False)),
        ("stop", json.dumps(uma_opcao, ensure_ascii=False)),
        ("stop", json.dumps(letra, ensure_ascii=False)),
        ("stop", "Aqui está o quiz: " + valido + " Espero ter ajudado {fim}"),
    ]


class ProvedorSimulado:
    """Reproduz cada categoria, em ciclo, sem rede (para os testes e o ``--simulado``)."""

    nome = "simulado"
    modelo = "simulado"

    def __init__(self, respostas: list | None = None):
        self.respostas = respostas or respostas_simuladas()
        self.chamadas = 0
        self.ultimo_motivo_fim: str | None = None
        self.ultimo_uso: dict | None = None

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        motivo, item = self.respostas[self.chamadas % len(self.respostas)]
        self.chamadas += 1
        self.ultimo_motivo_fim = motivo
        self.ultimo_uso = {"completion_tokens": 100 + self.chamadas, "total_tokens": 1000 + self.chamadas}
        if isinstance(item, BaseException):
            raise item
        return item


class ProvedorRitmado:
    def __init__(self, base, ritmo: Ritmo):
        self.base, self.ritmo = base, ritmo
        self.nome = getattr(base, "nome", "provedor")

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        self.ritmo.aguardar()
        try:
            return self.base.gerar(mensagens, timeout_segundos=timeout_segundos)
        finally:
            self.ritmo.marcar()


# ── Diagnóstico ───────────────────────────────────────────────────────────────


def montar_prompt(documento, formato: str, perfil: str = PERFIL_PADRAO) -> str:
    recuperar = recuperacao_lexical(documento.texto)
    trechos = recuperar(documento_id="diagnostico", consulta=pipeline._consulta_padrao(documento.titulo, perfil), k=6)
    return pipeline._montar_prompt(documento.titulo, [t.texto for t in trechos], perfil, formato, NICHO, NIVEL)


def diagnosticar(provedor, prompt: str, formato: str, n: int, ritmo: Ritmo, relogio=time.monotonic,
                 avisar=lambda _d: None) -> list[Diagnostico]:
    from app.llm.nvidia import remover_raciocinio

    diagnosticos = []
    ritmado = ProvedorRitmado(provedor, ritmo)
    for chamada in range(1, n + 1):
        inicio = relogio()
        try:
            texto = ritmado.gerar([Mensagem("user", prompt)], timeout_segundos=settings.llm_timeout_segundos)
        except ErroRespostaInvalida:
            motivo, resposta, total = _metadados_do_provedor(provedor)
            d = Diagnostico(chamada, TRUNCADO if motivo == "length" else OUTRO,
                            "resposta cortada pelo limite de tokens" if motivo == "length"
                            else "resposta vazia ou sem texto", motivo_fim=motivo,
                            tokens_resposta=resposta, tokens_total=total)
        except ErroLLM as exc:
            motivo, resposta, total = _metadados_do_provedor(provedor)
            d = Diagnostico(chamada, OUTRO, f"erro do provedor: {type(exc).__name__}", motivo_fim=motivo,
                            tokens_resposta=resposta, tokens_total=total)
        else:
            motivo, resposta, total = _metadados_do_provedor(provedor)
            d = classificar(remover_raciocinio(texto or ""), formato, motivo)
            d.chamada, d.tokens_resposta, d.tokens_total = chamada, resposta, total
        d.duracao_s = round(relogio() - inicio, 2)
        diagnosticos.append(d)
        avisar(d)
    return diagnosticos


# ── Pelo caminho da geração (--via-pipeline) ──────────────────────────────────


@dataclass
class Tentativa:
    tentativa: int
    resultado: str  # "valida" ou o tipo da exceção (o mesmo nome que vai para o log)
    motivo: str | None = None  # o motivo que a linha de log do pipeline mostra
    motivo_fim: str | None = None
    tokens_resposta: int | None = None
    tokens_total: int | None = None
    timeout_s: float | None = None  # timeout que o pipeline passou ao provedor
    duracao_s: float | None = None


@dataclass
class ExecucaoPipeline:
    execucao: int
    resultado: str  # "ok" ou "falha"
    erro: str | None = None  # tipo (e mensagem, se for do pipeline) do erro final
    chamadas: int = 0
    duracao_s: float | None = None
    tentativas: list[Tentativa] = field(default_factory=list)


_LOG_RESPOSTA_INVALIDA = "Resposta inválida do LLM"
_POSICAO_NO_MOTIVO = re.compile(r" \(caractere \d+ de \d+\)$")


class _CapturaDoLog(logging.Handler):
    """Guarda (tipo, motivo) de cada linha "Resposta inválida do LLM" do pipeline."""

    def __init__(self):
        super().__init__(logging.WARNING)
        self.registros: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        if str(record.msg).startswith(_LOG_RESPOSTA_INVALIDA) and len(record.args or ()) == 4:
            self.registros.append((str(record.args[2]), str(record.args[3])))


class ProvedorAnotado:
    """Anota cada chamada (tempo, timeout, motivo de fim, tokens) sem mudar o resultado."""

    def __init__(self, base, origem, relogio=time.monotonic):
        self.base, self.origem, self.relogio = base, origem, relogio
        self.nome = getattr(base, "nome", "provedor")
        self.chamadas: list[dict] = []

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        inicio = self.relogio()
        try:
            return self.base.gerar(mensagens, timeout_segundos=timeout_segundos)
        finally:
            motivo, resposta, total = _metadados_do_provedor(self.origem)
            self.chamadas.append({"motivo_fim": motivo, "tokens_resposta": resposta, "tokens_total": total,
                                  "timeout_s": timeout_segundos, "duracao_s": round(self.relogio() - inicio, 2)})


def _erro_final(exc: BaseException) -> str:
    # As mensagens de RuntimeError do pipeline são fixas e em português; as outras, só o tipo.
    return f"{type(exc).__name__}: {exc}" if isinstance(exc, RuntimeError) else type(exc).__name__


def diagnosticar_via_pipeline(provedor, prompt: str, formato: str, n: int, ritmo: Ritmo,
                              relogio=time.monotonic, avisar=lambda _e: None) -> list[ExecucaoPipeline]:
    """Roda N gerações por ``pipeline._gerar_conteudo``, como o redator do grafo na medição.

    Mesmas camadas da medição: ``_ProvedorContado`` (do grafo) sobre o provedor
    ritmado, dentro de ``limites_da_geracao`` com o prazo do job. As retentativas
    de falha transitória do provedor ficam dentro de uma chamada anotada.
    """
    from app.llm import limites_da_geracao
    from app.services.geracao_grafo import _ProvedorContado

    execucoes = []
    for numero in range(1, n + 1):
        anotado = ProvedorAnotado(ProvedorRitmado(provedor, ritmo), provedor, relogio)
        contado = _ProvedorContado(anotado)
        captura = _CapturaDoLog()
        pipeline.logger.addHandler(captura)
        inicio = relogio()
        execucao = ExecucaoPipeline(numero, "ok")
        try:
            with limites_da_geracao(relogio() + settings.job_timeout_segundos, None):
                pipeline._gerar_conteudo(contado, prompt, formato, avisar_revisao=lambda: None)
        except Exception as exc:  # noqa: BLE001 - o diagnóstico registra qualquer falha
            execucao.resultado, execucao.erro = "falha", _erro_final(exc)
        finally:
            pipeline.logger.removeHandler(captura)
        execucao.duracao_s = round(relogio() - inicio, 2)
        execucao.chamadas = contado.chamadas
        for indice, chamada in enumerate(anotado.chamadas):
            if indice < len(captura.registros):
                resultado, motivo = captura.registros[indice]
            elif execucao.resultado == "ok":
                resultado, motivo = VALIDA, None
            else:  # erro que o pipeline não repete (timeout, limite de uso...): sobe sem log
                resultado, motivo = execucao.erro or OUTRO, None
            execucao.tentativas.append(Tentativa(indice + 1, resultado, motivo, **chamada))
        execucoes.append(execucao)
        avisar(execucao)
    return execucoes


def resumo_via_pipeline(execucoes: list[ExecucaoPipeline]) -> dict:
    # No resumo, a posição do erro de JSON sai para juntar as tentativas do mesmo tipo.
    tentativas = Counter(
        f"{t.resultado}: {_POSICAO_NO_MOTIVO.sub('', t.motivo)}" if t.motivo else t.resultado
        for e in execucoes for t in e.tentativas
    )
    return {
        "execucoes_ok": sum(e.resultado == "ok" for e in execucoes),
        "execucoes_com_falha": sum(e.resultado == "falha" for e in execucoes),
        "chamadas": sum(e.chamadas for e in execucoes),
        "tentativas": dict(tentativas.most_common()),
    }


# ── Relatório ─────────────────────────────────────────────────────────────────


def _v(valor) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, float):
        return f"{valor:g}".replace(".", ",")
    return str(valor)


def resumo(diagnosticos: list[Diagnostico]) -> dict[str, int]:
    contagem = Counter(d.categoria for d in diagnosticos)
    return {c: contagem[c] for c in CATEGORIAS if contagem[c]}


def montar_relatorio(diagnosticos: list[Diagnostico], config: dict, quando: datetime) -> str:
    linhas = [
        f"# Diagnóstico das respostas, {quando:%Y-%m-%d %H:%M}", "",
        f"- Provedor: {config['provedor']}; modelo: `{config['modelo']}`",
        f"- Raciocínio: {config['raciocinio']}; max_tokens: {config['max_tokens']}; "
        f"orçamento de raciocínio: {config['orcamento_raciocinio']}",
        f"- Formato: {config['formato']}; documento: {config['documento']}; chamadas: {config['n']}; "
        f"recuperação: lexical (k=6)",
        "- Só metadados: nada do documento nem do conteúdo gerado.", "",
        "## Resumo por categoria", "",
        "| Categoria | Respostas |", "|---|---|",
        *[f"| {c} | {n} |" for c, n in resumo(diagnosticos).items()], "",
        "## Respostas", "",
        "| # | Categoria | Mensagem | Caminho | Tamanho | Motivo de fim | Tokens (resposta / total) "
        "| Posição (fração) | Sinais | Tempo (s) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in diagnosticos:
        linhas.append(
            f"| {d.chamada} | {d.categoria} | {_v(d.mensagem)} | {_v(d.caminho)} | {_v(d.tamanho)} "
            f"| {_v(d.motivo_fim)} | {_v(d.tokens_resposta)} / {_v(d.tokens_total)} "
            f"| {_v(d.posicao)} ({_v(d.posicao_relativa)}) | {', '.join(d.sinais) or '—'} | {_v(d.duracao_s)} |"
        )
    return "\n".join(linhas) + "\n"


def montar_relatorio_via_pipeline(execucoes: list[ExecucaoPipeline], config: dict, quando: datetime) -> str:
    r = resumo_via_pipeline(execucoes)
    linhas = [
        f"# Diagnóstico pelo caminho da geração, {quando:%Y-%m-%d %H:%M}", "",
        f"- Provedor: {config['provedor']}; modelo: `{config['modelo']}`",
        f"- Raciocínio: {config['raciocinio']}; max_tokens: {config['max_tokens']}; "
        f"orçamento de raciocínio: {config['orcamento_raciocinio']}",
        f"- Timeout por chamada: {config['timeout_s']} s; prazo do job: {config['prazo_job_s']} s; "
        f"retentativas de falha transitória: {config['tentativas_transitorias']}",
        f"- Formato: {config['formato']}; documento: {config['documento']}; gerações: {config['n']}; "
        f"recuperação: lexical (k=6)",
        "- Cada geração passa por `pipeline._gerar_conteudo` (até 2 tentativas), como o redator do grafo.",
        "- Só metadados: nada do documento nem do conteúdo gerado.", "",
        "## Resumo", "",
        f"- Gerações ok: {r['execucoes_ok']}; com falha: {r['execucoes_com_falha']}; chamadas: {r['chamadas']}",
        "", "| Tentativa (tipo: motivo do log) | Vezes |", "|---|---|",
        *[f"| {chave} | {vezes} |" for chave, vezes in r["tentativas"].items()], "",
        "## Tentativas", "",
        "| Geração | Resultado | Chamadas | Tempo (s) | Tentativa | Tipo | Motivo | Motivo de fim "
        "| Tokens (resposta / total) | Timeout (s) | Tempo da chamada (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in execucoes:
        resultado = e.resultado if not e.erro else f"{e.resultado} ({e.erro})"
        for t in e.tentativas or [Tentativa(0, "—")]:
            linhas.append(
                f"| {e.execucao} | {resultado} | {e.chamadas} | {_v(e.duracao_s)} | {t.tentativa} | {t.resultado} "
                f"| {_v(t.motivo)} | {_v(t.motivo_fim)} | {_v(t.tokens_resposta)} / {_v(t.tokens_total)} "
                f"| {_v(t.timeout_s)} | {_v(t.duracao_s)} |"
            )
    return "\n".join(linhas) + "\n"


def gravar(markdown: str, dados: dict, quando: datetime, pasta: Path = RELATORIOS) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    base = pasta / f"diagnostico_resposta_{quando:%Y%m%d_%H%M%S}"
    md, js = base.with_suffix(".md"), base.with_suffix(".json")
    md.write_text(markdown, encoding="utf-8")
    js.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return md, js


# ── Linha de comando ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None, *, provedor=None, pasta_relatorios: Path = RELATORIOS,
         relogio=time.monotonic, dormir=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Diagnostica respostas inválidas do modelo na geração.")
    parser.add_argument("--formato", default=FORMATO_PADRAO, help=", ".join(get_args(FormatoSaida)))
    parser.add_argument("--documento", default=DOCUMENTO_PADRAO, help="arquivo de data/exemplos/")
    parser.add_argument("--n", type=int, default=N_PADRAO, help="chamadas ao provedor")
    parser.add_argument("--intervalo", type=float, default=None,
                        help=f"segundos entre chamadas (padrão {INTERVALO_PADRAO_SEGUNDOS:g}; 0 no simulado)")
    parser.add_argument("--simulado", action="store_true", help="provedor falso que reproduz cada categoria")
    parser.add_argument("--via-pipeline", action="store_true",
                        help="cada geração pelo pipeline._gerar_conteudo (2 tentativas), como na medição")
    args = parser.parse_args(argv)

    disponiveis = sorted(p.name for p in EXEMPLOS.glob("*.md"))
    intervalo = args.intervalo if args.intervalo is not None else (0.0 if args.simulado else INTERVALO_PADRAO_SEGUNDOS)
    if args.formato not in get_args(FormatoSaida) or args.documento not in disponiveis or args.n < 1 or intervalo < 0:
        print(f"Opção inválida. Formatos: {', '.join(get_args(FormatoSaida))}; documentos: "
              f"{', '.join(disponiveis)}; --n a partir de 1.", file=sys.stderr)
        return 2

    nome = settings.llm_provider.strip().lower()
    if provedor is None:
        if args.simulado:
            provedor = ProvedorSimulado()
        else:
            if nome == "nvidia" and not settings.nvidia_nim_api_key.get_secret_value():
                print("NVIDIA_NIM_API_KEY não definida no ambiente. Use --simulado para testar sem chave.",
                      file=sys.stderr)
                return 2
            if nome == "gemini" and not settings.google_api_key:
                print("GOOGLE_API_KEY não definida no ambiente. Use --simulado para testar sem chave.",
                      file=sys.stderr)
                return 2
            from app.llm import obter_provedor

            provedor = obter_provedor()
    simulado = args.simulado or isinstance(_base(provedor), ProvedorSimulado)
    config = {
        "provedor": "simulado" if simulado else nome,
        "modelo": "simulado" if simulado else (
            settings.nvidia_nim_modelo if nome == "nvidia" else settings.modelo_llm),
        "raciocinio": "—" if simulado else (settings.nvidia_nim_raciocinio or "padrão do modelo"),
        "max_tokens": "—" if simulado else settings.nvidia_nim_max_tokens,
        "orcamento_raciocinio": "—" if simulado else (settings.nvidia_nim_orcamento_raciocinio or "não enviado"),
        "formato": args.formato, "documento": args.documento, "n": args.n, "intervalo_s": intervalo,
    }
    prompt = montar_prompt(carregar_documento(EXEMPLOS / args.documento), args.formato)
    ritmo = Ritmo(intervalo, dormir=dormir, relogio=relogio)

    if args.via_pipeline:
        config.update(via_pipeline=True, timeout_s=settings.llm_timeout_segundos,
                      prazo_job_s=settings.job_timeout_segundos, tentativas_transitorias=settings.llm_tentativas)

        def avisar_execucao(e: ExecucaoPipeline) -> None:
            passos = "; ".join(f"{t.resultado}" + (f" ({t.motivo})" if t.motivo else "") for t in e.tentativas)
            print(f"geração {e.execucao}: {e.resultado} | {e.chamadas} chamada(s) | {_v(e.duracao_s)} s | {passos}",
                  flush=True)

        execucoes = diagnosticar_via_pipeline(provedor, prompt, args.formato, args.n, ritmo,
                                              relogio=relogio, avisar=avisar_execucao)
        agora = datetime.now()
        r = resumo_via_pipeline(execucoes)
        md, js = gravar(
            montar_relatorio_via_pipeline(execucoes, config, agora),
            {"quando": agora.isoformat(timespec="seconds"), "configuracao": config, "resumo": r,
             "execucoes": [asdict(e) for e in execucoes]},
            agora, pasta_relatorios,
        )
        print(f"\nGerações ok: {r['execucoes_ok']}; com falha: {r['execucoes_com_falha']}; "
              f"chamadas: {r['chamadas']}")
        for chave, vezes in r["tentativas"].items():
            print(f"  {chave}: {vezes}")
        print(f"\nRelatórios: {md} e {js}")
        return 0

    def avisar(d: Diagnostico) -> None:
        print(f"chamada {d.chamada}: {d.categoria} | {d.mensagem or '—'} | tamanho {_v(d.tamanho)} "
              f"| fim {_v(d.motivo_fim)} | {_v(d.duracao_s)} s", flush=True)

    diagnosticos = diagnosticar(provedor, prompt, args.formato, args.n, ritmo, relogio=relogio, avisar=avisar)
    agora = datetime.now()
    md, js = gravar(
        montar_relatorio(diagnosticos, config, agora),
        {"quando": agora.isoformat(timespec="seconds"), "configuracao": config,
         "resumo": resumo(diagnosticos), "respostas": [asdict(d) for d in diagnosticos]},
        agora, pasta_relatorios,
    )
    print("\nResumo por categoria:")
    for categoria, total in resumo(diagnosticos).items():
        print(f"  {categoria}: {total}")
    print(f"\nRelatórios: {md} e {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
