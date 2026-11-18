"""Ancoragem medida em 12 saídas reais (3 documentos x 4 formatos).

As saídas estão em tests/fixtures/ancoragem/ (o ``resultado`` de cada job) e
os documentos de origem em data/exemplos/. Cada saída é medida contra a fonte
do próprio documento (fiel) e contra a fonte dos outros dois (cruzado: um
falso positivo da medida, sem texto escrito à mão).

A calibração foi ajustada só com ``http_apis_rest`` e ``git_versionamento``;
``sql_consultas`` ficou de validação, medido sem novos ajustes.

Valores medidos (fiel | cruzado contra as outras duas fontes):

    http_apis_rest     Flashcards 0.908 | 0.112 0.094   Quiz  0.999 | 0.142 0.064
                       Tutorial   0.883 | 0.086 0.070   Resumo 0.906 | 0.036 0.063
    git_versionamento  Flashcards 0.930 | 0.112 0.090   Quiz  0.706 | 0.078 0.070
                       Tutorial   0.795 | 0.099 0.084   Resumo 0.787 | 0.097 0.055
    sql_consultas      Flashcards 0.842 | 0.153 0.135   Quiz  0.911 | 0.130 0.126
    (validação)        Tutorial   0.838 | 0.132 0.187   Resumo 0.732 | 0.105 0.124

Antes da calibração, o fiel ficava entre 0.359 e 0.530 e o cruzado entre 0.023
e 0.082.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import ConteudoFlashcards, ConteudoMarkdown, ConteudoQuiz
from app.services.ancoragem import calcular_ancoragem, itens_medidos, media_das_notas

_BACKEND = Path(__file__).resolve().parents[2]
_FIXTURES = _BACKEND / "tests" / "fixtures" / "ancoragem"
_EXEMPLOS = _BACKEND / "data" / "exemplos"

DOCUMENTOS = ["http_apis_rest", "git_versionamento", "sql_consultas"]
FORMATOS = ["Flashcards", "Quiz", "Tutorial", "ResumoExecutivo"]
_CLASSES = {"flashcards": ConteudoFlashcards, "quiz": ConteudoQuiz, "markdown": ConteudoMarkdown}

FIEL_MINIMO = 0.70  # alvo; menor fiel medido: 0.706
CRUZADO_MAXIMO = 0.30  # maior cruzado medido: 0.187
SEPARACAO_MINIMA = 0.45  # menor (fiel - maior cruzado) medido: 0.608

SAIDAS = [(d, f) for d in DOCUMENTOS for f in FORMATOS]


def _fonte(documento: str) -> str:
    return (_EXEMPLOS / f"{documento}.md").read_text(encoding="utf-8")


def _conteudo(documento: str, formato: str):
    dados = json.loads((_FIXTURES / f"{documento}__{formato}.json").read_text(encoding="utf-8"))
    bruto = dados["conteudo_adaptado"]
    return _CLASSES[bruto["tipo"]].model_validate(bruto)


def _outros(documento: str) -> list[str]:
    return [d for d in DOCUMENTOS if d != documento]


def _ancoragem(documento: str, formato: str, fonte: str) -> float:
    # relevância fora de 0..1: se o fallback fosse usado, o resultado denunciaria.
    return calcular_ancoragem(_conteudo(documento, formato), _fonte(fonte), relevancia_media=-1)


def test_fixtures_completas():
    assert sorted(p.name for p in _FIXTURES.glob("*.json")) == sorted(
        f"{d}__{f}.json" for d, f in SAIDAS
    )


@pytest.mark.parametrize("documento,formato", SAIDAS)
def test_saida_real_fiel_a_propria_fonte(documento, formato):
    assert _ancoragem(documento, formato, documento) >= FIEL_MINIMO


@pytest.mark.parametrize("documento,formato", SAIDAS)
def test_saida_real_contra_fonte_de_outro_documento_fica_baixa(documento, formato):
    for outro in _outros(documento):
        assert 0.0 <= _ancoragem(documento, formato, outro) <= CRUZADO_MAXIMO


@pytest.mark.parametrize("documento,formato", SAIDAS)
def test_separacao_entre_fiel_e_cruzado(documento, formato):
    fiel = _ancoragem(documento, formato, documento)
    maior_cruzado = max(_ancoragem(documento, formato, o) for o in _outros(documento))
    assert fiel - maior_cruzado >= SEPARACAO_MINIMA


def test_medias_por_grupo():
    fieis = [_ancoragem(d, f, d) for d, f in SAIDAS]
    cruzados = [_ancoragem(d, f, o) for d, f in SAIDAS for o in _outros(d)]
    assert sum(fieis) / len(fieis) >= 0.80  # medido: 0.853
    assert sum(cruzados) / len(cruzados) <= 0.15  # medido: 0.102


@pytest.mark.parametrize("documento,formato", SAIDAS)
def test_controle_misto_mais_itens_estranhos_nota_menor(documento, formato):
    """Troca uma fração dos itens por itens do mesmo formato de outro documento."""
    proprios = itens_medidos(_conteudo(documento, formato))
    estranhos = itens_medidos(_conteudo(_outros(documento)[0], formato))
    fonte = _fonte(documento)
    notas = []
    for fracao in (0.0, 1 / 3, 2 / 3, 1.0):
        trocados = round(fracao * len(proprios))
        itens = proprios[: len(proprios) - trocados] + estranhos[:trocados]
        notas.append(media_das_notas(itens, fonte))
    assert notas == sorted(notas, reverse=True)
    assert len(set(notas)) == len(notas)  # cai a cada passo
    assert notas[0] - notas[1] >= 0.1  # trocar ~1/3 dos itens tira ao menos 0,1
    assert notas[-1] <= CRUZADO_MAXIMO
