import threading

import pytest

from app.rag import armazenamento, config, embeddings

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


# Antes cada documento tinha a própria collection e estes testes conferiam o
# nome gerado. Com a collection única, o id vai só nos metadados e no id da
# linha: os mesmos ids estranhos precisam gravar, ser achados e ficar separados.
@pytest.mark.parametrize(
    "doc_id", ["a", "relatório final.pdf", "../../etc", "x" * 600, "ç ã é 😀", "..a..b..", "a:00001"]
)
def test_ids_estranhos_gravam_e_sao_encontrados(doc_id):
    armazenamento.salvar_trechos(doc_id, "T", ["texto"], [[1.0, 0.0]])
    assert armazenamento.existe_documento(doc_id)
    assert armazenamento.buscar(doc_id, [1.0, 0.0])[0].documento_id == doc_id
    assert armazenamento.documentos_indexados() == {doc_id: 1}


def test_ids_parecidos_nao_colidem():
    armazenamento.salvar_trechos("a b", "T", ["um"], [[1.0, 0.0]])
    armazenamento.salvar_trechos("a-b", "T", ["dois"], [[0.0, 1.0]])
    assert [t.texto for t in armazenamento.buscar("a b", [0.0, 1.0], k=5)] == ["um"]
    assert [t.texto for t in armazenamento.buscar("a-b", [1.0, 0.0], k=5)] == ["dois"]


@pytest.mark.parametrize("funcao", ["validar_documento_id", "existe_documento", "remover_documento"])
def test_id_vazio_falha(funcao):
    with pytest.raises(ValueError):
        getattr(armazenamento, funcao)("  ")


# ── Collection única ──────────────────────────────────────────────────────────


def test_todos_os_documentos_ficam_numa_collection_so():
    indexar("doc-a", TRECHOS[:2])
    indexar("doc-b", TRECHOS[2:])
    cliente = armazenamento.obter_cliente()
    assert [c.name for c in cliente.list_collections()] == [config.NOME_COLLECTION]
    assert armazenamento.documentos_indexados() == {"doc-a": 2, "doc-b": 1}


def test_busca_nao_mistura_documentos_mesmo_com_k_grande():
    indexar("doc-a", TRECHOS[:1])
    indexar("doc-b", TRECHOS[1:])
    resultado = consultar(TRECHOS[1], doc_id="doc-a", k=10)
    assert [t.texto for t in resultado] == [TRECHOS[0]]
    assert {t.documento_id for t in consultar("servidor", doc_id="doc-b", k=10)} == {"doc-b"}


def test_remover_um_documento_mantem_o_outro():
    indexar("doc-a", TRECHOS[:1])
    indexar("doc-b", TRECHOS[1:])
    assert armazenamento.remover_documento("doc-a") is True
    assert not armazenamento.existe_documento("doc-a")
    assert armazenamento.documentos_indexados() == {"doc-b": 2}
    assert len(consultar("servidor", doc_id="doc-b", k=10)) == 2


def test_reindexar_substitui_so_as_linhas_do_documento():
    indexar("doc-a", TRECHOS)
    indexar("doc-b", TRECHOS[:2])
    indexar("doc-a", ["Conteúdo novo sobre bancos de dados relacionais."])
    assert armazenamento.documentos_indexados() == {"doc-a": 1, "doc-b": 2}
    assert "bancos de dados" in consultar("servidor", doc_id="doc-a")[0].texto


def test_linhas_guardam_documento_indice_e_titulo():
    armazenamento.salvar_trechos("doc-m", "Manual", ["um", "dois"], [[1.0, 0.0], [0.0, 1.0]])
    colecao = armazenamento.obter_cliente().get_collection(config.NOME_COLLECTION)
    linhas = colecao.get(include=["metadatas"])
    assert sorted(linhas["ids"]) == ["doc-m:00000", "doc-m:00001"]
    assert {(m["documento_id"], m["indice"], m["titulo"]) for m in linhas["metadatas"]} == {
        ("doc-m", 0, "Manual"), ("doc-m", 1, "Manual"),
    }


def test_documentos_indexados_le_em_paginas(monkeypatch):
    monkeypatch.setattr(armazenamento, "_LOTE_LEITURA", 2)
    for i in range(3):
        armazenamento.salvar_trechos(f"doc-{i}", "T", ["a", "b", "c"], [[1.0, 0.0]] * 3)
    assert armazenamento.documentos_indexados() == {"doc-0": 3, "doc-1": 3, "doc-2": 3}


def test_threads_em_documentos_diferentes_nao_se_misturam():
    """4 threads indexam, consultam e removem documentos diferentes ao mesmo tempo."""
    erros, misturas = [], []

    def trabalhar(t: int) -> None:
        try:
            for k in range(10):
                doc = f"doc-{t}-{k}"
                textos = [f"{doc} trecho {j}" for j in range(4)]
                vetores = [[float(t + 1), float(k + 1), float(j + 1)] for j in range(4)]
                armazenamento.salvar_trechos(doc, "T", textos, vetores)
                achados = armazenamento.buscar(doc, [1.0, 1.0, 1.0], k=10)
                if len(achados) != 4 or any(not a.texto.startswith(f"{doc} ") for a in achados):
                    misturas.append(doc)
                armazenamento.remover_documento(doc)
        except Exception as exc:  # pragma: no cover - aparece na asserção
            erros.append(repr(exc))

    threads = [threading.Thread(target=trabalhar, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert erros == []
    assert misturas == []
    assert armazenamento.documentos_indexados() == {}
