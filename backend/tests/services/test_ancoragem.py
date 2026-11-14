"""Ancoragem na fonte e clareza do material gerado (app/services/ancoragem.py)."""

from __future__ import annotations

import pytest

from app.models import (
    AvaliacaoQualidade,
    ConteudoFlashcards,
    ConteudoMarkdown,
    ConteudoQuiz,
    FlashcardItem,
    QuizItem,
)
from app.services.ancoragem import (
    MIN_SECOES_MARKDOWN,
    PALAVRAS_POR_FRASE_ALTA,
    PALAVRAS_GENERICAS,
    PALAVRAS_POR_FRASE_BAIXA,
    STOPWORDS,
    calcular_ancoragem,
    calcular_clareza,
    cobertura,
    itens_do_markdown,
    itens_medidos,
    normalizar,
    radical,
    termos,
    vocabulario_da_fonte,
)
from app.services.pipeline import _avaliar_qualidade

FONTE = (
    "O HTTP é o protocolo usado pela web para trocar mensagens entre cliente e servidor. "
    "Cada troca tem uma requisição, enviada pelo cliente, e uma resposta, devolvida pelo "
    "servidor. O método GET busca um recurso sem alterá-lo. O método POST cria um recurso "
    "novo. O método DELETE remove o recurso. Um método é idempotente quando repetir a mesma "
    "requisição produz o mesmo resultado. O código 404 indica recurso não encontrado e o "
    "código 500 indica erro interno do servidor."
)

# (título, introdução, pares de frente/verso) fiéis à FONTE e inventados no mesmo tema.
FIEL = (
    "Métodos do protocolo HTTP",
    "O protocolo HTTP troca mensagens entre cliente e servidor com requisição e resposta.",
    [
        ("Método GET", "Busca um recurso no servidor."),
        ("Método POST", "Cria um recurso novo."),
        ("Método DELETE", "Remove o recurso."),
        ("Código 404", "Indica recurso não encontrado."),
    ],
)
INVENTADO = (
    "Arquitetura GraphQL moderna",
    "GraphQL organiza esquemas tipados e resolvers para consultas flexíveis.",
    [
        ("Mutation", "Altera dados usando resolvers tipados."),
        ("Subscription", "Envia eventos através de websockets persistentes."),
        ("Fragmento", "Reaproveita campos entre consultas complexas."),
        ("Introspecção", "Descobre o esquema completo em tempo real."),
    ],
)


def _flashcards(dados) -> ConteudoFlashcards:
    titulo, intro, pares = dados
    return ConteudoFlashcards(
        titulo=titulo,
        introducao_contextualizada=intro,
        itens=[FlashcardItem(frente=f, verso=v) for f, v in pares],
    )


def _quiz(dados, distratores=None, explicacoes=None) -> ConteudoQuiz:
    titulo, intro, pares = dados
    itens = []
    for i, (frente, verso) in enumerate(pares):
        distrator = (distratores or ["Outra alternativa qualquer"])[i % len(distratores or [1])]
        itens.append(QuizItem(
            pergunta=f"O que faz {frente}?",
            opcoes=[distrator, verso],
            resposta_correta=1,
            explicacao=(explicacoes[i] if explicacoes else verso),
        ))
    return ConteudoQuiz(titulo=titulo, introducao_contextualizada=intro, itens=itens)


def _tutorial(dados) -> ConteudoMarkdown:
    titulo, intro, pares = dados
    passos = "\n\n".join(f"## Passo {i}\n\n{f}: {v}" for i, (f, v) in enumerate(pares, 1))
    return ConteudoMarkdown(titulo=titulo, introducao_contextualizada=intro, itens=passos)


def _resumo(dados) -> ConteudoMarkdown:
    titulo, intro, pares = dados
    lista = "\n".join(f"- **{f}**: {v}" for f, v in pares)
    return ConteudoMarkdown(
        titulo=titulo,
        introducao_contextualizada=intro,
        itens=f"## Pontos-chave\n\n{lista}\n\n## Conclusão\n\n{pares[0][1]}",
    )


CONSTRUTORES = {
    "Flashcards": _flashcards,
    "Quiz": _quiz,
    "Tutorial": _tutorial,
    "ResumoExecutivo": _resumo,
}


def _ancoragem(conteudo, relevancia=0.5, fonte=FONTE):
    return calcular_ancoragem(conteudo, fonte, relevancia)


# ── Fiel x inventado nos quatro formatos ─────────────────────────────────────


@pytest.mark.parametrize("formato", list(CONSTRUTORES))
def test_conteudo_fiel_tem_nota_bem_maior_que_inventado(formato):
    fiel = _ancoragem(CONSTRUTORES[formato](FIEL))
    inventado = _ancoragem(CONSTRUTORES[formato](INVENTADO))
    assert fiel >= 0.8
    assert inventado <= 0.2
    assert fiel - inventado >= 0.6


# ── Quiz: distratores e explicação ───────────────────────────────────────────


def test_quiz_distratores_absurdos_nao_derrubam_a_nota():
    plausivel = _quiz(FIEL, distratores=["Atualiza o recurso inteiro."])
    absurdo = _quiz(FIEL, distratores=["Teletransporta zeppelins quânticos", "Hipopótamo laranja"])
    assert _ancoragem(absurdo) == _ancoragem(plausivel)
    assert "zeppelins" not in " ".join(itens_medidos(absurdo)).lower()


def test_quiz_explicacao_inventada_derruba_a_nota():
    fiel = _quiz(FIEL)
    # Explicações do tamanho usual (a parte mais longa do item): como cada item
    # junta pergunta, opção correta e explicação, e cada item vale
    # min(1, cobertura / COBERTURA_DE_REFERENCIA), uma explicação inventada curta
    # quase não derrubaria o item.
    inventada = _quiz(FIEL, explicacoes=[
        "Kubernetes orquestra contêineres distribuídos em clusters elásticos com réplicas.",
        "Terraform provisiona infraestrutura declarativa versionada em nuvens públicas.",
        "Ansible configura máquinas remotas através de playbooks escritos em YAML.",
        "Prometheus coleta métricas temporais e dispara alertas para plantonistas.",
    ])
    # Medido: 1,0 -> 0,729. Era >= 0,3 antes da escala por COBERTURA_DE_REFERENCIA.
    assert _ancoragem(fiel) - _ancoragem(inventada) >= 0.25


def test_quiz_mede_so_a_opcao_correta():
    quiz = _quiz(FIEL, distratores=["Distrator"])
    assert all("Distrator" not in item for item in itens_medidos(quiz))
    assert any("Busca um recurso no servidor." in item for item in itens_medidos(quiz))


# ── Independência da recuperação ─────────────────────────────────────────────


@pytest.mark.parametrize("formato", list(CONSTRUTORES))
def test_ancoragem_nao_depende_da_relevancia(formato):
    conteudo = CONSTRUTORES[formato](FIEL)
    baixa = _avaliar_qualidade(0.2, conteudo, FONTE)
    alta = _avaliar_qualidade(0.95, conteudo, FONTE)
    assert baixa == alta


# ── Média por item ───────────────────────────────────────────────────────────


def test_item_inventado_pesa_mais_que_na_contagem_diluida():
    titulo, intro, pares = FIEL
    # Itens fiéis longos (só palavras da fonte) e um item inventado curto.
    pares_longos = [
        ("Método GET", "Busca um recurso sem alterá-lo; a resposta é devolvida pelo servidor ao cliente."),
        ("Método POST", "Cria um recurso novo; a requisição é enviada pelo cliente ao servidor."),
        ("Método DELETE", "Remove o recurso; a resposta é devolvida pelo servidor ao cliente."),
        ("Código 404", "Indica recurso não encontrado na resposta devolvida pelo servidor."),
    ]
    so_fieis = _flashcards((titulo, intro, pares_longos))
    conteudo = _flashcards((titulo, intro, pares_longos + [("Kafka", "Particiona tópicos")]))
    fonte = vocabulario_da_fonte(FONTE)
    diluida = cobertura(" ".join(itens_medidos(conteudo)), fonte)
    por_item = _ancoragem(conteudo)
    assert _ancoragem(so_fieis) == 1.0
    assert por_item == round(6 / 7, 4)  # 6 itens fiéis (título, introdução, 4 cartões) e 1 inventado
    # Contando termos, os 3 termos inventados somem entre ~26 da fonte (~0,885).
    assert diluida - por_item >= 0.02


# ── Normalização, flexão e markdown ──────────────────────────────────────────


def test_acentos_e_maiusculas_nao_mudam_a_nota():
    titulo, intro, pares = FIEL
    gritado = (titulo.upper(), normalizar(intro).upper(), [(f.upper(), normalizar(v)) for f, v in pares])
    assert _ancoragem(_flashcards(gritado)) == _ancoragem(_flashcards(FIEL))


def test_markdown_nao_muda_a_nota():
    simples = ConteudoMarkdown(
        titulo="Métodos HTTP",
        introducao_contextualizada="O protocolo HTTP troca mensagens.",
        itens="O método GET busca um recurso.\n\nO método POST cria um recurso novo.",
    )
    marcado = simples.model_copy(update={"itens": (
        "## Passo 1\n\nO método **`GET`** busca um [recurso](https://exemplo.com/x).\n\n"
        "## Passo 2\n\n- O método _POST_ cria um recurso novo."
    )})
    assert itens_do_markdown(marcado.itens) == [
        "O método GET busca um recurso.", "O método POST cria um recurso novo.",
    ]
    assert _ancoragem(marcado) == _ancoragem(simples)


def test_codigo_dentro_da_cerca_e_medido_sem_as_crases():
    itens = itens_do_markdown("Texto antes.\n\n```bash\ncurl -X DELETE\n```\n\nTexto depois.")
    assert itens == ["Texto antes.", "curl -X DELETE", "Texto depois."]


@pytest.mark.parametrize(
    "plural,singular",
    [
        ("métodos", "método"),
        ("requisições", "requisição"),
        ("servidores", "servidor"),
        ("mensagens", "mensagem"),
        ("anéis", "anel"),  # "papel", usado antes aqui, entrou na lista genérica
        ("canais", "canal"),
        ("clientes", "cliente"),
        ("recursos", "recurso"),
    ],
)
def test_plural_simples_casa_com_o_singular(plural, singular):
    assert radical(normalizar(plural)) == radical(normalizar(singular))
    assert cobertura(plural, vocabulario_da_fonte(singular)) == 1.0
    assert cobertura(singular, vocabulario_da_fonte(plural)) == 1.0


@pytest.mark.parametrize(
    "derivada,fonte",
    [
        ("idempotência", "idempotente"),
        ("versionação", "versionamento"),
        ("paginação", "paginadas"),
        # Antes não casavam; com a raiz de 6 letras, casam de propósito. O preço
        # é aceito porque o controle cruzado com saídas reais continua baixo
        # (tests/services/test_ancoragem_calibracao.py).
        ("metodologia", "método"),
        ("recursivo", "recurso"),
    ],
)
def test_derivacoes_da_mesma_raiz_casam(derivada, fonte):
    assert cobertura(derivada, vocabulario_da_fonte(fonte)) == 1.0


@pytest.mark.parametrize(
    "termo,fonte",
    [("metal", "método"), ("servir", "servidor"), ("canela", "canal"), ("4040", "404"),
     ("rede", "redirecionamento")],
)
def test_palavras_sem_relacao_nao_casam(termo, fonte):
    assert cobertura(termo, vocabulario_da_fonte(fonte)) == 0.0


def test_termos_relevantes_ignoram_stopwords_e_palavras_curtas_mas_nao_numeros():
    assert termos("Para cada uso, o GET e o 404 funcionam quando como mais") == {
        "404", radical("funcionam"),
    }


@pytest.mark.parametrize(
    "palavra",
    ["exatamente", "utilizando", "garantir", "possui", "representa", "definido",
     "importante", "desenvolvedores", "característica", "tutorial"],
)
def test_vocabulario_generico_e_ignorado(palavra):
    assert termos(palavra) == set()


@pytest.mark.parametrize(
    "termo",
    ["tabela", "chave", "commit", "branch", "consulta", "requisição", "versão",
     "recurso", "servidor", "cliente", "método", "status", "mensagem", "arquivo",
     "repositório", "contrato", "aplicativo", "funcionalidade", "revisão", "índice",
     "transação", "junção", "idempotente", "cabeçalho"],
)
def test_termos_de_dominio_nao_sao_genericos(termo):
    assert termos(termo) == {radical(normalizar(termo))}


def test_listas_de_palavras_estao_normalizadas():
    for categoria, palavras in PALAVRAS_GENERICAS.items():
        assert palavras, categoria
        assert all(p == normalizar(p) and " " not in p for p in palavras), categoria
    assert all(p == normalizar(p) and len(p) >= 4 for p in STOPWORDS)


# ── Casos degenerados ────────────────────────────────────────────────────────


def _so_stopwords() -> ConteudoMarkdown:
    return ConteudoMarkdown(
        titulo="Para",
        introducao_contextualizada="como mais quando",
        itens="## Passo\n\npara como mais quando porque pois então também ainda.",
    )


@pytest.mark.parametrize("relevancia,esperado", [(0.42, 0.42), (1.7, 1.0), (-0.3, 0.0)])
def test_sem_termos_mensuraveis_usa_a_relevancia_limitada(relevancia, esperado):
    assert _ancoragem(_so_stopwords(), relevancia=relevancia) == esperado


def test_fonte_vazia_da_zero_sem_dividir_por_zero():
    assert _ancoragem(_flashcards(FIEL), fonte="") == 0.0


@pytest.mark.parametrize("formato", list(CONSTRUTORES))
@pytest.mark.parametrize("dados", [FIEL, INVENTADO], ids=["fiel", "inventado"])
def test_resultado_sempre_entre_zero_e_um_com_quatro_casas(formato, dados):
    valor = _ancoragem(CONSTRUTORES[formato](dados))
    assert 0.0 <= valor <= 1.0
    assert valor == round(valor, 4)


# ── Clareza ──────────────────────────────────────────────────────────────────


def _frase(palavras: int) -> str:
    return " ".join(["recurso"] * palavras) + "."


def _markdown_com_frases(palavras: int, secoes: int = MIN_SECOES_MARKDOWN) -> ConteudoMarkdown:
    corpo = "\n\n".join(f"## Seção {i}\n\n{_frase(palavras)} {_frase(palavras)}" for i in range(secoes))
    return ConteudoMarkdown(titulo="Recursos", introducao_contextualizada=_frase(palavras), itens=corpo)


@pytest.mark.parametrize(
    "palavras,esperado",
    [
        (int(PALAVRAS_POR_FRASE_ALTA), "Alta"),
        (int(PALAVRAS_POR_FRASE_ALTA) + 1, "Media"),
        (int(PALAVRAS_POR_FRASE_BAIXA), "Media"),
        (int(PALAVRAS_POR_FRASE_BAIXA) + 1, "Baixa"),
    ],
)
def test_limiares_de_palavras_por_frase(palavras, esperado):
    assert calcular_clareza(_markdown_com_frases(palavras)) == esperado


@pytest.mark.parametrize(
    "palavras,esperado",
    [(int(PALAVRAS_POR_FRASE_ALTA), "Media"), (int(PALAVRAS_POR_FRASE_ALTA) + 1, "Baixa")],
)
def test_markdown_sem_secoes_suficientes_rebaixa(palavras, esperado):
    assert calcular_clareza(_markdown_com_frases(palavras, secoes=1)) == esperado


def test_introducao_curta_rebaixa():
    completo = _flashcards(FIEL)
    sem_intro = completo.model_copy(update={"introducao_contextualizada": "HTTP básico."})
    assert calcular_clareza(completo) == "Alta"
    assert calcular_clareza(sem_intro) == "Media"


def test_quiz_sem_explicacao_rebaixa():
    completo = _quiz(FIEL)
    sem_explicacao = _quiz(FIEL, explicacoes=["", "Cria um recurso novo.", "Remove.", "404."])
    assert calcular_clareza(completo) == "Alta"
    assert calcular_clareza(sem_explicacao) == "Media"


def test_flashcard_sem_verso_rebaixa():
    titulo, intro, pares = FIEL
    assert calcular_clareza(_flashcards((titulo, intro, pares[:-1] + [("Código 500", " ")]))) == "Media"


def test_clareza_nao_depende_da_relevancia_nem_da_ancoragem():
    curto = _flashcards(FIEL)
    # Mesmas palavras da fonte (ancoragem igual), em frases longas demais.
    longo = curto.model_copy(update={
        "introducao_contextualizada": " ".join([FIEL[1][:-1]] * 4) + ".",
        "itens": [
            FlashcardItem(frente=f, verso=" ".join([v[:-1]] * 8) + ".") for f, v in FIEL[2]
        ],
    })
    assert _ancoragem(curto) == _ancoragem(longo) == 1.0
    assert calcular_clareza(curto) == "Alta"
    assert calcular_clareza(longo) == "Baixa"
    for relevancia in (0.0, 0.2, 0.95, 1.0):
        assert _avaliar_qualidade(relevancia, curto, FONTE).clareza_pedagogica == "Alta"


# ── Contrato ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("formato", list(CONSTRUTORES))
@pytest.mark.parametrize("dados", [FIEL, INVENTADO], ids=["fiel", "inventado"])
def test_avaliacao_valida_no_esquema_nos_quatro_formatos(formato, dados):
    avaliacao = _avaliar_qualidade(0.75, CONSTRUTORES[formato](dados), FONTE)
    assert AvaliacaoQualidade.model_validate(avaliacao.model_dump()) == avaliacao
    assert avaliacao.clareza_pedagogica in {"Alta", "Media", "Baixa"}
    assert avaliacao.observacoes is None
