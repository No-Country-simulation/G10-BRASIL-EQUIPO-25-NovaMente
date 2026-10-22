import pytest

from app.rag import config, embeddings


def test_trechos_usam_task_type_documento(embedding_falso):
    vetores = embeddings.vetorizar_trechos(["um", "dois"])
    assert len(vetores) == 2
    assert embedding_falso.chamadas == [("documentos", 2, config.TASK_TYPE_DOCUMENTO)]


def test_consulta_usa_task_type_consulta(embedding_falso):
    embeddings.vetorizar_consulta("pergunta")
    assert embedding_falso.chamadas == [("consulta", 1, config.TASK_TYPE_CONSULTA)]


def test_trechos_em_lotes(embedding_falso, monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_LOTE", 3)
    vetores = embeddings.vetorizar_trechos([f"t{i}" for i in range(7)])
    assert len(vetores) == 7
    assert [c[1] for c in embedding_falso.chamadas] == [3, 3, 1]


def test_retenta_em_limite_de_taxa(monkeypatch):
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: None)
    tentativas = []

    def instavel():
        tentativas.append(1)
        if len(tentativas) < 3:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return "ok"

    assert embeddings._com_retentativa(instavel) == "ok"
    assert len(tentativas) == 3


def test_desiste_apos_tentativas(monkeypatch):
    monkeypatch.setattr(embeddings.time, "sleep", lambda _s: None)

    def sempre_429():
        raise RuntimeError("429")

    with pytest.raises(RuntimeError):
        embeddings._com_retentativa(sempre_429)


def test_outros_erros_nao_retentam():
    tentativas = []

    def quebra():
        tentativas.append(1)
        raise ValueError("chave inválida")

    with pytest.raises(ValueError):
        embeddings._com_retentativa(quebra)
    assert len(tentativas) == 1
