"""Fontes do chat: trechos do documento e do pacote, seleção e cache."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.models import ConteudoMarkdown, ConteudoQuiz, QuizItem
from app.rag import chunking
from app.services import contexto_chat, repositorio
from app.services.constantes_chat import MaterialNaoEncontrado
from app.services.contexto_chat import (
    blocos_do_pacote,
    carregar_fontes,
    invalidar_material,
    limpar_cache,
    montar_consulta,
    montar_fontes,
    selecionar_trechos,
    tamanho_cache,
    trechos_do_pacote,
)

PARAGRAFO = (
    "Uma VCN é a rede virtual privada da nuvem. Ela é dividida em subnets, e cada "
    "subnet recebe um bloco de endereços. As tabelas de roteamento definem para onde "
    "vai o tráfego que sai de cada subnet, e os gateways ligam a VCN à internet. "
)
TEXTO = "\n\n".join(f"Seção {i}. {PARAGRAFO}" for i in range(12))


def _quiz(pacote):
    return pacote.model_copy(update={"conteudo_adaptado": ConteudoQuiz(
        titulo="Quiz de redes",
        introducao_contextualizada="Teste seus conhecimentos.",
        itens=[QuizItem(pergunta="O que é uma subnet?", opcoes=["Uma parte da VCN", "Um disco"],
                        resposta_correta=0, explicacao="A subnet subdivide a VCN.")],
    )})


def _markdown(pacote):
    return pacote.model_copy(update={"conteudo_adaptado": ConteudoMarkdown(
        titulo="Tutorial de VCN",
        introducao_contextualizada="Passo a passo.",
        itens="## Passo 1\nCrie a VCN no console.\n## Passo 2\nAdicione uma subnet pública.",
    )})


@pytest.fixture(autouse=True)
def _cache_limpo():
    limpar_cache()
    yield
    limpar_cache()


# ── Trechos ───────────────────────────────────────────────────────────────────


def test_documento_usa_o_splitter_do_rag_e_ids_estaveis(pacote_exemplo):
    fontes = montar_fontes("M1", pacote_exemplo, TEXTO)
    documento = [t for t in fontes.trechos if t.origem == "documento"]
    assert [t.texto for t in documento] == chunking.dividir_texto(TEXTO)
    assert [t.id for t in documento] == [f"F{i}" for i in range(1, len(documento) + 1)]
    pacote = [t for t in fontes.trechos if t.origem == "pacote"]
    assert [t.id for t in pacote] == [f"P{i}" for i in range(1, len(pacote) + 1)]
    assert fontes.base == "documento_e_pacote"
    assert [t.id for t in montar_fontes("M1", pacote_exemplo, TEXTO).trechos] == [
        t.id for t in fontes.trechos
    ]


def test_flashcards_viram_texto(pacote_exemplo):
    blocos = blocos_do_pacote(pacote_exemplo)
    assert blocos[0].startswith("Fundamentos de VCN")
    assert any("Frente: O que é uma VCN?" in b and "Dica: Pense em um condomínio" in b for b in blocos)
    assert blocos[-1] == "Conceitos-chave: VCN, Subnet, Roteamento"


def test_quiz_vira_texto_com_resposta_e_explicacao(pacote_exemplo):
    bloco = "\n".join(blocos_do_pacote(_quiz(pacote_exemplo)))
    assert "Pergunta 1: O que é uma subnet?" in bloco
    assert "a) Uma parte da VCN; b) Um disco" in bloco
    assert "Resposta correta: Uma parte da VCN" in bloco
    assert "Explicação: A subnet subdivide a VCN." in bloco


def test_markdown_vira_uma_secao_por_titulo(pacote_exemplo):
    blocos = blocos_do_pacote(_markdown(pacote_exemplo))
    assert "## Passo 1\nCrie a VCN no console." in blocos
    assert "## Passo 2\nAdicione uma subnet pública." in blocos


def test_formato_desconhecido_nao_estoura():
    class Outro(BaseModel):
        tipo: str = "mapa_mental"
        titulo: str = "Mapa"
        nos: list[dict] = [{"rotulo": "VCN", "filhos": ["subnet", "gateway"]}]

    pacote = SimpleNamespace(conteudo_adaptado=Outro(), metadados=None)
    blocos = blocos_do_pacote(pacote)
    assert blocos[0] == "Mapa"
    assert {"VCN", "subnet", "gateway"} <= set(blocos)
    assert "mapa_mental" not in blocos
    assert trechos_do_pacote(SimpleNamespace(conteudo_adaptado=object(), metadados=None)) == []


def test_trechos_do_pacote_agrupam_ate_o_tamanho_do_rag(pacote_exemplo):
    from app.rag import config

    itens = pacote_exemplo.conteudo_adaptado.itens * 10
    grande = pacote_exemplo.model_copy(update={"conteudo_adaptado": pacote_exemplo.conteudo_adaptado.model_copy(update={"itens": itens})})
    trechos = trechos_do_pacote(grande)
    assert len(trechos) > 1
    assert all(len(t) <= config.CHUNK_TAMANHO for t in trechos)


def test_material_sem_fonte_usa_so_o_pacote(pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo)  # sem texto-fonte
    fontes = carregar_fontes(pacote_exemplo.adaptacao_id)
    assert fontes.base == "pacote"
    assert fontes.trechos and all(t.origem == "pacote" for t in fontes.trechos)


def test_material_inexistente():
    with pytest.raises(MaterialNaoEncontrado):
        carregar_fontes("NAO_EXISTE")


# ── Seleção ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("orcamento", [300, 1000, 2500, 24_000])
def test_respeita_o_orcamento(pacote_exemplo, orcamento):
    fontes = montar_fontes("M1", pacote_exemplo, TEXTO)
    escolhidos = selecionar_trechos(fontes, "subnet roteamento VCN gateways", orcamento=orcamento)
    assert escolhidos
    assert sum(len(t.texto) for t in escolhidos) <= orcamento
    cortados = [t for t in escolhidos if t.cortado]
    assert len(cortados) <= 1
    assert all(not t.cortado for t in escolhidos[:-1])


def test_inclui_trecho_do_pacote_quando_algum_pontua(pacote_exemplo):
    fontes = montar_fontes("M1", pacote_exemplo, TEXTO)
    # Os trechos do documento ganham do pacote nesta consulta; o orçamento só cabe dois.
    consulta = "subnet tabelas de roteamento gateways"
    ranqueados = [trecho[0] for trecho, _p in fontes.indice.buscar(consulta)]
    assert ranqueados[0].startswith("F") and ranqueados[1].startswith("F")  # o pacote viria depois
    assert any(i.startswith("P") for i in ranqueados)
    escolhidos = selecionar_trechos(fontes, consulta, orcamento=1200)
    assert any(t.origem == "pacote" for t in escolhidos)
    assert sum(len(t.texto) for t in escolhidos) <= 1200


def test_pergunta_generica_cai_nos_primeiros_trechos_do_pacote(pacote_exemplo):
    fontes = montar_fontes("M1", pacote_exemplo, TEXTO)
    escolhidos = selecionar_trechos(fontes, "resuma tudo", orcamento=24_000)
    pacote = [t for t in fontes.trechos if t.origem == "pacote"]
    assert [t.id for t in escolhidos] == [t.id for t in pacote]


def test_seguimento_curto_usa_a_pergunta_anterior():
    historico = [("user", "Como funcionam as tabelas de roteamento?"), ("assistant", "Assim [F1].")]
    assert montar_consulta("e o gateway?", historico) == (
        "Como funcionam as tabelas de roteamento? e o gateway?"
    )
    assert montar_consulta("Como criar uma subnet pública na VCN?", historico) == (
        "Como criar uma subnet pública na VCN?"
    )
    assert montar_consulta("e o gateway?", []) == "e o gateway?"


# ── Cache ─────────────────────────────────────────────────────────────────────


def test_cache_reaproveita_e_invalida(pacote_exemplo, monkeypatch):
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO)
    mid = pacote_exemplo.adaptacao_id
    montagens = []
    original = contexto_chat.montar_fontes
    monkeypatch.setattr(contexto_chat, "montar_fontes", lambda *a: montagens.append(1) or original(*a))

    primeira = carregar_fontes(mid)
    assert carregar_fontes(mid) is primeira
    assert len(montagens) == 1

    invalidar_material(mid)
    assert carregar_fontes(mid) is not primeira
    assert len(montagens) == 2

    # A fonte mudou (outro tamanho): reindexa e descarta a versão antiga.
    repositorio.salvar_pacote(pacote_exemplo, texto=TEXTO + "\n\nSeção extra sobre NAT gateway.")
    terceira = carregar_fontes(mid)
    assert len(montagens) == 3
    assert any("NAT gateway" in t.texto for t in terceira.trechos)
    assert tamanho_cache() == 1


def test_cache_nao_passa_do_limite(pacote_exemplo, monkeypatch):
    monkeypatch.setattr(contexto_chat, "TAMANHO_CACHE", 3)
    ids = []
    for i in range(5):
        pacote = pacote_exemplo.model_copy(update={"adaptacao_id": f"MAT{i}"})
        repositorio.salvar_pacote(pacote)
        ids.append(pacote.adaptacao_id)
        carregar_fontes(pacote.adaptacao_id)
    assert tamanho_cache() == 3
    limpar_cache()
    assert tamanho_cache() == 0


def test_cache_seguro_com_threads(pacote_exemplo):
    for i in range(4):
        repositorio.salvar_pacote(pacote_exemplo.model_copy(update={"adaptacao_id": f"THR{i}"}), texto=TEXTO)
    erros = []

    def trabalhar(t):
        try:
            for k in range(20):
                mid = f"THR{(t + k) % 4}"
                fontes = carregar_fontes(mid)
                assert fontes.material_id == mid
                if k % 7 == 0:
                    invalidar_material(mid)
        except Exception as exc:  # pragma: no cover - aparece na asserção
            erros.append(repr(exc))

    threads = [threading.Thread(target=trabalhar, args=(t,)) for t in range(6)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert erros == []
    assert tamanho_cache() <= contexto_chat.TAMANHO_CACHE
