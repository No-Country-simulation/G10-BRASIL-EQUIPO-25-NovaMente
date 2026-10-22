import pytest

from app.rag import ResultadoIndexacao, indexar_documento, recuperar

pytestmark = pytest.mark.usefixtures("chroma_temporario")

SECOES = {
    "http": "O protocolo HTTP usa métodos como GET e POST. O código 404 indica "
    "recurso não encontrado e o código 500 indica erro interno do servidor.",
    "sql": "Em bancos de dados relacionais, a linguagem SQL usa SELECT para "
    "consultar tabelas e JOIN para combinar linhas de tabelas diferentes.",
    "git": "No Git, o comando commit registra alterações e o branch permite "
    "desenvolver funcionalidades separadas antes do merge.",
}


def documento(repeticoes: int = 8) -> str:
    # Cada seção repetida vira parágrafos suficientes para gerar vários trechos.
    return "\n\n".join(texto for texto in SECOES.values() for _ in range(repeticoes))


def test_indexar_devolve_resumo(embedding_falso):
    texto = documento()
    resultado = indexar_documento("apostila-1", "Apostila", texto)
    assert isinstance(resultado, ResultadoIndexacao)
    assert resultado.documento_id == "apostila-1"
    assert resultado.total_trechos > 1
    assert resultado.caracteres == len(texto.strip())


def test_recuperar_traz_trecho_do_assunto(embedding_falso):
    indexar_documento("apostila-1", "Apostila", documento())
    trechos = recuperar("apostila-1", "consultar tabelas com SELECT e JOIN em SQL", k=2)
    assert len(trechos) == 2
    assert "SQL" in trechos[0].texto
    assert trechos[0].relevancia >= trechos[1].relevancia
    assert all(t.documento_id == "apostila-1" for t in trechos)


def test_on_etapa_na_ordem(embedding_falso):
    etapas = []
    indexar_documento("apostila-1", "Apostila", documento(), on_etapa=etapas.append)
    assert etapas == ["chunking", "embeddings"]


def test_texto_invalido_nao_avisa_etapa_nem_chama_api(embedding_falso):
    etapas = []
    with pytest.raises(ValueError, match="curto"):
        indexar_documento("x", "T", "curto demais", on_etapa=etapas.append)
    with pytest.raises(ValueError, match="longo"):
        indexar_documento("x", "T", "a" * 50_001, on_etapa=etapas.append)
    assert etapas == []
    assert embedding_falso.chamadas == []


def test_id_vazio_falha(embedding_falso):
    with pytest.raises(ValueError):
        indexar_documento("", "T", documento())


def test_reindexar_substitui(embedding_falso):
    indexar_documento("apostila-1", "Apostila", documento())
    so_git = "\n\n".join([SECOES["git"]] * 4)
    resultado = indexar_documento("apostila-1", "Apostila v2", so_git)
    trechos = recuperar("apostila-1", "protocolo HTTP código 404", k=10)
    assert len(trechos) == resultado.total_trechos
    assert all("HTTP" not in t.texto for t in trechos)


def test_documentos_nao_se_misturam(embedding_falso):
    indexar_documento("doc-http", "HTTP", "\n\n".join([SECOES["http"]] * 4))
    indexar_documento("doc-sql", "SQL", "\n\n".join([SECOES["sql"]] * 4))
    trechos = recuperar("doc-http", "SQL SELECT JOIN tabelas", k=4)
    assert all("HTTP" in t.texto for t in trechos)


def test_documento_inexistente_nao_chama_api(embedding_falso):
    with pytest.raises(LookupError):
        recuperar("nunca-indexado", "pergunta")
    assert embedding_falso.chamadas == []


@pytest.mark.parametrize("consulta,k", [("", 4), ("   ", 4), ("pergunta", 0)])
def test_parametros_invalidos_de_recuperar(embedding_falso, consulta, k):
    indexar_documento("apostila-1", "Apostila", documento())
    with pytest.raises(ValueError):
        recuperar("apostila-1", consulta, k=k)


def test_id_com_caracteres_estranhos(embedding_falso):
    doc_id = "Relatório Final (v2).pdf"
    indexar_documento(doc_id, "Relatório", documento())
    assert recuperar(doc_id, "commit e branch no Git", k=1)[0].documento_id == doc_id
