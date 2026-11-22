"""Utilitários de extração de texto a partir de diferentes formatos de arquivo."""

from __future__ import annotations

import io


def extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """Extrai texto de um PDF usando pypdf.

    Lança ValueError se o arquivo não puder ser lido como PDF (vazio,
    corrompido, truncado ou protegido por senha) ou se não tiver texto.
    """
    try:
        from pypdf import PdfReader  # type: ignore
        from pypdf.errors import FileNotDecryptedError, PyPdfError  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pypdf não instalado.") from exc

    partes = []
    try:
        reader = PdfReader(io.BytesIO(conteudo_bytes))
        for pagina in reader.pages:
            txt = pagina.extract_text() or ""
            partes.append(txt)
    except FileNotDecryptedError as exc:
        raise ValueError("O PDF está protegido por senha e não pode ser lido.") from exc
    except PyPdfError as exc:
        raise ValueError("O arquivo não é um PDF válido ou está corrompido.") from exc
    texto = "\n".join(partes).strip()
    if not texto:
        raise ValueError("O PDF não contém camada de texto extraível.")
    return texto


def extrair_texto_markdown(conteudo_bytes: bytes) -> str:
    """Decodifica bytes de arquivo Markdown/texto simples."""
    try:
        return conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return conteudo_bytes.decode("latin-1")
