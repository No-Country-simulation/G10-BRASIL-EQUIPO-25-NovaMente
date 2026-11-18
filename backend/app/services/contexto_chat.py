"""Fontes do chat de um material: trechos do documento e do pacote, busca e seleção.

O material é identificado por ``material_id``, que no catálogo é igual ao
``adaptacao_id`` do pacote (docs/backend-alteracoes-2026-11-09.md, §10.2).

- Documento: o texto-fonte (``fonte.obter_fonte``) dividido com o mesmo
  splitter e os mesmos parâmetros do RAG da geração (``rag.chunking``). Ids
  ``F1``, ``F2``... na ordem do texto.
- Pacote: o conteúdo gerado vira texto simples, um bloco por item (título e
  introdução, cada flashcard, cada pergunta do quiz com a resposta e a
  explicação, cada seção do markdown), e os blocos são agrupados em trechos
  de até ``CHUNK_TAMANHO`` caracteres. Ids ``P1``, ``P2``...
- Material antigo, sem texto-fonte: só o pacote (base ``"pacote"``).

O índice BM25 de cada material fica num cache LRU pequeno; a remoção do
material deve chamar :func:`invalidar_material`.
"""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass, replace

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

from app.rag import chunking
from app.rag import config as config_rag
from app.services import fonte, repositorio
from app.services.busca_lexical import IndiceBM25, tokenizar
from app.services.constantes_chat import (
    BASE_DOCUMENTO_E_PACOTE,
    BASE_PACOTE,
    K_MAXIMO_BUSCA,
    MIN_CARACTERES_TRECHO_CORTADO,
    ORIGEM_DOCUMENTO,
    ORIGEM_PACOTE,
    TERMOS_PERGUNTA_CURTA,
    MaterialNaoEncontrado,
)

TAMANHO_CACHE = 32  # materiais com índice em memória


@dataclass(frozen=True)
class TrechoChat:
    id: str  # "F1", "P2"...
    origem: str  # "documento" ou "pacote"
    texto: str
    cortado: bool = False  # o texto foi cortado para caber no orçamento do contexto


@dataclass(frozen=True)
class FontesMaterial:
    material_id: str
    base: str  # "documento_e_pacote" ou "pacote"
    trechos: tuple[TrechoChat, ...]
    indice: IndiceBM25

    @property
    def por_id(self) -> dict[str, TrechoChat]:
        return {t.id: t for t in self.trechos}


# ── Texto dos trechos ─────────────────────────────────────────────────────────


def _divisor() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config_rag.CHUNK_TAMANHO,
        chunk_overlap=config_rag.CHUNK_OVERLAP,
        separators=config_rag.SEPARADORES,
        keep_separator="end",
        strip_whitespace=True,
    )


def trechos_do_documento(texto: str) -> list[str]:
    """Os mesmos trechos do RAG; texto fora dos limites do RAG é dividido sem validar."""
    try:
        return chunking.dividir_texto(texto)
    except ValueError:
        limpo = (texto or "").strip()
        return [t for t in _divisor().split_text(limpo) if t] if limpo else []


_TITULO_MD = re.compile(r"^\s{0,3}#{1,6}\s")


def _secoes_do_markdown(markdown: str) -> list[str]:
    """Uma seção por título (``#``), com o título junto; o que vem antes vira uma seção."""
    secoes: list[list[str]] = [[]]
    for linha in markdown.splitlines():
        if _TITULO_MD.match(linha) and any(l.strip() for l in secoes[-1]):
            secoes.append([])
        secoes[-1].append(linha)
    return [texto for s in secoes if (texto := "\n".join(s).strip())]


def _textos_dos_campos(valor) -> list[str]:
    """Todos os textos de um valor qualquer (dict, lista, modelo), menos o campo ``tipo``."""
    if isinstance(valor, BaseModel):
        valor = valor.model_dump()
    if isinstance(valor, str):
        return [valor] if valor.strip() else []
    if isinstance(valor, dict):
        return [t for chave, v in valor.items() if chave != "tipo" for t in _textos_dos_campos(v)]
    if isinstance(valor, (list, tuple)):
        return [t for v in valor for t in _textos_dos_campos(v)]
    return []


def blocos_do_pacote(pacote) -> list[str]:
    """Um texto por item do conteúdo gerado; formato desconhecido cai nos campos de texto."""
    conteudo = pacote.conteudo_adaptado
    titulo = getattr(conteudo, "titulo", "") or ""
    introducao = getattr(conteudo, "introducao_contextualizada", "") or ""
    blocos = ["\n".join(t for t in (titulo, introducao) if t)]
    tipo = getattr(conteudo, "tipo", None)
    itens = getattr(conteudo, "itens", None)
    if tipo == "flashcards" and isinstance(itens, list):
        for i, card in enumerate(itens, 1):
            linhas = [f"Flashcard {i}", f"Frente: {card.frente}", f"Verso: {card.verso}"]
            if card.dica_didatica:
                linhas.append(f"Dica: {card.dica_didatica}")
            blocos.append("\n".join(linhas))
    elif tipo == "quiz" and isinstance(itens, list):
        for i, questao in enumerate(itens, 1):
            letras = "abcdef"
            opcoes = [f"{letras[k]}) {o}" for k, o in enumerate(questao.opcoes)]
            correta = (
                questao.opcoes[questao.resposta_correta]
                if 0 <= questao.resposta_correta < len(questao.opcoes)
                else ""
            )
            blocos.append(
                "\n".join(
                    [f"Pergunta {i}: {questao.pergunta}", "Opções: " + "; ".join(opcoes),
                     f"Resposta correta: {correta}", f"Explicação: {questao.explicacao}"]
                )
            )
    elif tipo == "markdown" and isinstance(itens, str):
        blocos.extend(_secoes_do_markdown(itens))
    else:
        resto = {k: v for k, v in _como_dict(conteudo).items() if k not in ("titulo", "introducao_contextualizada")}
        blocos.extend(_textos_dos_campos(resto))
    conceitos = getattr(getattr(pacote, "metadados", None), "conceitos_chave", None)
    if conceitos:
        blocos.append("Conceitos-chave: " + ", ".join(conceitos))
    return [b for b in blocos if b.strip()]


def _como_dict(conteudo) -> dict:
    if isinstance(conteudo, BaseModel):
        return conteudo.model_dump()
    if isinstance(conteudo, dict):
        return conteudo
    return dict(getattr(conteudo, "__dict__", {}))


def trechos_do_pacote(pacote) -> list[str]:
    """Blocos agrupados, na ordem, em trechos de até ``CHUNK_TAMANHO`` caracteres."""
    limite = config_rag.CHUNK_TAMANHO
    trechos: list[str] = []
    atual = ""
    for bloco in blocos_do_pacote(pacote):
        partes = _divisor().split_text(bloco) if len(bloco) > limite else [bloco]
        for parte in partes:
            if atual and len(atual) + 2 + len(parte) > limite:
                trechos.append(atual)
                atual = ""
            atual = f"{atual}\n\n{parte}" if atual else parte
    if atual:
        trechos.append(atual)
    return trechos


def montar_fontes(material_id: str, pacote, texto_fonte: str | None) -> FontesMaterial:
    documento = trechos_do_documento(texto_fonte) if texto_fonte else []
    trechos = [TrechoChat(f"F{i}", ORIGEM_DOCUMENTO, t) for i, t in enumerate(documento, 1)]
    trechos += [
        TrechoChat(f"P{i}", ORIGEM_PACOTE, t) for i, t in enumerate(trechos_do_pacote(pacote), 1)
    ]
    return FontesMaterial(
        material_id=material_id,
        base=BASE_DOCUMENTO_E_PACOTE if documento else BASE_PACOTE,
        trechos=tuple(trechos),
        indice=IndiceBM25([(t.id, t.texto) for t in trechos]),
    )


# ── Cache ─────────────────────────────────────────────────────────────────────

_cache: OrderedDict[tuple[str, int, str], FontesMaterial] = OrderedDict()
_trava = threading.Lock()


def carregar_fontes(material_id: str) -> FontesMaterial:
    """Fontes do material, do cache quando a fonte e o pacote não mudaram.

    Levanta ``MaterialNaoEncontrado`` se não há pacote com esse id;
    ``repositorio.PacoteCorrompido`` sobe como está.
    """
    pacote = repositorio.obter_pacote(material_id)
    if pacote is None:
        raise MaterialNaoEncontrado("Material não encontrado.")
    texto = fonte.obter_fonte(material_id)
    chave = (material_id, len(texto) if texto else 0, pacote.criado_em)
    with _trava:
        if chave in _cache:
            _cache.move_to_end(chave)
            return _cache[chave]
    fontes = montar_fontes(material_id, pacote, texto)  # fora da trava: pode demorar
    with _trava:
        for antiga in [c for c in _cache if c[0] == material_id and c != chave]:
            del _cache[antiga]  # versão anterior do mesmo material
        _cache[chave] = fontes
        _cache.move_to_end(chave)
        while len(_cache) > TAMANHO_CACHE:
            _cache.popitem(last=False)
    return fontes


def invalidar_material(material_id: str) -> None:
    """Tira do cache o índice do material (chamar ao remover ou regerar)."""
    with _trava:
        for chave in [c for c in _cache if c[0] == material_id]:
            del _cache[chave]


def limpar_cache() -> None:
    with _trava:
        _cache.clear()


def tamanho_cache() -> int:
    with _trava:
        return len(_cache)


# ── Seleção para o prompt ─────────────────────────────────────────────────────


def montar_consulta(pergunta: str, historico: Sequence[tuple[str, str]] = ()) -> str:
    """A pergunta; se for curta (seguimento), com a última pergunta do usuário junto."""
    if len(tokenizar(pergunta)) >= TERMOS_PERGUNTA_CURTA:
        return pergunta
    anteriores = [conteudo for papel, conteudo in historico if papel == "user"]
    return f"{anteriores[-1]} {pergunta}" if anteriores else pergunta


def _cortar(texto: str, limite: int) -> str:
    """Corta no último espaço antes do limite (ou no limite, se não houver)."""
    if len(texto) <= limite:
        return texto
    corte = texto.rfind(" ", 0, limite)
    return texto[: corte if corte > limite // 2 else limite].rstrip()


def _encher(candidatos: Sequence[TrechoChat], orcamento: int) -> list[TrechoChat]:
    """Trechos na ordem até o orçamento; o último que não cabe entra cortado, se valer a pena."""
    escolhidos: list[TrechoChat] = []
    usado = 0
    for trecho in candidatos:
        sobra = orcamento - usado
        if len(trecho.texto) <= sobra:
            escolhidos.append(trecho)
            usado += len(trecho.texto)
            continue
        if sobra >= MIN_CARACTERES_TRECHO_CORTADO:
            escolhidos.append(replace(trecho, texto=_cortar(trecho.texto, sobra), cortado=True))
        break
    return escolhidos


def selecionar_trechos(
    fontes: FontesMaterial,
    pergunta: str,
    historico: Sequence[tuple[str, str]] = (),
    orcamento: int = 24_000,
) -> list[TrechoChat]:
    """Trechos para o prompt, sem passar de ``orcamento`` caracteres de texto.

    Ordem da busca BM25 sobre documento e pacote juntos. Se algum trecho do
    pacote pontuou, pelo menos um vai junto. Se nada pontuou, os primeiros
    trechos do pacote (ou do documento, se o pacote não tiver), na ordem.
    """
    achados = [trecho_id for (trecho_id, _texto), _p in fontes.indice.buscar(
        montar_consulta(pergunta, historico), K_MAXIMO_BUSCA
    )]
    por_id = fontes.por_id
    if not achados:
        pacote = [t for t in fontes.trechos if t.origem == ORIGEM_PACOTE]
        return _encher(pacote or list(fontes.trechos), orcamento)

    ranqueados = [por_id[i] for i in achados]
    escolhidos = _encher(ranqueados, orcamento)
    melhor_do_pacote = next((t for t in ranqueados if t.origem == ORIGEM_PACOTE), None)
    if melhor_do_pacote is None or any(t.origem == ORIGEM_PACOTE for t in escolhidos):
        return escolhidos
    # Abre espaço para o melhor trecho do pacote tirando os últimos escolhidos.
    while escolhidos and sum(len(t.texto) for t in escolhidos) + min(
        len(melhor_do_pacote.texto), MIN_CARACTERES_TRECHO_CORTADO
    ) > orcamento:
        escolhidos.pop()
    sobra = orcamento - sum(len(t.texto) for t in escolhidos)
    escolhidos += _encher([melhor_do_pacote], sobra)
    return escolhidos
