"""QuizItem: resposta_correta precisa apontar para uma das opções (contrato do frontend)."""

import pytest
from pydantic import ValidationError

from app.models import QuizItem


def _item(resposta_correta, opcoes=("GET", "POST", "PUT")):
    return QuizItem(pergunta="Qual?", opcoes=list(opcoes), resposta_correta=resposta_correta, explicacao="Porque.")


@pytest.mark.parametrize("indice", [0, 2])
def test_indice_valido_passa(indice):
    assert _item(indice).resposta_correta == indice


def test_indice_igual_ao_numero_de_opcoes_falha():
    with pytest.raises(ValidationError) as erro:
        _item(3)
    (e,) = erro.value.errors()
    assert (e["loc"], e["type"]) == (("resposta_correta",), "resposta_fora_das_opcoes")


def test_indice_negativo_falha():
    with pytest.raises(ValidationError) as erro:
        _item(-1)
    assert erro.value.errors()[0]["type"] == "greater_than_equal"


def test_opcoes_invalidas_nao_mascaram_o_erro():
    # Com as opções recusadas, só o erro delas aparece (o índice não é conferido).
    with pytest.raises(ValidationError) as erro:
        _item(5, opcoes=["só uma"])
    assert [e["loc"] for e in erro.value.errors()] == [("opcoes",)]
