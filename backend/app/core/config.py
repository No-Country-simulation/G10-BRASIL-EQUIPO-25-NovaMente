"""Configurações da aplicação via variáveis de ambiente."""

import os
from pathlib import Path
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Padrões do chat na nvidia, escolhidos pela medição de 19/11/2026 (README,
# "Modelo padrão do chat"). O modelo padrão vem primeiro na lista.
MODELO_PADRAO_CHAT = "google/gemma-4-31b-it"
MODELOS_PERMITIDOS_CHAT = (
    "google/gemma-4-31b-it,nvidia/nemotron-3.5-bolt-e4b,nvidia/nemotron-3.5-lightning-30b-a3b"
)

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
    # Desligado por padrão: com o raciocínio no padrão do modelo, ele consome o
    # NVIDIA_NIM_MAX_TOKENS e o JSON do material sai cortado (finish_reason=length).
    # Vazio também vale "desligado"; "padrao" não envia nada (vale o padrão do modelo).
    nvidia_nim_raciocinio: str = "desligado"  # "desligado", "ligado" ou "padrao"
    nvidia_nim_orcamento_raciocinio: int | None = Field(None, ge=1)  # vazio: não envia

    # ── Chat sobre o material (provedor próprio, independente de LLM_PROVIDER) ──
    # Vazio em qualquer CHAT_* vale como o padrão abaixo.
    chat_llm_provider: str = "nvidia"  # provedor registrado em app/llm/fabrica.py
    # Medição de 19/11/2026 (scripts/medir_chat.py; veja o README). Os dois
    # padrões abaixo são ids da NVIDIA: com outro CHAT_LLM_PROVIDER e sem valor
    # próprio, ficam vazios e valem o modelo padrão daquele provedor.
    chat_llm_modelo: str = MODELO_PADRAO_CHAT
    chat_llm_raciocinio: str = "desligado"  # "ligado" ou "desligado"; vazio vale "desligado"
    chat_llm_max_tokens: int = Field(1024, ge=64)
    chat_llm_temperatura: float = Field(0.2, ge=0, le=2)
    chat_llm_timeout_segundos: int = Field(45, ge=5)  # prazo total de uma pergunta
    # Ids separados por vírgula; o modelo do chat sempre entra, em primeiro lugar.
    chat_modelos_permitidos: str = MODELOS_PERMITIDOS_CHAT
    # Limites do serviço do chat
    chat_max_pergunta_caracteres: int = Field(1000, ge=1)
    chat_max_mensagens_historico: int = Field(10, ge=1)  # mensagens anteriores aceitas no pedido
    chat_max_contexto_caracteres: int = Field(24_000, ge=1)
    chat_limite_por_minuto: int = Field(12, ge=1)  # perguntas por aluno

    # ── Geração multiagente (app/services/geracao_grafo.py) ─────────────────
    # Desligada por padrão: a geração é a passada única de sempre. Vazio vale o padrão.
    geracao_multiagente: bool = False
    grafo_max_revisoes: int = Field(2, ge=0, le=2)  # rodadas de revisão além da primeira escrita
    # Ancoragem que aprova o rascunho. Nas 12 saídas reais da calibração
    # (tests/services/test_ancoragem_calibracao.py) as fiéis vão de 0,706 a 0,999,
    # com um vão entre 0,732 e 0,787; 0,75 revisa só as duas mais fracas e fica
    # muito acima do maior falso positivo (0,187). Provisório: são só 12 saídas.
    grafo_limiar_ancoragem: float = Field(0.75, ge=0, le=1)
    grafo_max_simultaneos: int = Field(2, ge=1)  # jobs no grafo ao mesmo tempo; sem vaga, passada única

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

    @field_validator(
        "chat_llm_provider",
        "chat_llm_modelo",
        "chat_modelos_permitidos",
        "chat_llm_raciocinio",
        "chat_llm_max_tokens",
        "chat_llm_temperatura",
        "chat_llm_timeout_segundos",
        "chat_max_pergunta_caracteres",
        "chat_max_mensagens_historico",
        "chat_max_contexto_caracteres",
        "chat_limite_por_minuto",
        "geracao_multiagente",
        "grafo_max_revisoes",
        "grafo_limiar_ancoragem",
        "grafo_max_simultaneos",
        mode="before",
    )
    @classmethod
    def _chat_vazio_e_padrao(cls, valor, info):
        """``CHAT_LLM_MAX_TOKENS=`` (linha vazia no .env) vale como o padrão do campo."""
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return cls.model_fields[info.field_name].default
        return valor

    @field_validator("chat_llm_provider", "chat_llm_modelo", "chat_modelos_permitidos")
    @classmethod
    def _sem_espacos(cls, valor: str) -> str:
        return valor.strip()

    @field_validator("chat_llm_provider")
    @classmethod
    def _provedor_minusculo(cls, valor: str) -> str:
        return valor.lower()

    @model_validator(mode="after")
    def _modelos_do_chat_so_na_nvidia(self):
        """Fora da nvidia, os padrões de modelo do chat (ids da NVIDIA) não se aplicam.

        Sem CHAT_LLM_MODELO/CHAT_MODELOS_PERMITIDOS próprios (ausentes ou vazios),
        ficam vazios e o chat usa o modelo padrão do provedor (app/llm/fabrica.py).
        """
        if self.chat_llm_provider != "nvidia":
            if self.chat_llm_modelo == MODELO_PADRAO_CHAT:
                self.chat_llm_modelo = ""
            if self.chat_modelos_permitidos == MODELOS_PERMITIDOS_CHAT:
                self.chat_modelos_permitidos = ""
        return self

    @field_validator("chat_llm_raciocinio")
    @classmethod
    def _raciocinio_do_chat_valido(cls, valor: str) -> str:
        normalizado = str(valor).strip().lower()
        if normalizado not in ("ligado", "desligado"):
            raise ValueError(
                f"CHAT_LLM_RACIOCINIO '{valor}' inválido. "
                "Valores válidos: vazio (desligado), ligado, desligado."
            )
        return normalizado

    @field_validator("nvidia_nim_raciocinio", mode="before")
    @classmethod
    def _raciocinio_valido(cls, valor):
        normalizado = str(valor or "").strip().lower()
        if not normalizado:
            return "desligado"
        if normalizado == "padrao":
            return ""  # o provedor não envia o parâmetro
        if normalizado not in RACIOCINIO_VALORES:
            raise ValueError(
                f"NVIDIA_NIM_RACIOCINIO '{valor}' inválido. "
                "Valores válidos: vazio (desligado), desligado, ligado, padrao."
            )
        return normalizado


settings = Settings()

# Sincroniza com os.environ para módulos do LangChain e RAG
if settings.google_api_key and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
if settings.chroma_dir:
    os.environ["CHROMA_DIR"] = settings.chroma_dir
