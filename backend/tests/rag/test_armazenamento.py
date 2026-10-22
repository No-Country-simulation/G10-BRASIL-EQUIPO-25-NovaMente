import re

import pytest

from app.rag import armazenamento, embeddings

pytestmark = pytest.mark.usefixtures("embedding_falso", "chroma_temporario")

TRECHOS = [
    "O código HTTP 404 indica recurso não encontrado no servidor.",
    "A fotossíntese converte luz solar em energia química nas plantas.",
    "O método POST envia dados ao servidor no corpo da requisição.",
]


def indexar(doc_id="doc-1", trechos=TRECHOS):
    return armazenamento.salvar_trechos(
        doc_id, "Título", trechos, embeddings.vetorizar_trechos(trechos)
    )


def consultar(texto, doc_id="doc-1", k=3):
    return armazenamento.buscar(doc_id, embeddings.vetorizar_consulta(texto), k)


def test_trecho_mais_parecido_vem_primeiro():
    indexar()
    resultado = consultar("plantas e fotossíntese com luz")
    assert resultado[0].indice == 1
    assert resultado[0].documento_id == "doc-1"
    relevancias = [t.relevancia for t in resultado]
    assert relevancias == sorted(relevancias, reverse=True)
    assert all(0.0 <= r <= 1.0 for r in relevancias)


def test_texto_identico_tem_relevancia_maxima():
    indexar()
    assert consultar(TRECHOS[2])[0].relevancia == pytest.approx(1.0, abs=1e-4)


def test_k_limita_e_nao_passa_do_total():
    indexar()
    assert len(consultar("servidor", k=1)) == 1
    assert len(consultar("servidor", k=10)) == 3


def test_reindexar_substitui():
    indexar()
    indexar(trechos=["Conteúdo novo sobre bancos de dados relacionais."])
    resultado = consultar("servidor HTTP")
    assert len(resultado) == 1
    assert "bancos de dados" in resultado[0].texto


def test_documentos_ficam_separados():
    indexar("doc-a", TRECHOS[:1])
    indexar("doc-b", TRECHOS[1:2])
    assert consultar("fotossíntese", doc_id="doc-a")[0].texto == TRECHOS[0]


def test_documento_inexistente_falha():
    with pytest.raises(LookupError):
        consultar("qualquer", doc_id="nunca-indexado")


def test_remover_documento():
    indexar()
    assert armazenamento.remover_documento("doc-1") is True
    assert armazenamento.remover_documento("doc-1") is False


def test_trechos_e_vetores_desalinhados_falham():
    with pytest.raises(ValueError):
        armazenamento.salvar_trechos("doc-1", "T", ["a", "b"], [[1.0]])


@pytest.mark.parametrize(
    "doc_id", ["a", "relatório final.pdf", "../../etc", "x" * 600, "ç ã é 😀", "..a..b.."]
)
def test_nome_collection_valido(doc_id):
    nome = armazenamento.nome_collection(doc_id)
    assert 3 <= len(nome) <= 512
    assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]", nome)
    armazenamento.salvar_trechos(doc_id, "T", ["texto"], [[1.0, 0.0]])


def test_ids_parecidos_nao_colidem():
    assert armazenamento.nome_collection("a b") != armazenamento.nome_collection("a-b")


def test_id_vazio_falha():
    with pytest.raises(ValueError):
        armazenamento.nome_collection("  ")
