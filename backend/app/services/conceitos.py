"""Conceitos-chave do material gerado (``MetadadosAdaptacao.conceitos_chave``).

O LLM devolve os conceitos no mesmo JSON do conteúdo (campo opcional
``conceitos_chave``). ``escolher_conceitos`` aproveita só os itens que passam
em ``validar_conceitos`` e, se nenhum passar, usa ``conceitos_fallback``,
calculado a partir do título e dos trechos recuperados, sem nova chamada.

Para cortar mais palavras genéricas ou estruturais, acrescente-as (em
minúsculas e sem acento) a ``PALAVRAS_GENERICAS``; validação e fallback usam
a mesma lista.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

MAX_CONCEITOS = 8
MAX_CARACTERES = 60  # por conceito

# Palavras que sozinhas não são conceito: artigos, preposições, conjunções,
# pronomes, quantificadores, advérbios e verbos comuns, numerais e termos
# estruturais de documento. Sempre em minúsculas e sem acento.
PALAVRAS_GENERICAS: frozenset[str] = frozenset(
    """
    o a os as um uma uns umas
    de do da dos das em no na nos nas por pelo pela pelos pelas para pra
    com sem sob sobre entre ate apos ante desde contra ao aos
    e ou mas porem contudo todavia que se como quando porque pois entao logo
    tambem nem enquanto embora caso conforme
    este esta estes estas esse essa esses essas aquele aquela aqueles aquelas
    isto isso aquilo ele ela eles elas voce voces eu nos lhe lhes
    seu sua seus suas meu minha meus minhas nosso nossa nossos nossas
    cada todo toda todos todas tudo outro outra outros outras algum alguma
    alguns algumas nenhum nenhuma muito muita muitos muitas pouco pouca
    poucos poucas varios varias mesmo mesma mesmos mesmas tal tais
    qual quais quem onde aqui ali la mais menos ainda sempre nunca nao sim
    apenas so bem ja agora depois antes novamente assim
    ser sao foi era sera estar estao ter tem tinha haver ha pode podem
    deve devem faz fazer usar use usa veja vamos
    dois duas tres quatro cinco primeiro primeira segundo segunda terceiro
    terceira ultimo ultima
    introducao conclusao resumo texto exemplo exemplos capitulo secao
    topico topicos parte item itens lista nota notas observacao figura tabela
    anexo sumario indice documento conteudo material pagina passo etapa
    objetivo objetivos visao geral definicao conceito conceitos glossario
    referencias bibliografia licao aula modulo unidade simulado teste testes
    """.split()
)

# Palavra capitalizada ou sigla (2+ caracteres), como no cálculo antigo.
_TERMO_CAPITALIZADO = re.compile(r"\b[A-ZÀ-Ú][A-Za-zÀ-ú0-9]+\b")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e com espaços colapsados (para comparar)."""
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def _aparar(texto: str) -> str:
    """Apara e colapsa espaços, mantendo maiúsculas e acentos (forma exibida)."""
    return " ".join(texto.split())


def _variantes(texto: str) -> set[str]:
    """Forma normalizada e, se houver plural simples, as formas sem "s"/"es".

    Só tira o plural quando o original termina em "s" minúsculo: "APIs" dá
    "api" e "Redes" dá "rede"; siglas em maiúsculas como "HTTPS" ou "DNS"
    não são tocadas.
    """
    aparado = _aparar(texto)
    normalizado = normalizar(aparado)
    variantes = {normalizado}
    if aparado.endswith("s") and len(normalizado) > 2:
        variantes.add(normalizado[:-1])
        if aparado.endswith("es") and len(normalizado) > 3:
            variantes.add(normalizado[:-2])
    return variantes


def _chave(texto: str) -> str:
    """Forma usada para deduplicar: normalizada, sem o "s" do plural simples."""
    aparado = _aparar(texto)
    normalizado = normalizar(aparado)
    if aparado.endswith("s") and len(normalizado) > 2:
        return normalizado[:-1]
    return normalizado


def _so_generico(normalizado: str) -> bool:
    palavras = re.findall(r"\w+", normalizado)
    return all(p in PALAVRAS_GENERICAS for p in palavras)


def _padrao_ocorrencia(texto: str) -> re.Pattern[str]:
    """Regex do termo no texto normalizado, aceitando o plural simples."""
    variantes = sorted(_variantes(texto), key=len, reverse=True)
    alternativas = "|".join(re.escape(v) for v in variantes)
    return re.compile(rf"(?<!\w)(?:{alternativas})(?:s|es)?(?!\w)")


def validar_conceitos(candidatos: object, *, titulo: str, texto_origem: str) -> list[str]:
    """Conceitos do LLM aproveitáveis, na ordem recebida, no máximo ``MAX_CONCEITOS``.

    Aceita qualquer valor (o campo vem cru do JSON): o que não for lista
    devolve ``[]``. Descarta itens que não são texto, com 1 caractere, com mais
    de ``MAX_CARACTERES``, duplicados (sem diferenciar maiúsculas, acentos e
    plural simples), formados só por palavras genéricas, iguais ao título ou
    que não aparecem no texto de origem.
    """
    if not isinstance(candidatos, list):
        return []
    origem = normalizar(texto_origem)
    titulo_normalizado = normalizar(titulo)
    vistos: set[str] = set()
    aceitos: list[str] = []
    for item in candidatos:
        if not isinstance(item, str):
            continue
        termo = _aparar(item)
        normalizado = normalizar(termo)
        if len(normalizado) < 2 or len(termo) > MAX_CARACTERES:
            continue
        chave = _chave(termo)
        if chave in vistos:
            continue
        if _so_generico(normalizado) or normalizado == titulo_normalizado:
            continue
        if not _padrao_ocorrencia(termo).search(origem):
            continue
        vistos.add(chave)
        aceitos.append(termo)
        if len(aceitos) == MAX_CONCEITOS:
            break
    return aceitos


def conceitos_fallback(titulo: str, trechos: Iterable[str]) -> list[str]:
    """Termos capitalizados e siglas do título e dos trechos, por relevância.

    Ordena pela frequência nos trechos recuperados e, no empate, pela ordem de
    aparição. Sem duplicados, palavras genéricas ou termos de 1 caractere; no
    máximo ``MAX_CONCEITOS``. Se nada sobrar, devolve o título (aparado a
    ``MAX_CARACTERES``), para sempre haver ao menos um item.
    """
    trechos = list(trechos)
    trechos_normalizados = normalizar(" ".join(trechos))
    candidatos: dict[str, str] = {}  # chave -> primeira forma encontrada
    for termo in _TERMO_CAPITALIZADO.findall(" ".join([titulo, *trechos])):
        normalizado = normalizar(termo)
        if len(normalizado) < 2 or _so_generico(normalizado):
            continue
        candidatos.setdefault(_chave(termo), termo)

    ordem = list(candidatos.values())
    frequencia = {
        termo: len(_padrao_ocorrencia(termo).findall(trechos_normalizados)) for termo in ordem
    }
    ordenados = sorted(ordem, key=lambda t: (-frequencia[t], ordem.index(t)))
    if ordenados:
        return ordenados[:MAX_CONCEITOS]

    titulo_aparado = _aparar(titulo)[:MAX_CARACTERES].strip()
    if titulo_aparado:
        return [titulo_aparado]
    primeiro_trecho = next((_aparar(t) for t in trechos if t.strip()), "")
    return [primeiro_trecho[:MAX_CARACTERES].strip() or "Conceito"]


def escolher_conceitos(
    candidatos: object, *, titulo: str, texto_origem: str, trechos: Iterable[str]
) -> list[str]:
    """Conceitos do LLM se algum for válido; senão, o fallback."""
    return validar_conceitos(candidatos, titulo=titulo, texto_origem=texto_origem) or (
        conceitos_fallback(titulo, trechos)
    )
