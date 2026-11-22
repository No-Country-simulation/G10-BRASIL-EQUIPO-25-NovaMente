"""Configurações da aplicação via variáveis de ambiente."""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

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
    # Chave das rotas da empresa (cabeçalho X-API-Key). Vazia = rotas abertas.
    # repr=False para a chave nunca aparecer ao imprimir as configurações.
    api_key_empresa: str = Field("", repr=False)

    # ── Google Gemini ────────────────────────────────────────────────────────
    google_api_key: str = ""
    llm_provider: str = "gemini"  # provedor de LLM registrado em app/llm/fabrica.py
    modelo_llm: str = "gemini-3.5-flash-lite"

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
    # Backup do SQLite (app/services/backup.py). Caminhos relativos valem a partir
    # da pasta de execução (backend/). BACKUP_RETENCAO fora do intervalo impede a subida.
    backup_dir: str = Field("./data/backups", min_length=1)
    backup_retencao: int = Field(7, ge=1)  # quantidade de backups mantidos na pasta
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

    # ── Segurança de entrada (CORS e limites de uso) ─────────────────────────
    # Origens permitidas no CORS, separadas por vírgula. Cada uma no formato
    # esquema://host[:porta], sem barra final. "*" é recusado: o CORS usa credenciais.
    cors_origins: str = "http://localhost:3000"
    # Gerações (POST /adaptacoes e /adaptacoes/upload) por minuto, por IP de cliente.
    geracao_limite_por_minuto: int = Field(6, ge=1)
    # Jobs de geração em andamento (queued ou running) ao mesmo tempo, no processo.
    geracao_max_jobs_simultaneos: int = Field(4, ge=1)
    # Usa o X-Forwarded-For como IP do cliente. Só ligue atrás de um proxy confiável.
    confiar_x_forwarded_for: bool = False

    @field_validator("cors_origins")
    @classmethod
    def _validar_cors_origins(cls, valor: str) -> str:
        import re

        origens = [item.strip() for item in valor.split(",") if item.strip()]
        if not origens:
            raise ValueError("CORS_ORIGINS não pode ficar vazia; informe ao menos uma origem.")
        for origem in origens:
            if origem == "*":
                raise ValueError(
                    "CORS_ORIGINS não aceita '*': o CORS usa credenciais, e "
                    "liberar qualquer origem com credenciais é inseguro. "
                    "Liste as origens, como https://app.exemplo.com."
                )
            if not re.fullmatch(r"https?://[^/\s,]+", origem):
                raise ValueError(
                    f"CORS_ORIGINS tem uma origem inválida: '{origem}'. Use "
                    "esquema://host[:porta], sem caminho nem barra final."
                )
        return ",".join(origens)

    @property
    def cors_origins_lista(self) -> list[str]:
        """Origens do CORS já separadas, sem espaços nem entradas vazias."""
        return [item for item in self.cors_origins.split(",") if item]


settings = Settings()

# Sincroniza com os.environ para módulos do LangChain e RAG
if settings.google_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
if settings.chroma_dir:
    os.environ["CHROMA_DIR"] = settings.chroma_dir
