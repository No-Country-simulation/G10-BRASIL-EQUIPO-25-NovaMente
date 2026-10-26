import pytest
from pydantic import ValidationError

from app.rag import config
from app.rag.chunking import dividir_texto, validar_texto
from app.rag.modelos import ResultadoIndexacao, Trecho

PARAGRAFO = (
    "O protocolo HTTP define métodos como GET e POST. "
    "Cada requisição recebe um código de status na resposta. "
    "Códigos 2xx indicam sucesso e 4xx indicam erro do cliente. "
)


def texto_longo(paragrafos: int = 30) -> str:
    return "\n\n".join(f"Seção {i}. {PARAGRAFO}" for i in range(paragrafos))


def test_texto_curto_falha():
    with pytest.raises(ValueError, match="curto"):
        validar_texto("a" * (config.TEXTO_MIN_CARACTERES - 1))


def test_texto_longo_demais_falha():
    with pytest.raises(ValueError, match="longo"):
        validar_texto("a" * (config.TEXTO_MAX_CARACTERES + 1))


def test_espacos_nas_pontas_nao_contam():
    with pytest.raises(ValueError):
        validar_texto("   " + "a" * 150 + "   " * 100)


def test_texto_nao_string_falha():
    with pytest.raises(ValueError):
        validar_texto(None)  # type: ignore[arg-type]


def test_trechos_respeitam_tamanho():
    trechos = dividir_texto(texto_longo())
    assert len(trechos) > 1
    assert all(len(t) <= config.CHUNK_TAMANHO for t in trechos)


def test_trechos_preservam_ordem_e_conteudo():
    texto = texto_longo()
    trechos = dividir_texto(texto)
    assert trechos[0].startswith("Seção 0.")
    assert "Seção 29." in trechos[-1]
    for i in range(30):
        assert any(f"Seção {i}." in t for t in trechos)


def test_overlap_entre_vizinhos():
    # Texto sem parágrafos força quebra por frase e evidencia o overlap.
    texto = " ".join(f"Frase número {i} sobre redes." for i in range(200))
    trechos = dividir_texto(texto, tamanho=300, overlap=80)
    assert all(len(t) <= 300 for t in trechos)
    compartilhados = sum(
        1 for a, b in zip(trechos, trechos[1:]) if a[-40:].split()[-1] in b
    )
    assert compartilhados >= len(trechos) - 2


def test_overlap_maior_que_tamanho_falha():
    with pytest.raises(ValueError, match="overlap"):
        dividir_texto(texto_longo(), tamanho=100, overlap=100)


def test_texto_pequeno_vira_um_trecho():
    texto = PARAGRAFO * 2
    assert dividir_texto(texto) == [texto.strip()]


def test_modelos_validam_campos():
    t = Trecho(texto="x", indice=0, relevancia=0.9, documento_id="d1")
    assert t.relevancia == 0.9
    with pytest.raises(ValidationError):
        Trecho(texto="x", indice=0, relevancia=1.5, documento_id="d1")
    with pytest.raises(ValidationError):
        ResultadoIndexacao(documento_id="d1", total_trechos=-1, caracteres=10)
