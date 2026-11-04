"""Configurações da aplicação via variáveis de ambiente."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Busca .env em backend/.env ou na pasta atual
_BASE_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BASE_DIR / ".env" if (_BASE_DIR / ".env").exists() else ".env"


class Settings(BaseSettings):
    """Configurações carregadas do .env ou do ambiente."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ── API ──────────────────────────────────────────────────────────────────
    app_nome: str = "NovaMente API"
    app_versao: str = "0.1.0"
    debug: bool = False

    # ── Google Gemini ────────────────────────────────────────────────────────
    google_api_key: str = ""
    modelo_llm: str = "gemini-3.5-flash-lite"

    # ── RAG / Chroma ─────────────────────────────────────────────────────────
    chroma_dir: str = "/data/chroma"

    # ── OCI Object Storage ───────────────────────────────────────────────────
    oci_config_file: str = "~/.oci/config"
    oci_profile: str = "DEFAULT"
    oci_namespace: str = ""
    oci_bucket: str = "novamente-conteudos-educativos"
    oci_regiao: str = ""

    # ── Jobs em memória ──────────────────────────────────────────────────────
    job_ttl_segundos: int = 1800  # 30 minutos
    job_timeout_segundos: int = 300  # 5 minutos (igual ao frontend)

    # ── Limites de entrada ───────────────────────────────────────────────────
    texto_min_caracteres: int = 200
    texto_max_caracteres: int = 50_000
    arquivo_max_bytes: int = 10 * 1024 * 1024  # 10 MiB


settings = Settings()

# Sincroniza com os.environ para módulos do LangChain e RAG
if settings.google_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
if settings.chroma_dir:
    os.environ["CHROMA_DIR"] = settings.chroma_dir
