"""Router de adaptações — POST /adaptacoes e POST /adaptacoes/upload."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app.core.config import settings
from app.core.erros import NovaMenteError
from app.models import (
    AdaptacaoInput,
    AdaptacaoPacote,
    AdaptacaoResumo,
    FormatoExportacao,
    FormatoSaida,
    JobResposta,
    NichoSetor,
    NivelDetalhe,
    PaginaAdaptacoes,
    PerfilDestinatario,
)
from app.services import repositorio
from app.services.extracao import extrair_texto_markdown, extrair_texto_pdf
from app.workers.job_worker import criar_job

router = APIRouter(prefix="/adaptacoes", tags=["adaptacoes"])

# MIME types aceitos para upload
_MIMES_ACEITOS = {
    "application/pdf",
    "text/markdown",
    "text/x-markdown",
    "text/plain",
}
_EXTENSOES_ACEITAS = {".pdf", ".md", ".txt"}


# ── POST /adaptacoes ─────────────────────────────────────────────────────────


@router.post("", status_code=202)
def criar_por_texto(body: AdaptacaoInput) -> Response:
    """Cria um job de adaptação a partir de texto colado (JSON)."""
    job = criar_job(
        titulo=body.documento_titulo,
        texto=body.documento_conteudo,
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil=body.perfil_destinatario,
        formato=body.formato_saida,
        nicho=body.nicho_setor,
        nivel=body.nivel_detalhe,
    )
    return JSONResponse(
        content=job.model_dump(),
        status_code=202,
        headers={"Location": f"/api/v1/jobs/{job.job_id}"},
    )


# ── POST /adaptacoes/upload ──────────────────────────────────────────────────


@router.post("/upload", status_code=202)
async def criar_por_arquivo(
    arquivo: UploadFile = File(...),
    documento_titulo: str = Form(..., min_length=3, max_length=150),
    perfil_destinatario: PerfilDestinatario = Form(...),
    formato_saida: FormatoSaida = Form(...),
    nicho_setor: NichoSetor = Form(...),
    nivel_detalhe: NivelDetalhe = Form(...),
) -> Response:
    """Cria um job de adaptação a partir de upload de arquivo (multipart)."""
    import os

    # Validar extensão
    nome = arquivo.filename or ""
    ext = os.path.splitext(nome)[1].lower()
    if ext not in _EXTENSOES_ACEITAS:
        raise HTTPException(
            status_code=415,
            detail={
                "erro": {
                    "codigo": "ARQUIVO_INVALIDO",
                    "mensagem": f"Extensão '{ext}' não suportada. Use .pdf, .md ou .txt.",
                }
            },
        )

    # Validar MIME
    content_type = (arquivo.content_type or "").split(";")[0].strip()
    if content_type and content_type not in _MIMES_ACEITOS:
        raise HTTPException(
            status_code=415,
            detail={
                "erro": {
                    "codigo": "ARQUIVO_INVALIDO",
                    "mensagem": f"Content-Type '{content_type}' não suportado.",
                }
            },
        )

    # Ler conteúdo e validar tamanho
    conteudo_bytes = await arquivo.read()
    tamanho = len(conteudo_bytes)
    if tamanho > settings.arquivo_max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "erro": {
                    "codigo": "LIMITE_EXCEDIDO",
                    "mensagem": f"Arquivo excede o limite de 10 MiB ({tamanho} bytes recebidos).",
                }
            },
        )

    # Extrair texto
    try:
        if ext == ".pdf":
            texto = extrair_texto_pdf(conteudo_bytes)
        else:
            texto = extrair_texto_markdown(conteudo_bytes)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"erro": {"codigo": "DOCUMENTO_ILEGIVEL", "mensagem": str(exc)}},
        )

    # Validar tamanho do texto extraído
    if len(texto) < settings.texto_min_caracteres:
        raise HTTPException(
            status_code=400,
            detail={
                "erro": {
                    "codigo": "DOCUMENTO_ILEGIVEL",
                    "mensagem": "Texto extraído do arquivo é muito curto (mínimo 200 caracteres).",
                }
            },
        )
    if len(texto) > settings.texto_max_caracteres:
        raise HTTPException(
            status_code=413,
            detail={
                "erro": {
                    "codigo": "LIMITE_EXCEDIDO",
                    "mensagem": f"Texto extraído excede 50.000 caracteres ({len(texto)} caracteres).",
                }
            },
        )

    job = criar_job(
        titulo=documento_titulo,
        texto=texto,
        origem="upload",
        nome_arquivo=nome,
        tamanho_bytes=tamanho,
        perfil=perfil_destinatario,
        formato=formato_saida,
        nicho=nicho_setor,
        nivel=nivel_detalhe,
    )
    return JSONResponse(
        content=job.model_dump(),
        status_code=202,
        headers={"Location": f"/api/v1/jobs/{job.job_id}"},
    )


# ── GET /adaptacoes ──────────────────────────────────────────────────────────

_ORDENAR_VALIDOS = {"criado_em:desc", "criado_em:asc", "ancoragem:desc"}


@router.get("", response_model=PaginaAdaptacoes)
def listar_adaptacoes(
    pagina: int = 1,
    tamanho_pagina: int = 12,
    formato: FormatoSaida | None = None,
    perfil: PerfilDestinatario | None = None,
    q: str | None = None,
    ordenar: str = "criado_em:desc",
) -> PaginaAdaptacoes:
    """Histórico paginado e filtrável."""
    # Validações de parâmetros
    erros: dict[str, str] = {}
    if pagina < 1:
        erros["pagina"] = "Deve ser >= 1."
    if not (1 <= tamanho_pagina <= 50):
        erros["tamanho_pagina"] = "Deve estar entre 1 e 50."
    if ordenar not in _ORDENAR_VALIDOS:
        erros["ordenar"] = f"Valores aceitos: {', '.join(_ORDENAR_VALIDOS)}."
    if q and not (1 <= len(q) <= 100):
        erros["q"] = "Deve ter entre 1 e 100 caracteres."
    if erros:
        raise HTTPException(
            status_code=422,
            detail={"erro": {"codigo": "VALIDACAO", "mensagem": "Parâmetros inválidos.", "campos": erros}},
        )

    todos = repositorio.listar_pacotes()

    # Filtros
    if formato:
        todos = [p for p in todos if p.metadados.formato_gerado == formato]
    if perfil:
        todos = [p for p in todos if p.metadados.perfil_aplicado == perfil]
    if q:
        q_lower = q.lower()
        todos = [
            p for p in todos
            if q_lower in p.documento.titulo.lower()
            or any(q_lower in c.lower() for c in p.metadados.conceitos_chave)
        ]

    # Ordenação
    if ordenar == "criado_em:desc":
        todos.sort(key=lambda p: p.criado_em, reverse=True)
    elif ordenar == "criado_em:asc":
        todos.sort(key=lambda p: p.criado_em)
    elif ordenar == "ancoragem:desc":
        todos.sort(key=lambda p: p.avaliacao_qualidade.ancoragem_fonte_score, reverse=True)

    total = len(todos)
    total_paginas = max(1, (total + tamanho_pagina - 1) // tamanho_pagina) if total else 0
    inicio = (pagina - 1) * tamanho_pagina
    pagina_itens = todos[inicio: inicio + tamanho_pagina]

    resumos = [
        AdaptacaoResumo(
            adaptacao_id=p.adaptacao_id,
            criado_em=p.criado_em,
            documento=p.documento,
            perfil_aplicado=p.metadados.perfil_aplicado,
            formato_gerado=p.metadados.formato_gerado,
            nivel_detalhe_aplicado=p.metadados.nivel_detalhe_aplicado,
            nicho_setor_aplicado=p.metadados.nicho_setor_aplicado,
            tempo_estimado_estudo_minutos=p.metadados.tempo_estimado_estudo_minutos,
            ancoragem_fonte_score=p.avaliacao_qualidade.ancoragem_fonte_score,
            status_upload=p.armazenamento_oci.status_upload,
            conceitos_chave=p.metadados.conceitos_chave[:6],
        )
        for p in pagina_itens
    ]

    return PaginaAdaptacoes(
        itens=resumos,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total=total,
        total_paginas=total_paginas,
    )


# ── GET /adaptacoes/{id} ─────────────────────────────────────────────────────


@router.get("/{adaptacao_id}", response_model=AdaptacaoPacote)
def obter_adaptacao(adaptacao_id: str) -> AdaptacaoPacote:
    pacote = repositorio.obter_pacote(adaptacao_id)
    if pacote is None:
        raise HTTPException(
            status_code=404,
            detail={"erro": {"codigo": "ADAPTACAO_NAO_ENCONTRADA", "mensagem": "Adaptação não encontrada."}},
        )
    return pacote


# ── GET /adaptacoes/{id}/download ────────────────────────────────────────────


@router.get("/{adaptacao_id}/download")
def baixar_json(adaptacao_id: str) -> Response:
    """Serve o pacote como arquivo JSON para download."""
    pacote = repositorio.obter_pacote(adaptacao_id)
    if pacote is None:
        raise HTTPException(
            status_code=404,
            detail={"erro": {"codigo": "ADAPTACAO_NAO_ENCONTRADA", "mensagem": "Adaptação não encontrada."}},
        )
    nome_arquivo = pacote.armazenamento_oci.objeto_id
    return Response(
        content=pacote.model_dump_json(indent=2),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


# ── GET /adaptacoes/{id}/exportacao ─────────────────────────────────────────


@router.get("/{adaptacao_id}/exportacao")
def exportar(adaptacao_id: str, formato: str) -> Response:
    """Exporta o pacote em MD, PDF ou CSV-Anki."""
    if formato not in ("md", "pdf", "csv"):
        raise HTTPException(
            status_code=400,
            detail={"erro": {"codigo": "FORMATO_DESCONHECIDO", "mensagem": f"Formato '{formato}' desconhecido."}},
        )

    pacote = repositorio.obter_pacote(adaptacao_id)
    if pacote is None:
        raise HTTPException(
            status_code=404,
            detail={"erro": {"codigo": "ADAPTACAO_NAO_ENCONTRADA", "mensagem": "Adaptação não encontrada."}},
        )

    conteudo = pacote.conteudo_adaptado
    nome_base = pacote.armazenamento_oci.objeto_id.rsplit(".", 1)[0]

    if formato == "csv":
        if conteudo.tipo != "flashcards":
            raise HTTPException(
                status_code=409,
                detail={"erro": {"codigo": "FORMATO_INCOMPATIVEL", "mensagem": "CSV-Anki disponível apenas para Flashcards."}},
            )
        linhas = ["frente;verso;dica"]
        for item in conteudo.itens:
            dica = item.dica_didatica or ""
            linhas.append(
                f'"{item.frente.replace(chr(34), chr(34)*2)}";'
                f'"{item.verso.replace(chr(34), chr(34)*2)}";'
                f'"{dica.replace(chr(34), chr(34)*2)}"'
            )
        body = "\n".join(linhas).encode("utf-8")
        return Response(
            content=body,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nome_base}.csv"'},
        )

    if formato == "md":
        if conteudo.tipo == "markdown":
            md_texto = f"# {conteudo.titulo}\n\n{conteudo.introducao_contextualizada}\n\n{conteudo.itens}"
        elif conteudo.tipo == "flashcards":
            linhas = [f"# {conteudo.titulo}\n\n{conteudo.introducao_contextualizada}\n"]
            for i, item in enumerate(conteudo.itens, 1):
                linhas.append(f"## Card {i}\n**Frente:** {item.frente}\n**Verso:** {item.verso}")
                if item.dica_didatica:
                    linhas.append(f"*Dica:* {item.dica_didatica}")
            md_texto = "\n\n".join(linhas)
        else:  # quiz
            linhas = [f"# {conteudo.titulo}\n\n{conteudo.introducao_contextualizada}\n"]
            for i, item in enumerate(conteudo.itens, 1):
                opcoes = "\n".join(
                    f"{'✓' if j == item.resposta_correta else ' '} {op}"
                    for j, op in enumerate(item.opcoes)
                )
                linhas.append(f"## Questão {i}\n{item.pergunta}\n\n{opcoes}\n\n*{item.explicacao}*")
            md_texto = "\n\n".join(linhas)
        return Response(
            content=md_texto.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{nome_base}.md"'},
        )

    if formato == "pdf":
        try:
            from markdown_it import MarkdownIt  # type: ignore
            import weasyprint  # type: ignore
        except ImportError:
            raise HTTPException(
                status_code=501,
                detail={"erro": {"codigo": "INTERNO", "mensagem": "Dependências de PDF não instaladas."}},
            )
        # Gera o MD primeiro, depois converte para HTML → PDF
        md_resp = exportar(adaptacao_id, "md")
        md_texto = md_resp.body.decode("utf-8")
        md = MarkdownIt()
        html = f"<html><body>{md.render(md_texto)}</body></html>"
        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{nome_base}.pdf"'},
        )

    # Nunca chega aqui, mas para o type checker:
    raise HTTPException(status_code=400, detail={"erro": {"codigo": "FORMATO_DESCONHECIDO", "mensagem": ""}})
