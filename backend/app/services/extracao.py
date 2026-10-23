"""Utilitários de extração de texto a partir de diferentes formatos de arquivo."""

from __future__ import annotations

import io


def extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """Extrai texto de um PDF usando pypdf. Lança ValueError se sem texto."""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pypdf não instalado.") from exc

    reader = PdfReader(io.BytesIO(conteudo_bytes))
    partes = []
    for pagina in reader.pages:
        txt = pagina.extract_text() or ""
        partes.append(txt)
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
