"""BM25 em Python puro (app/services/busca_lexical.py)."""

from app.services.busca_lexical import IndiceBM25, tokenizar

TRECHOS = [
    ("T1", "O método GET busca um recurso no servidor sem alterá-lo."),
    ("T2", "O método POST cria um recurso novo; a requisição leva um corpo."),
    ("T3", "Índices aceleram consultas SQL em tabelas grandes."),
    ("T4", "A fotossíntese converte luz em energia química."),
]


def _ids(resultado):
    return [trecho[0] for trecho, _p in resultado]


def test_tokenizar_tira_acento_caixa_stopwords_e_curtos():
    assert tokenizar("O Índice É da TABELA e x") == ["indice", "tabela"]
    assert tokenizar("métodos Métodos METODO") == ["metodo", "metodo", "metodo"]
    assert tokenizar("para com que isso de a") == []


def test_ordena_por_relevancia():
    indice = IndiceBM25(TRECHOS)
    assert _ids(indice.buscar("índices em consultas SQL"))[0] == "T3"
    assert _ids(indice.buscar("criar recurso novo com POST"))[0] == "T2"


def test_acento_e_caixa_nao_atrapalham():
    indice = IndiceBM25(TRECHOS)
    assert _ids(indice.buscar("FOTOSSINTESE")) == ["T4"]
    assert _ids(indice.buscar("indice")) == _ids(indice.buscar("ÍNDICES"))


def test_stopwords_nao_pontuam():
    indice = IndiceBM25(TRECHOS)
    assert indice.buscar("o um a de em sem") == []


def test_pontuacao_zero_fica_de_fora():
    indice = IndiceBM25(TRECHOS)
    resultado = indice.buscar("método")
    assert _ids(resultado) == ["T1", "T2"]
    assert all(p > 0 for _t, p in resultado)
    assert indice.buscar("blockchain") == []
    assert IndiceBM25([]).buscar("qualquer") == []


def test_deterministico_e_desempate_pela_posicao():
    iguais = [("A", "rede virtual"), ("B", "outra coisa"), ("C", "rede virtual"), ("D", "rede virtual")]
    indice = IndiceBM25(iguais)
    primeiro = indice.buscar("rede virtual")
    assert _ids(primeiro) == ["A", "C", "D"]
    assert [indice.buscar("rede virtual") for _ in range(5)] == [primeiro] * 5
    assert _ids(IndiceBM25(list(iguais)).buscar("rede virtual")) == ["A", "C", "D"]


def test_k_limita_e_indice_e_reutilizavel():
    indice = IndiceBM25(TRECHOS)
    assert len(indice.buscar("recurso método", k=1)) == 1
    assert _ids(indice.buscar("energia")) == ["T4"]
    assert _ids(indice.buscar("servidor")) == ["T1"]
    assert len(indice) == 4


def test_termo_raro_pesa_mais_que_comum():
    indice = IndiceBM25(TRECHOS)
    # "recurso" aparece em 2 trechos; "corpo" só em 1.
    resultado = dict((t[0], p) for t, p in indice.buscar("recurso corpo"))
    assert resultado["T2"] > resultado["T1"]
