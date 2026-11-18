"""Configurações da aplicação via variáveis de ambiente."""

import os
from pathlib import Path
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Busca .env em backend/.env ou na pasta atual
_BASE_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BASE_DIR / ".env" if (_BASE_DIR / ".env").exists() else ".env"

# Valores de NVIDIA_NIM_RACIOCINIO; vazio deixa o padrão do modelo.
RACIOCINIO_VALORES = ("", "ligado", "desligado")


class Settings(BaseSettings):
    """Configurações carregadas do .env ou do ambiente."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # ── API ──────────────────────────────────────────────────────────────────
    app_nome: str = "NovaMente API"
    app_versao: str = "0.1.0"
    debug: bool = False

    # ── Google Gemini ────────────────────────────────────────────────────────
    google_api_key: str = ""
    llm_provider: str = "gemini"  # provedor de LLM registrado em app/llm/fabrica.py
    modelo_llm: str = "gemini-3.5-flash-lite"

    # ── NVIDIA NIM (LLM_PROVIDER=nvidia; API compatível com OpenAI) ─────────
    nvidia_nim_api_key: SecretStr = SecretStr("")  # obrigatória com LLM_PROVIDER=nvidia
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    # Sugestão: o catálogo gratuito muda com frequência; confira com scripts/comparar_modelos.py.
    nvidia_nim_modelo: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nvidia_nim_temperatura: float | None = None  # vazio: padrão do modelo, como no Gemini
    # Limite da resposta, raciocínio incluído: precisa ser maior que o orçamento de raciocínio.
    nvidia_nim_max_tokens: int = Field(8192, ge=1)
    nvidia_nim_raciocinio: str = ""  # "", "ligado" ou "desligado" (vazio: padrão do modelo)
    nvidia_nim_orcamento_raciocinio: int | None = Field(None, ge=1)  # vazio: não envia

    # ── Banco de dados ───────────────────────────────────────────────────────
    database_url: str = "sqlite:///./data/novamente.db"

    # ── RAG / Chroma ─────────────────────────────────────────────────────────
    chroma_dir: str = "/data/chroma"

    # ── OCI Object Storage ───────────────────────────────────────────────────
    oci_config_file: str = "~/.oci/config"
    oci_profile: str = "DEFAULT"
    oci_namespace: str = ""
    oci_bucket: str = "novamente-conteudos-educativos"
    oci_regiao: str = ""

    # ── Jobs e histórico (SQLite) ────────────────────────────────────────────
    db_path: str = "./data/novamente.db"  # mesmo arquivo do catálogo; em produção, use um volume
    job_ttl_segundos: int = 1800  # 30 minutos
    job_timeout_segundos: int = 300  # 5 minutos (igual ao frontend)
    llm_timeout_segundos: int = 120  # por chamada ao Gemini
    # Retentativa de falhas transitórias do LLM (app/llm/retentativa.py). Valores
    # fora do intervalo impedem a subida.
    llm_tentativas: int = Field(3, ge=1)  # chamadas por geração, contando a primeira
    llm_espera_inicial_segundos: float = Field(2.0, ge=0)  # dobra a cada retentativa

    # ── Limites de entrada ───────────────────────────────────────────────────
    texto_min_caracteres: int = 200
    texto_max_caracteres: int = 50_000
    arquivo_max_bytes: int = 10 * 1024 * 1024  # 10 MiB

    @field_validator("nvidia_nim_temperatura", "nvidia_nim_orcamento_raciocinio", mode="before")
    @classmethod
    def _vazio_e_none(cls, valor):
        """Linha vazia no .env (``NVIDIA_NIM_TEMPERATURA=``) vale como não definida."""
        if isinstance(valor, str) and not valor.strip():
            return None
        return valor

    @field_validator("nvidia_nim_raciocinio", mode="before")
    @classmethod
    def _raciocinio_valido(cls, valor):
        normalizado = str(valor or "").strip().lower()
        if normalizado not in RACIOCINIO_VALORES:
            raise ValueError(
                f"NVIDIA_NIM_RACIOCINIO '{valor}' inválido. "
                "Valores válidos: vazio (padrão do modelo), ligado, desligado."
            )
        return normalizado


settings = Settings()

# Sincroniza com os.environ para módulos do LangChain e RAG
if settings.google_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
if settings.chroma_dir:
    os.environ["CHROMA_DIR"] = settings.chroma_dir
