"""Adaptador da NVIDIA NIM para ``ProvedorLLM`` (API compatível com OpenAI).

Chama ``POST {NVIDIA_NIM_BASE_URL}/chat/completions`` com ``httpx``. Como no
Gemini, a chave (``NVIDIA_NIM_API_KEY``) só é exigida na geração: sem ela, a
chamada falha com ``ErroConfiguracao`` e a subida do app não é afetada. O
cliente HTTP é criado uma vez e reaproveitado; o timeout vale por chamada e
não há retentativa interna (quem retenta é ``ProvedorComRetentativa``).

A chave nunca vai para log, mensagem de erro nem ``repr``: os erros levam só
o código HTTP ou o tipo da exceção, e são levantados sem a exceção original
encadeada (que carregaria a requisição).

``modelo_disponivel`` consulta ``GET {base_url}/models``; não roda na subida,
é usada por scripts/comparar_modelos.py.
"""

from __future__ import annotations

import logging
import re
import threading

import httpx

from app.core.config import RACIOCINIO_VALORES, settings
from app.llm.base import Mensagem
from app.llm.erros import (
    ErroAutenticacao,
    ErroConfiguracao,
    ErroIndisponivel,
    ErroLimiteTaxa,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
    ErroRespostaInvalida,
    ErroTimeout,
)

logger = logging.getLogger(__name__)

TIMEOUT_CATALOGO_SEGUNDOS = 30.0
_DA_CONFIGURACAO = object()  # argumento omitido: vale o que está em settings
_BLOCO_RACIOCINIO = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FIM_RACIOCINIO = re.compile(r"</think>", re.IGNORECASE)


def remover_raciocinio(texto: str) -> str:
    """Tira os blocos ``<think>...</think>`` que modelos de raciocínio põem no texto.

    Se sobrar um ``</think>`` sem abertura (o modelo começou a resposta já
    dentro do bloco), vale só o que vem depois dele.
    """
    sem_blocos = _BLOCO_RACIOCINIO.sub("", texto)
    partes = _FIM_RACIOCINIO.split(sem_blocos)
    return partes[-1].strip()


def _erro_por_status(status: int) -> Exception:
    """Erro normalizado para uma resposta HTTP de erro (sem o corpo, que pode ter dados)."""
    if status == 429:
        return ErroLimiteTaxa("NVIDIA NIM: limite de requisições atingido (HTTP 429).")
    if status in (408, 504):
        return ErroTimeout(f"NVIDIA NIM: tempo limite no servidor (HTTP {status}).")
    if status in (401, 403):
        return ErroAutenticacao(
            f"NVIDIA NIM: chave inválida ou sem acesso ao modelo (HTTP {status})."
        )
    if status == 404:
        return ErroModeloIndisponivel("NVIDIA NIM: modelo indisponível no catálogo (HTTP 404).")
    if status == 410:
        return ErroModeloIndisponivel("NVIDIA NIM: modelo removido do catálogo (HTTP 410).")
    if status >= 500:
        return ErroIndisponivel(f"NVIDIA NIM: serviço indisponível (HTTP {status}).")
    return ErroRequisicaoRecusada(f"NVIDIA NIM: requisição recusada (HTTP {status}).")


def _chave() -> str:
    chave = settings.nvidia_nim_api_key.get_secret_value()
    if not chave:
        raise ErroConfiguracao("NVIDIA_NIM_API_KEY não definida.")
    return chave


class ProvedorNvidia:
    """Gera texto com um modelo do catálogo da NVIDIA NIM."""

    nome = "nvidia"

    def __init__(
        self,
        modelo: str,
        base_url: str,
        *,
        temperatura: float | None = None,
        max_tokens: int | None = None,
        raciocinio: str = "",
        orcamento_raciocinio: int | None = None,
        transporte: httpx.BaseTransport | None = None,
    ):
        if raciocinio not in RACIOCINIO_VALORES:
            raise ValueError(
                f"Raciocínio '{raciocinio}' inválido. Valores válidos: vazio, ligado, desligado."
            )
        self.modelo = modelo
        self.base_url = base_url.rstrip("/")
        self.temperatura = temperatura
        self.max_tokens = max_tokens
        self.raciocinio = raciocinio  # "": não envia nada (vale o padrão do modelo)
        self.orcamento_raciocinio = orcamento_raciocinio
        self.ultimo_uso: dict | None = None  # campo ``usage`` da última resposta, se veio
        self.ultimo_motivo_fim: str | None = None  # ``finish_reason`` da última resposta
        self._transporte = transporte  # os testes injetam um httpx.MockTransport
        self._cliente: httpx.Client | None = None
        self._trava = threading.Lock()

    def __repr__(self) -> str:
        return f"ProvedorNvidia(modelo={self.modelo!r}, base_url={self.base_url!r})"

    def _obter_cliente(self) -> httpx.Client:
        with self._trava:
            if self._cliente is None:
                self._cliente = httpx.Client(transport=self._transporte)
            return self._cliente

    def _requisitar(self, metodo: str, caminho: str, *, timeout: float, json: dict | None = None):
        cabecalhos = {"Authorization": f"Bearer {_chave()}", "Accept": "application/json"}
        try:
            resposta = self._obter_cliente().request(
                metodo, f"{self.base_url}{caminho}", headers=cabecalhos, json=json, timeout=timeout
            )
        except httpx.TimeoutException as exc:
            logger.error("Falha na chamada à NVIDIA NIM (ErroTimeout): %s", type(exc).__name__)
            raise ErroTimeout(f"NVIDIA NIM: sem resposta em {timeout:g}s ({type(exc).__name__}).") from None
        except httpx.TransportError as exc:
            logger.error("Falha na chamada à NVIDIA NIM (ErroIndisponivel): %s", type(exc).__name__)
            raise ErroIndisponivel(f"NVIDIA NIM: falha de conexão ({type(exc).__name__}).") from None
        if resposta.status_code >= 400:
            erro = _erro_por_status(resposta.status_code)
            logger.error(
                "Falha na chamada à NVIDIA NIM (%s): HTTP %d", type(erro).__name__, resposta.status_code
            )
            raise erro
        try:
            return resposta.json()
        except ValueError:
            raise ErroRespostaInvalida("NVIDIA NIM: resposta que não é JSON.") from None

    @staticmethod
    def _montar(mensagens: list[Mensagem]) -> list[dict]:
        """Junta as instruções de sistema numa mensagem só, no início, como no Gemini."""
        sistema = [m.conteudo for m in mensagens if m.papel == "system"]
        conversa = [{"role": m.papel, "content": m.conteudo} for m in mensagens if m.papel != "system"]
        if sistema:
            conversa.insert(0, {"role": "system", "content": "\n\n".join(sistema)})
        return conversa

    def _parametros_de_raciocinio(self) -> dict:
        """Campos no nível raiz do corpo (no cliente OpenAI, eles vão em ``extra_body``)."""
        parametros: dict = {}
        if self.raciocinio:
            parametros["chat_template_kwargs"] = {"enable_thinking": self.raciocinio == "ligado"}
        if self.orcamento_raciocinio is not None and self.raciocinio != "desligado":
            parametros["reasoning_budget"] = self.orcamento_raciocinio
        return parametros

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        corpo: dict = {"model": self.modelo, "messages": self._montar(mensagens), "stream": False}
        if self.temperatura is not None:
            corpo["temperature"] = self.temperatura
        if self.max_tokens is not None:
            corpo["max_tokens"] = self.max_tokens
        corpo.update(self._parametros_de_raciocinio())
        self.ultimo_uso = None
        self.ultimo_motivo_fim = None
        dados = self._requisitar("POST", "/chat/completions", timeout=timeout_segundos, json=corpo)

        uso = dados.get("usage") if isinstance(dados, dict) else None
        self.ultimo_uso = uso if isinstance(uso, dict) else None
        try:
            escolha = dados["choices"][0]
            # Só message.content: reasoning_content (raciocínio) é ignorado.
            conteudo = escolha["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ErroRespostaInvalida("NVIDIA NIM: resposta sem choices ou sem message.") from None
        motivo = escolha.get("finish_reason")
        self.ultimo_motivo_fim = motivo if isinstance(motivo, str) else None
        if motivo == "length":
            # Mesmo com texto parcial: o JSON do material cortado não serve.
            raise ErroRespostaInvalida(
                "NVIDIA NIM: resposta cortada pelo limite de tokens; aumente "
                "NVIDIA_NIM_MAX_TOKENS ou reduza o raciocínio."
            )
        if not isinstance(conteudo, str):
            raise ErroRespostaInvalida("NVIDIA NIM: resposta sem texto.")
        texto = remover_raciocinio(conteudo)
        if not texto:
            raise ErroRespostaInvalida("NVIDIA NIM: resposta vazia.")
        return texto

    def listar_modelos(self, timeout_segundos: float = TIMEOUT_CATALOGO_SEGUNDOS) -> list[str]:
        """Ids de ``GET {base_url}/models``, em ordem alfabética."""
        dados = self._requisitar("GET", "/models", timeout=timeout_segundos)
        itens = dados.get("data") if isinstance(dados, dict) else None
        if not isinstance(itens, list):
            raise ErroRespostaInvalida("NVIDIA NIM: lista de modelos em formato inesperado.")
        return sorted(
            {item["id"] for item in itens if isinstance(item, dict) and isinstance(item.get("id"), str)}
        )

    def modelo_disponivel(self, timeout_segundos: float = TIMEOUT_CATALOGO_SEGUNDOS) -> bool:
        """True se o modelo configurado aparece em ``GET {base_url}/models``."""
        return self.modelo in self.listar_modelos(timeout_segundos)


def criar_provedor_nvidia(
    modelo: str | None = None,
    *,
    raciocinio=_DA_CONFIGURACAO,
    orcamento_raciocinio=_DA_CONFIGURACAO,
    **opcoes,
) -> ProvedorNvidia:
    """Provedor com a configuração de ``settings``.

    ``modelo``, ``raciocinio`` e ``orcamento_raciocinio`` substituem
    NVIDIA_NIM_MODELO, NVIDIA_NIM_RACIOCINIO e NVIDIA_NIM_ORCAMENTO_RACIOCINIO
    (``raciocinio=""`` força o padrão do modelo; ``orcamento_raciocinio=None``
    deixa de enviar o orçamento).
    """
    return ProvedorNvidia(
        modelo=modelo or settings.nvidia_nim_modelo,
        base_url=settings.nvidia_nim_base_url,
        temperatura=settings.nvidia_nim_temperatura,
        max_tokens=settings.nvidia_nim_max_tokens,
        raciocinio=settings.nvidia_nim_raciocinio if raciocinio is _DA_CONFIGURACAO else raciocinio,
        orcamento_raciocinio=(
            settings.nvidia_nim_orcamento_raciocinio
            if orcamento_raciocinio is _DA_CONFIGURACAO
            else orcamento_raciocinio
        ),
        **opcoes,
    )
