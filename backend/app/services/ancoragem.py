"""Avaliação de qualidade do material gerado, sem chamar o LLM nem os embeddings.

Ancoragem (``ancoragem_fonte_score``): para cada item medido do conteúdo
gerado, a fração dos seus termos relevantes que aparecem no texto completo do
documento, relativa a ``COBERTURA_DE_REFERENCIA`` (limitada a 1); a nota é a
média por item, então um item inventado puxa a nota para baixo em vez de ser
diluído entre os outros. É uma medida lexical: indica risco de conteúdo sem
base na fonte, não prova fidelidade.

Clareza (``clareza_pedagogica``): indicador de estrutura e legibilidade (média
de palavras por frase e completude da estrutura), não um julgamento didático.

Para ignorar mais palavras na ancoragem, acrescente-as (em minúsculas e sem
acento) a ``STOPWORDS`` (palavras funcionais, comparadas inteiras) ou a uma das
categorias de ``PALAVRAS_GENERICAS`` (comparadas pela raiz, então basta o lema).

Calibração (12 saídas reais, 3 documentos x 4 formatos; ajuste em
``http_apis_rest`` e ``git_versionamento``, validação em ``sql_consultas``):
os valores medidos estão em tests/services/test_ancoragem_calibracao.py.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from app.models import ConteudoAdaptado, ConteudoFlashcards, ConteudoQuiz

MIN_LETRAS_TERMO = 4  # termos com menos letras são ignorados (exceto números)
TAMANHO_RAIZ = 6  # a raiz é o termo sem o plural simples, cortado neste tamanho
# Cobertura de um item fiel típico. Uma paráfrase fiel sempre acrescenta
# vocabulário próprio (conectivos, elaboração em registro técnico), então a
# cobertura bruta de um item fiel fica perto de 0,6, não de 1. Cada item vale
# min(1, cobertura / COBERTURA_DE_REFERENCIA). O valor é a mediana da cobertura
# dos itens fiéis no treino da calibração (0,64), arredondada.
COBERTURA_DE_REFERENCIA = 0.65

# Palavras funcionais do português (artigos, preposições, pronomes, conectivos,
# numerais, verbos auxiliares), com 4 letras ou mais: as menores já são
# ignoradas por MIN_LETRAS_TERMO. Comparadas inteiras (só sem o plural), para
# que "contra" não engula "contrato". Sempre em minúsculas e sem acento.
STOPWORDS: frozenset[str] = frozenset(
    """
    para pelo pela pelos pelas como mais menos quando porque pois entao tambem
    esse essa esses essas este esta estes estas isso isto aquele aquela
    aqueles aquelas aquilo seus suas nosso nossa nossos nossas minha minhas
    cada todo toda todos todas tudo nada algo outro outra outros outras
    muito muita muitos muitas pouco pouca poucos poucas ainda apenas sempre
    nunca onde qual quais quem depois antes agora assim aqui entre sobre
    desde apos durante contra porem contudo embora enquanto caso mesmo mesma
    mesmos mesmas algum alguma alguns algumas nenhum nenhuma voce voces eles
    elas dele dela deles delas nele nela neles nelas numa numas
    sendo sido seja sejam seria sera serao estar estao estava estavam esteja
    teve tinha temos tenha tenham haver havia pode podem podera poderia deve
    devem deveria fazer feito fica ficam vamos veja usar usando usado usada
    forma modo tipo tipos coisa coisas vezes geral exemplo exemplos
    conforme mediante atraves perante cujo cuja cujos cujas
    dois duas tres quatro cinco seis sete oito nove segundo terceiro quarto quinto
    """.split()
)

# Vocabulário genérico de registro didático, por categoria, escrito a partir do
# português geral (não de saídas do modelo). Comparado pela raiz, então cada
# entrada cobre as flexões e derivações próximas ("utilizar" cobre "utiliza",
# "utilizando", "utilização"). Não entram termos de domínio (tabela, chave,
# commit, branch, consulta, requisição, versão...): há teste para isso.
PALAVRAS_GENERICAS: dict[str, tuple[str, ...]] = {
    "verbos frequentes": tuple("""
        ser estar ter haver fazer poder dever vir dar ver dizer falar saber querer
        ficar passar deixar levar trazer tornar permitir possibilitar usar utilizar
        empregar precisar necessitar conseguir comecar iniciar terminar continuar
        seguir manter garantir assegurar evitar ajudar facilitar melhorar aumentar
        reduzir representar significar definir possuir conter incluir apresentar
        mostrar exibir descrever explicar entender compreender conhecer lembrar
        observar notar perceber considerar existir ocorrer acontecer trabalhar
        realizar criar obter tratar chamar costumar envolver exigir oferecer
        fornecer resolver colocar pensar parecer
    """.split()),
    "verbos de aprendizagem": tuple("""
        aprender estudar praticar memorizar fixar ensinar dominar
    """.split()),
    "advérbios": tuple("""
        muito pouco sempre nunca ainda logo cedo tarde hoje agora depois antes aqui
        assim tambem apenas somente inclusive quase talvez entao porem contudo
        todavia entretanto portanto enfim alem mesmo tanto quanto demais bastante
        sobretudo
    """.split()),
    "adjetivos genéricos": tuple("""
        importante principal basico simples comum possivel necessario essencial
        fundamental util facil dificil claro correto adequado especifico diferente
        igual novo grande pequeno maior menor melhor pior primeiro ultimo seguinte
        anterior proximo certo determinado diverso varios completo inteiro pratico
        frequente tipico exato proprio tecnico teorico eficiente eficaz robusto
        moderno atual tradicional complexo especial generico global local parcial
        total relevante significativo consistente confiavel flexivel multiplo
        variado numeroso independente adicional devido
    """.split()),
    "substantivos genéricos": tuple("""
        maneira caso parte ponto aspecto questao situacao processo conceito ideia
        objetivo finalidade resultado pratica problema solucao vantagem desvantagem
        beneficio importancia necessidade capacidade possibilidade contexto cenario
        informacao conteudo material texto secao topico resumo introducao conclusao
        pessoa momento lugar abordagem analise caracteristica categoria componente
        comportamento conjunto criterio desenvolvimento diferenca efeito elemento
        estrutura estrategia fator fundamento impacto implementacao mecanismo
        modelo nivel papel principio propriedade qualidade relacao significado
        tecnica tendencia limitacao alternativa organizacao sistema
    """.split()),
    "enquadramento do material": tuple("""
        aluno estudante leitor publico iniciante desenvolvedor junior pleno senior
        lider gestor executivo profissional carreira flashcard cartao quiz tutorial
        guia licao aula modulo
    """.split()),
}
_SUFIXO_ADVERBIO = "mente"  # advérbios de modo ("exatamente", "obrigatoriamente")

# ── Clareza: limiares fixos ──────────────────────────────────────────────────
PALAVRAS_POR_FRASE_ALTA = 20.0  # média até aqui (e estrutura completa): "Alta"
PALAVRAS_POR_FRASE_BAIXA = 30.0  # média acima disto: "Baixa"
MIN_PALAVRAS_INTRODUCAO = 5  # introdução com menos palavras conta como ausente
MIN_SECOES_MARKDOWN = 2  # Tutorial e Resumo precisam de 2 títulos (##) ou mais

_TOKEN = re.compile(r"[a-z0-9]+")
_FIM_DE_FRASE = re.compile(r"[.!?]+(?:\s|$)|\n+")
_TITULO_MARKDOWN = re.compile(r"^\s{0,3}#{1,6}\s")
_LINHA_DE_LISTA = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


# ── Normalização e termos ────────────────────────────────────────────────────


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def singular(termo: str) -> str:
    """Tira só o plural simples do português.

    "metodos" -> "metodo", "requisicoes" -> "requisicao", "servidores" ->
    "servidor", "papeis" -> "papel", "canais" -> "canal", "mensagens" ->
    "mensagem". Números e palavras curtas ficam como estão.
    """
    if termo.isdigit() or len(termo) < 4 or not termo.endswith("s"):
        return termo
    for plural, forma in (("oes", "ao"), ("aes", "ao"), ("eis", "el"), ("ais", "al"),
                          ("ns", "m"), ("res", "r"), ("zes", "z")):
        if termo.endswith(plural) and len(termo) - len(plural) >= 2:
            return termo[: -len(plural)] + forma
    return termo[:-1]


def radical(termo: str) -> str:
    """Singular cortado em ``TAMANHO_RAIZ`` letras; números ficam inteiros.

    Junta flexões e derivações da mesma raiz ("idempotente"/"idempotência",
    "versionamento"/"versionação", "método"/"metodologia") sem lista de
    sufixos. Palavras com até 6 letras só perdem o plural.
    """
    forma = singular(termo)
    return forma if forma.isdigit() else forma[:TAMANHO_RAIZ]


_RAIZES_GENERICAS: frozenset[str] = frozenset(
    radical(p) for categoria in PALAVRAS_GENERICAS.values() for p in categoria
)


def _relevante(token: str) -> bool:
    if token.isdigit():
        return True
    if len(token) < MIN_LETRAS_TERMO or token in STOPWORDS or singular(token) in STOPWORDS:
        return False
    if token.endswith(_SUFIXO_ADVERBIO) and len(token) > len(_SUFIXO_ADVERBIO) + 2:
        return False
    return radical(token) not in _RAIZES_GENERICAS


def termos(texto: str) -> set[str]:
    """Raízes dos termos relevantes do texto (≥ 4 letras ou números, sem genéricos)."""
    return {radical(t) for t in _TOKEN.findall(normalizar(texto)) if _relevante(t)}


def vocabulario_da_fonte(texto: str) -> set[str]:
    """Radicais de todas as palavras do documento de origem."""
    return {radical(t) for t in _TOKEN.findall(normalizar(texto))}


# ── Itens medidos por formato ────────────────────────────────────────────────


def _sem_markdown(linha: str) -> str:
    linha = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", linha)  # links e imagens: só o texto
    linha = _TITULO_MARKDOWN.sub("", linha)
    linha = _LINHA_DE_LISTA.sub("", linha)
    linha = re.sub(r"^\s*>\s?", "", linha)  # citação
    return re.sub(r"[`*_~]", "", linha).strip()


def itens_do_markdown(markdown: str) -> list[str]:
    """Parágrafos e linhas de lista, sem a sintaxe markdown.

    Títulos (``#``) e as linhas das cercas de código (```) não entram: são a
    estrutura pedida pelo modelo de resposta ("## Passo 1", "## Conclusão").
    O código dentro da cerca entra como texto, porque o aluno o lê.
    """
    itens: list[str] = []
    paragrafo: list[str] = []

    def fechar_paragrafo() -> None:
        if paragrafo:
            itens.append(" ".join(paragrafo))
            paragrafo.clear()

    for linha in markdown.splitlines():
        if not linha.strip() or _TITULO_MARKDOWN.match(linha) or linha.strip().startswith("```"):
            fechar_paragrafo()
            continue
        if _LINHA_DE_LISTA.match(linha):
            fechar_paragrafo()
            itens.append(_sem_markdown(linha))
            continue
        paragrafo.append(_sem_markdown(linha))
    fechar_paragrafo()
    return [i for i in itens if i]


def itens_medidos(conteudo: ConteudoAdaptado) -> list[str]:
    """Textos medidos na ancoragem: título, introdução e um texto por item.

    Flashcards: frente, verso e dica. Quiz: pergunta, opção correta e
    explicação (os distratores ficam de fora, pois são inventados por
    construção). Markdown: cada parágrafo ou linha de lista.
    """
    itens = [conteudo.titulo, conteudo.introducao_contextualizada]
    if isinstance(conteudo, ConteudoFlashcards):
        itens += [" ".join(filter(None, (c.frente, c.verso, c.dica_didatica))) for c in conteudo.itens]
    elif isinstance(conteudo, ConteudoQuiz):
        for q in conteudo.itens:
            correta = q.opcoes[q.resposta_correta] if q.resposta_correta < len(q.opcoes) else ""
            itens.append(" ".join((q.pergunta, correta, q.explicacao)))
    else:
        itens += itens_do_markdown(conteudo.itens)
    return itens


# ── Ancoragem ────────────────────────────────────────────────────────────────


def cobertura(texto: str, fonte: set[str]) -> float | None:
    """Fração dos termos do texto presentes na fonte; ``None`` se não há termos."""
    proprios = termos(texto)
    if not proprios:
        return None
    return len(proprios & fonte) / len(proprios)


def nota_do_item(cobertura_do_item: float) -> float:
    """Cobertura relativa à de um item fiel típico, limitada a 1."""
    return min(1.0, cobertura_do_item / COBERTURA_DE_REFERENCIA)


def media_das_notas(itens: Iterable[str], texto_fonte: str) -> float | None:
    """Média de ``nota_do_item`` dos itens com termos; ``None`` se nenhum tem."""
    fonte = vocabulario_da_fonte(texto_fonte)
    valores = [nota_do_item(c) for c in (cobertura(i, fonte) for i in itens) if c is not None]
    return sum(valores) / len(valores) if valores else None


def calcular_ancoragem(
    conteudo: ConteudoAdaptado, texto_fonte: str, relevancia_media: float
) -> float:
    """Média, por item, da cobertura dos termos gerados no texto da fonte (0 a 1).

    Cada item vale ``min(1, cobertura / COBERTURA_DE_REFERENCIA)``.

    Sem nenhum termo mensurável, usa ``relevancia_media`` (o cálculo antigo)
    como último recurso.
    """
    media = media_das_notas(itens_medidos(conteudo), texto_fonte)
    if media is None:
        media = relevancia_media
    return round(min(1.0, max(0.0, media)), 4)


# ── Clareza ──────────────────────────────────────────────────────────────────


def _texto_legivel(conteudo: ConteudoAdaptado) -> str:
    """Texto corrido que o aluno lê, um bloco por linha (as frases não se juntam).

    A frente do flashcard fica de fora: é uma deixa curta (um termo ou uma
    pergunta), não uma frase, e baixaria a média de palavras por frase.
    """
    partes = [conteudo.introducao_contextualizada]
    if isinstance(conteudo, ConteudoFlashcards):
        partes += [p for c in conteudo.itens for p in (c.verso, c.dica_didatica) if p]
    elif isinstance(conteudo, ConteudoQuiz):
        partes += [p for q in conteudo.itens for p in (q.pergunta, q.explicacao)]
    else:
        partes += itens_do_markdown(conteudo.itens)
    return "\n".join(partes)


def palavras_por_frase(texto: str) -> float | None:
    """Média de palavras por frase; ``None`` se não há palavras."""
    frases = [f for f in _FIM_DE_FRASE.split(texto) if re.search(r"\w", f)]
    if not frases:
        return None
    return sum(len(re.findall(r"\w+", f)) for f in frases) / len(frases)


def estrutura_completa(conteudo: ConteudoAdaptado) -> bool:
    """Introdução presente e cada formato com as partes que o aluno precisa."""
    introducao = re.findall(r"\w+", conteudo.introducao_contextualizada)
    if len(introducao) < MIN_PALAVRAS_INTRODUCAO:
        return False
    if isinstance(conteudo, ConteudoFlashcards):
        return all(c.frente.strip() and c.verso.strip() for c in conteudo.itens)
    if isinstance(conteudo, ConteudoQuiz):
        return all(q.explicacao.strip() for q in conteudo.itens)
    secoes = [l for l in conteudo.itens.splitlines() if _TITULO_MARKDOWN.match(l)]
    return len(secoes) >= MIN_SECOES_MARKDOWN


def calcular_clareza(conteudo: ConteudoAdaptado) -> str:
    """"Alta", "Media" ou "Baixa" a partir de palavras por frase e da estrutura.

    - "Alta": estrutura completa e até ``PALAVRAS_POR_FRASE_ALTA`` palavras por frase.
    - "Baixa": mais de ``PALAVRAS_POR_FRASE_BAIXA``, sem texto, ou estrutura
      incompleta com frases acima de ``PALAVRAS_POR_FRASE_ALTA``.
    - "Media": o resto.
    """
    media = palavras_por_frase(_texto_legivel(conteudo))
    if media is None or media > PALAVRAS_POR_FRASE_BAIXA:
        return "Baixa"
    completa = estrutura_completa(conteudo)
    if media <= PALAVRAS_POR_FRASE_ALTA:
        return "Alta" if completa else "Media"
    return "Media" if completa else "Baixa"
