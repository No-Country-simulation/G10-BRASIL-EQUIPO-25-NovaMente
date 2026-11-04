"""Testes de upload de PDF inválido — devem virar 400 DOCUMENTO_ILEGIVEL, não 500."""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from app.main import app
from app.services.extracao import extrair_texto_pdf

client = TestClient(app)

DADOS = {
    "documento_titulo": "Manual de Teste",
    "perfil_destinatario": "Iniciante",
    "formato_saida": "Flashcards",
    "nicho_setor": "Geral",
    "nivel_detalhe": "Didatico",
}

TEXTO_PDF = "Texto de teste do NovaMente sobre APIs REST"


def _pdf_com_texto(texto: str) -> bytes:
    """Monta em memória um PDF mínimo de uma página com o texto informado."""
    conteudo = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(conteudo) + conteudo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    saida = io.BytesIO()
    saida.write(b"%PDF-1.4\n")
    posicoes = []
    for numero, objeto in enumerate(objetos, 1):
        posicoes.append(saida.tell())
        saida.write(b"%d 0 obj\n" % numero + objeto + b"\nendobj\n")
    inicio_xref = saida.tell()
    saida.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1))
    for posicao in posicoes:
        saida.write(b"%010d 00000 n \n" % posicao)
    saida.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objetos) + 1, inicio_xref)
    )
    return saida.getvalue()


def _pdf_com_senha() -> bytes:
    escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(_pdf_com_texto(TEXTO_PDF))))
    escritor.encrypt("segredo")
    saida = io.BytesIO()
    escritor.write(saida)
    return saida.getvalue()


def _enviar(conteudo: bytes):
    arquivos = {"arquivo": ("documento.pdf", conteudo, "application/pdf")}
    return client.post("/api/v1/adaptacoes/upload", files=arquivos, data=DADOS)


PDFS_INVALIDOS = {
    "vazio": lambda: b"",
    "bytes_aleatorios": lambda: os.urandom(2048),
    "truncado": lambda: _pdf_com_texto(TEXTO_PDF)[:200],
    "protegido_por_senha": _pdf_com_senha,
}


@pytest.mark.parametrize("gerar", PDFS_INVALIDOS.values(), ids=PDFS_INVALIDOS.keys())
def test_upload_pdf_invalido_retorna_400(gerar):
    resp = _enviar(gerar())
    assert resp.status_code == 400
    erro = resp.json()["erro"]
    assert erro["codigo"] == "DOCUMENTO_ILEGIVEL"
    assert erro["mensagem"]


@pytest.mark.parametrize("gerar", PDFS_INVALIDOS.values(), ids=PDFS_INVALIDOS.keys())
def test_extracao_pdf_invalido_lanca_value_error(gerar):
    with pytest.raises(ValueError):
        extrair_texto_pdf(gerar())


def test_extracao_pdf_com_senha_explica_o_motivo():
    with pytest.raises(ValueError, match="senha"):
        extrair_texto_pdf(_pdf_com_senha())


def test_extracao_pdf_valido_devolve_texto():
    assert extrair_texto_pdf(_pdf_com_texto(TEXTO_PDF)) == TEXTO_PDF


def test_upload_pdf_valido_passa_da_extracao():
    # Texto curto: a extração funciona e a recusa vem da validação de tamanho.
    resp = _enviar(_pdf_com_texto(TEXTO_PDF))
    assert resp.status_code == 400
    assert "muito curto" in resp.json()["erro"]["mensagem"]
