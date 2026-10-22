"""Divisão do texto em trechos (chunks) para indexação.

O módulo recebe texto já extraído. A extração de PDF/MD fica com quem
integra o endpoint (etapa "extraindo").
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag import config


def validar_texto(texto: str) -> str:
    """Confere o tamanho do texto e devolve a versão sem espaços nas pontas.

    Levanta ValueError com mensagem em português se o texto for curto ou
    longo demais.
    """
    if not isinstance(texto, str):
        raise ValueError("O texto do documento precisa ser uma string.")
    limpo = texto.strip()
    total = len(limpo)
    if total < config.TEXTO_MIN_CARACTERES:
        raise ValueError(
            f"Texto muito curto: {total} caracteres "
            f"(mínimo {config.TEXTO_MIN_CARACTERES})."
        )
    if total > config.TEXTO_MAX_CARACTERES:
        raise ValueError(
            f"Texto muito longo: {total} caracteres "
            f"(máximo {config.TEXTO_MAX_CARACTERES})."
        )
    return limpo


def dividir_texto(
    texto: str,
    tamanho: int = config.CHUNK_TAMANHO,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    """Valida o texto e divide em trechos de até `tamanho` caracteres.

    Trechos vizinhos compartilham até `overlap` caracteres para não perder
    contexto na fronteira. A ordem da lista é a ordem no documento.
    """
    if overlap >= tamanho:
        raise ValueError("O overlap precisa ser menor que o tamanho do trecho.")
    limpo = validar_texto(texto)
    divisor = RecursiveCharacterTextSplitter(
        chunk_size=tamanho,
        chunk_overlap=overlap,
        separators=config.SEPARADORES,
        keep_separator="end",
        strip_whitespace=True,
    )
    return [t for t in divisor.split_text(limpo) if t]
