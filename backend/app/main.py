"""Ponto de entrada principal da aplicação FastAPI — NovaMente API."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.routers import adaptacoes, health, jobs, oci
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_nome,
    version=settings.app_versao,
    docs_url="/docs",
    redoc_url="/redoc",
    description=(
        "API do NovaMente — Sistema Inteligente de Adaptação e Geração "
        "de Conteúdo Educacional via RAG + Google Gemini."
    ),
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Em produção, restrinja allow_origins ao domínio do frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rotas ─────────────────────────────────────────────────────────────────────
_V1 = "/api/v1"
app.include_router(adaptacoes.router, prefix=_V1)
app.include_router(jobs.router, prefix=_V1)
app.include_router(oci.router, prefix=_V1)
app.include_router(health.router, prefix=_V1)


# ── Handlers de erro globais ──────────────────────────────────────────────────


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Normaliza HTTPException para o envelope ApiProblema da spec."""
    detail = exc.detail
    # Se o detail já é um dict com a chave 'erro', usa diretamente
    if isinstance(detail, dict) and "erro" in detail:
        content = detail
    else:
        content = {
            "erro": {
                "codigo": "INTERNO",
                "mensagem": str(detail),
            }
        }
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Transforma erros de validação do FastAPI no formato ApiProblema."""
    campos: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p not in ("body", "query"))
        campos[loc] = err["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "erro": {
                "codigo": "VALIDACAO",
                "mensagem": "Dados de entrada inválidos.",
                "campos": campos,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    campos: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        campos[loc] = err["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "erro": {
                "codigo": "VALIDACAO",
                "mensagem": "Dados de entrada inválidos.",
                "campos": campos,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = str(uuid.uuid4())
    logger.exception("Erro interno [%s]: %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={
            "erro": {
                "codigo": "INTERNO",
                "mensagem": "Erro interno do servidor.",
                "request_id": request_id,
            }
        },
    )

