"""Compara modelos da NVIDIA NIM gerando material com o pipeline real.

Para cada modelo, variante de raciocínio, documento de ``data/exemplos/`` e
formato, monta o prompt e gera o conteúdo com as funções do pipeline
(``_montar_prompt``, ``_gerar_conteudo`` e ``_avaliar_qualidade`` de
app/services/pipeline.py) e mede:

- ancoragem na fonte (``ancoragem_fonte_score``, app/services/ancoragem.py);
- JSON válido na primeira resposta (sem usar a retentativa de resposta
  inválida do pipeline);
- gerações cortadas pelo limite de tokens (``finish_reason`` "length");
- latência das chamadas;
- tokens, quando a API devolve ``usage``.

Variantes de raciocínio (``--raciocinio``): ``padrao`` não envia nada (vale
o padrão do modelo); ``desligado`` e ``ligado`` enviam
``chat_template_kwargs.enable_thinking``. Uma variante que o modelo recusa
(HTTP 4xx) fica como "não suportado" e o script segue para a próxima.

Variáveis de ambiente:

- ``NVIDIA_NIM_API_KEY`` (obrigatória), ``NVIDIA_NIM_BASE_URL``,
  ``NVIDIA_NIM_TEMPERATURA``, ``NVIDIA_NIM_MAX_TOKENS`` e
  ``NVIDIA_NIM_ORCAMENTO_RACIOCINIO`` (opcionais), lidas como no backend;
  ``LLM_TIMEOUT_SEGUNDOS`` limita cada chamada. ``NVIDIA_NIM_RACIOCINIO`` é
  substituída pela variante em teste.
- ``GOOGLE_API_KEY`` NÃO é necessária. A ancoragem é lexical (compara o
  conteúdo gerado com o texto completo do documento) e não usa embeddings.
  Os embeddings do Gemini só servem para escolher os trechos do prompt; os
  exemplos têm cerca de 2 KB, cabem inteiros nos 6 trechos que o pipeline
  recupera, então aqui os trechos são os do chunking, na ordem do documento,
  e o Chroma não é usado.

As chamadas são sequenciais, com intervalo mínimo entre elas (padrão 1,6 s,
cerca de 37 por minuto, abaixo do limite de ~40 do plano gratuito). Quem decide
que um modelo está indisponível é o HTTP 404 na geração: aí ele fica como
"indisponível" e o script segue para o próximo. Um modelo que não aparece no
``GET /models`` é tentado mesmo assim (alguns modelos com endpoint próprio não
são listados); se gerar, fica como "disponível (fora do /models)". A falha de
uma geração não interrompe as outras e não há retentativa de falhas
passageiras: um 429 conta como falha. Chave inválida (HTTP 401/403)
interrompe tudo e grava o relatório parcial.

O relatório em Markdown vai para ``data/relatorios/`` (ignorada pelo git).
Nada da chave nem de corpo de resposta é impresso ou gravado.

Uso (no container, a partir de /app):
    python scripts/comparar_modelos.py --listar
    python scripts/comparar_modelos.py
    python scripts/comparar_modelos.py --modelos org/modelo-a,org/modelo-b \\
        --raciocinio padrao,desligado --documentos http_apis_rest.md \\
        --formatos Quiz --intervalo 3
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import settings  # noqa: E402
from app.llm.erros import (  # noqa: E402
    ErroAutenticacao,
    ErroLLM,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
)
from app.rag.chunking import dividir_texto  # noqa: E402
from app.services import pipeline  # noqa: E402

# Lista baseada no catálogo de chat do build.nvidia.com em 18/11/2026; o
# GET /models da conta é quem decide (veja --listar).
MODELOS_PADRAO = [
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "google/gemma-4-31b-it",
    "openai/gpt-oss-20b",
    "deepseek-ai/deepseek-v4.1-flash",
    "z-ai/glm-5-3-flash",
]
DOCUMENTOS_PADRAO = ["http_apis_rest.md", "sql_consultas.md", "git_versionamento.md"]
FORMATOS_PADRAO = ["Flashcards", "Tutorial"]
# Variante de raciocínio -> valor de NVIDIA_NIM_RACIOCINIO enviado ao provedor.
VARIANTES_RACIOCINIO = {"padrao": "", "desligado": "desligado", "ligado": "ligado"}
RACIOCINIO_PADRAO = ["padrao"]
PERFIL, NIVEL, NICHO = "Desenvolvedor", "Tecnico", "Geral"
TRECHOS_NO_PROMPT = 6  # o mesmo k da recuperação no pipeline
INTERVALO_PADRAO_SEGUNDOS = 1.6
EXEMPLOS = BACKEND / "data" / "exemplos"
RELATORIOS = BACKEND / "data" / "relatorios"

OK, FALHA, INDISPONIVEL, NAO_SUPORTADO = "ok", "falha", "indisponível", "não suportado"
MOTIVO_CORTE = "length"


@dataclass(frozen=True)
class Documento:
    nome: str
    titulo: str
    texto: str


@dataclass
class Medicao:
    modelo: str
    raciocinio: str
    documento: str
    formato: str
    status: str
    ancoragem: float | None = None
    clareza: str | None = None
    json_valido_primeira: bool = False
    cortada: bool = False
    chamadas: int = 0
    latencia_s: float | None = None
    tokens: int | None = None
    erro: str | None = None
    fora_do_catalogo: bool = False  # o modelo não apareceu no GET /models, mas foi tentado


@dataclass
class ResumoModelo:
    modelo: str
    raciocinio: str
    situacao: str
    geracoes: int = 0
    ok: int = 0
    falhas: int = 0
    cortadas: int = 0
    ancoragem_media: float | None = None
    json_valido_taxa: float | None = None
    latencia_media_s: float | None = None
    tokens_medios: float | None = None
    erros: Counter = field(default_factory=Counter)


class ComparacaoInterrompida(Exception):
    """Chave inválida ou sem acesso: nada mais vai funcionar. Leva o que já foi medido."""

    def __init__(self, motivo: str, medicoes: list[Medicao]):
        super().__init__(motivo)
        self.medicoes = medicoes


# ── Documentos ────────────────────────────────────────────────────────────────


def carregar_documento(caminho: Path) -> Documento:
    """Título é a primeira linha sem o "# ", como nos jobs de calibração."""
    texto = caminho.read_text(encoding="utf-8")
    primeira = texto.strip().splitlines()[0] if texto.strip() else caminho.stem
    return Documento(caminho.name, primeira.lstrip("#").strip() or caminho.stem, texto)


def trechos_do_documento(documento: Documento) -> list[str]:
    return dividir_texto(documento.texto)[:TRECHOS_NO_PROMPT]


# ── Medição ───────────────────────────────────────────────────────────────────


class Ritmo:
    """Intervalo mínimo entre requisições, compartilhado por todos os modelos."""

    def __init__(self, intervalo_segundos: float, dormir=time.sleep, relogio=time.monotonic):
        self.intervalo = max(0.0, intervalo_segundos)
        self._dormir, self._relogio = dormir, relogio
        self._ultima: float | None = None

    def aguardar(self) -> None:
        if self._ultima is not None:
            espera = self.intervalo - (self._relogio() - self._ultima)
            if espera > 0:
                self._dormir(espera)

    def marcar(self) -> None:
        self._ultima = self._relogio()


class ProvedorMedido:
    """Embrulha um ``ProvedorLLM`` registrando latência, tokens, motivo de fim e erro."""

    def __init__(self, base, ritmo: Ritmo, relogio=time.monotonic):
        self.base = base
        self.nome = base.nome
        self.ritmo = ritmo
        self._relogio = relogio
        self.chamadas: list[dict] = []

    def gerar(self, mensagens, *, timeout_segundos: float) -> str:
        self.ritmo.aguardar()
        inicio = self._relogio()
        registro: dict = {"latencia_s": None, "tokens": None, "motivo_fim": None, "erro": None}
        self.chamadas.append(registro)
        try:
            texto = self.base.gerar(mensagens, timeout_segundos=timeout_segundos)
        except Exception as exc:
            registro["erro"] = exc
            raise
        finally:
            registro["latencia_s"] = self._relogio() - inicio
            registro["motivo_fim"] = getattr(self.base, "ultimo_motivo_fim", None)
            self.ritmo.marcar()
        uso = getattr(self.base, "ultimo_uso", None) or {}
        registro["tokens"] = uso.get("total_tokens") if isinstance(uso.get("total_tokens"), int) else None
        return texto


def medir_geracao(
    medido: ProvedorMedido, modelo: str, raciocinio: str, documento: Documento, formato: str
) -> Medicao:
    """Uma geração com as funções do pipeline.

    Só levanta ``ErroAutenticacao`` (chave inválida); qualquer outra falha
    vira uma medição com status "falha", "indisponível" ou "não suportado".
    """
    inicio = len(medido.chamadas)
    prompt = pipeline._montar_prompt(
        documento.titulo, trechos_do_documento(documento), PERFIL, formato, NICHO, NIVEL
    )
    medicao = Medicao(modelo, raciocinio, documento.nome, formato, OK)
    try:
        # Devolve também o valor cru de conceitos_chave, que o comparador não mede.
        _texto, conteudo, _conceitos = pipeline._gerar_conteudo(
            medido, prompt, formato, avisar_revisao=lambda: None
        )
        # Sem recuperação, não há relevância: o último recurso da ancoragem fica em 0.
        avaliacao = pipeline._avaliar_qualidade(0.0, conteudo, documento.texto)
        medicao.ancoragem = avaliacao.ancoragem_fonte_score
        medicao.clareza = avaliacao.clareza_pedagogica
    except Exception as exc:  # RuntimeError do pipeline ou erro inesperado
        medicao.status = FALHA
        medicao.erro = type(exc).__name__
    chamadas = medido.chamadas[inicio:]
    erros = [c["erro"] for c in chamadas if c["erro"] is not None]
    if any(isinstance(e, ErroAutenticacao) for e in erros):
        raise next(e for e in erros if isinstance(e, ErroAutenticacao))
    if medicao.status == FALHA:
        if erros:
            medicao.erro = type(erros[-1]).__name__
            if isinstance(erros[-1], ErroModeloIndisponivel):
                medicao.status = INDISPONIVEL
            elif isinstance(erros[-1], ErroRequisicaoRecusada):
                medicao.status = NAO_SUPORTADO
        else:
            medicao.erro = "RespostaInvalida"  # as respostas vieram, mas nenhuma passou na validação
    medicao.chamadas = len(chamadas)
    medicao.cortada = any(c["motivo_fim"] == MOTIVO_CORTE for c in chamadas)
    medicao.json_valido_primeira = medicao.status == OK and len(chamadas) == 1
    latencias = [c["latencia_s"] for c in chamadas if c["latencia_s"] is not None]
    medicao.latencia_s = sum(latencias) if latencias else None
    tokens = [c["tokens"] for c in chamadas if c["erro"] is None]
    medicao.tokens = sum(tokens) if tokens and all(isinstance(t, int) for t in tokens) else None
    return medicao


def verificar_catalogo(base, ritmo: Ritmo) -> bool | None:
    """True/False pelo ``GET /models``; None se não deu para consultar (segue e tenta gerar)."""
    verificar = getattr(base, "modelo_disponivel", None)
    if verificar is None:
        return None
    ritmo.aguardar()
    try:
        return verificar()
    except ErroAutenticacao:
        raise  # chave inválida: não adianta seguir com nenhum modelo
    except Exception:
        return None
    finally:
        ritmo.marcar()


def comparar(
    modelos: Iterable[str],
    variantes: list[str],
    documentos: list[Documento],
    formatos: list[str],
    criar_provedor: Callable[[str, str], object],
    ritmo: Ritmo,
    avisar: Callable[[Medicao], None] = lambda _m: None,
    informar: Callable[[str], None] = lambda _t: None,
) -> list[Medicao]:
    """Mede cada modelo em cada variante de raciocínio, documento e formato, em sequência.

    ``criar_provedor(modelo, variante)`` devolve o provedor daquela variante.
    Um modelo que não aparece no ``GET /models`` é tentado mesmo assim (alguns
    modelos com endpoint próprio não são listados); só o HTTP 404 na geração
    o marca como indisponível. ``informar`` recebe os avisos de texto.
    Levanta ``ComparacaoInterrompida`` (com o que já foi medido) se a chave
    for recusada.
    """
    medicoes: list[Medicao] = []

    def registrar(medicao: Medicao) -> None:
        medicoes.append(medicao)
        avisar(medicao)

    try:
        for modelo in modelos:
            fora_do_catalogo = verificar_catalogo(criar_provedor(modelo, variantes[0]), ritmo) is False
            if fora_do_catalogo:
                informar(f"{modelo}: não listado em /models; tentando mesmo assim")
            pares = [(documento, formato) for documento in documentos for formato in formatos]
            for variante in variantes:
                medido = ProvedorMedido(criar_provedor(modelo, variante), ritmo)
                parada = None
                for documento, formato in pares:
                    medicao = medir_geracao(medido, modelo, variante, documento, formato)
                    medicao.fora_do_catalogo = fora_do_catalogo
                    registrar(medicao)
                    if medicao.status in (INDISPONIVEL, NAO_SUPORTADO):
                        parada = medicao.status  # o resto desta variante daria o mesmo
                        break
                if parada == INDISPONIVEL:
                    break  # 404: as outras variantes do modelo também
    except ErroAutenticacao as exc:
        raise ComparacaoInterrompida(str(exc), medicoes) from None
    return medicoes


# ── Agregação e relatório ─────────────────────────────────────────────────────


def _media(valores: list[float]) -> float | None:
    return sum(valores) / len(valores) if valores else None


def _situacao(lista: list[Medicao]) -> str:
    if any(m.status == INDISPONIVEL for m in lista):
        return INDISPONIVEL
    if any(m.status == NAO_SUPORTADO for m in lista):
        return NAO_SUPORTADO
    if any(m.fora_do_catalogo for m in lista):
        return "disponível (fora do /models)"
    return "disponível"


def agregar(medicoes: Iterable[Medicao]) -> list[ResumoModelo]:
    """Um resumo por modelo e variante de raciocínio, na ordem em que aparecem."""
    grupos: dict[tuple[str, str], list[Medicao]] = {}
    for medicao in medicoes:
        grupos.setdefault((medicao.modelo, medicao.raciocinio), []).append(medicao)
    resumos = []
    for (modelo, raciocinio), lista in grupos.items():
        geracoes = [m for m in lista if m.status not in (INDISPONIVEL, NAO_SUPORTADO)]
        ok = [m for m in geracoes if m.status == OK]
        resumos.append(ResumoModelo(
            modelo=modelo,
            raciocinio=raciocinio,
            situacao=_situacao(lista),
            geracoes=len(geracoes),
            ok=len(ok),
            falhas=len(geracoes) - len(ok),
            cortadas=sum(m.cortada for m in lista),
            ancoragem_media=_media([m.ancoragem for m in ok if m.ancoragem is not None]),
            json_valido_taxa=(
                sum(m.json_valido_primeira for m in geracoes) / len(geracoes) if geracoes else None
            ),
            latencia_media_s=_media([m.latencia_s for m in geracoes if m.latencia_s is not None]),
            tokens_medios=_media([m.tokens for m in ok if m.tokens is not None]),
            erros=Counter(m.erro for m in lista if m.erro),
        ))
    return resumos


def _numero(valor: float | None, casas: int = 3) -> str:
    return "—" if valor is None else f"{valor:.{casas}f}".replace(".", ",")


def _percentual(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.0f}%"


def tabela_markdown(resumos: Iterable[ResumoModelo]) -> str:
    linhas = [
        "| Modelo | Raciocínio | Situação | Gerações ok | Ancoragem média "
        "| JSON válido na 1ª resposta | Cortadas | Latência média (s) | Tokens médios | Falhas |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resumos:
        falhas = ", ".join(f"{erro} ×{n}" for erro, n in sorted(r.erros.items())) or "—"
        linhas.append(
            f"| `{r.modelo}` | {r.raciocinio} | {r.situacao} | {r.ok}/{r.geracoes} "
            f"| {_numero(r.ancoragem_media)} | {_percentual(r.json_valido_taxa)} | {r.cortadas} "
            f"| {_numero(r.latencia_media_s, 1)} | {_numero(r.tokens_medios, 0)} | {falhas} |"
        )
    return "\n".join(linhas)


def tabela_detalhada(medicoes: Iterable[Medicao]) -> str:
    linhas = [
        "| Modelo | Raciocínio | Documento | Formato | Situação | Ancoragem | Clareza | JSON na 1ª "
        "| Cortada | Chamadas | Latência (s) | Tokens | Erro |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in medicoes:
        linhas.append(
            f"| `{m.modelo}` | {m.raciocinio} | {m.documento} | {m.formato} | {m.status} "
            f"| {_numero(m.ancoragem)} | {m.clareza or '—'} | {'sim' if m.json_valido_primeira else 'não'} "
            f"| {'sim' if m.cortada else 'não'} | {m.chamadas} | {_numero(m.latencia_s, 1)} "
            f"| {m.tokens if m.tokens is not None else '—'} | {m.erro or '—'} |"
        )
    return "\n".join(linhas)


def montar_relatorio(medicoes: list[Medicao], documentos: list[Documento], formatos: list[str],
                     quando: datetime, interrompido: str | None = None) -> str:
    linhas = [f"# Comparação de modelos (NVIDIA NIM), {quando:%Y-%m-%d %H:%M}", ""]
    if interrompido:
        linhas += [f"> **Relatório parcial:** comparação interrompida ({interrompido}).", ""]
    linhas += [
        f"- Documentos: {', '.join(f'{d.nome} ({len(d.texto)} caracteres)' for d in documentos)}",
        f"- Formatos: {', '.join(formatos)}; perfil {PERFIL}, nível {NIVEL}, nicho {NICHO}",
        "- Ancoragem: média das gerações que terminaram bem; JSON válido: gerações aceitas "
        "na primeira resposta, sem a retentativa de resposta inválida; cortadas: gerações "
        "com alguma resposta encerrada pelo limite de tokens.",
        "",
        "## Resumo por modelo e raciocínio",
        "",
        tabela_markdown(agregar(medicoes)),
        "",
        "## Gerações",
        "",
        tabela_detalhada(medicoes),
        "",
    ]
    return "\n".join(linhas)


def gravar_relatorio(texto: str, quando: datetime, pasta: Path = RELATORIOS) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"comparacao_modelos_{quando:%Y%m%d_%H%M%S}.md"
    destino.write_text(texto, encoding="utf-8")
    return destino


# ── Linha de comando ──────────────────────────────────────────────────────────


def _lista(valor: str) -> list[str]:
    return [item.strip() for item in valor.split(",") if item.strip()]


def listar(provedor) -> int:
    """``--listar``: imprime os ids do catálogo da conta, em ordem, e sai."""
    try:
        ids = provedor.listar_modelos()
    except ErroLLM as exc:  # mensagem sem chave nem corpo da resposta
        print(f"Não foi possível listar os modelos: {exc}", file=sys.stderr)
        return 1
    for modelo in ids:
        print(modelo)
    return 0


def main(argv: list[str] | None = None, *, criar_provedor=None, pasta_relatorios: Path = RELATORIOS) -> int:
    parser = argparse.ArgumentParser(description="Compara modelos da NVIDIA NIM no pipeline real.")
    parser.add_argument("--modelos", type=_lista, default=MODELOS_PADRAO, help="ids separados por vírgula")
    parser.add_argument("--raciocinio", type=_lista, default=RACIOCINIO_PADRAO,
                        help="variantes separadas por vírgula: padrao, desligado, ligado")
    parser.add_argument("--documentos", type=_lista, default=DOCUMENTOS_PADRAO,
                        help="arquivos de data/exemplos/, separados por vírgula")
    parser.add_argument("--formatos", type=_lista, default=FORMATOS_PADRAO,
                        help="Flashcards, Quiz, Tutorial e/ou ResumoExecutivo")
    parser.add_argument("--intervalo", type=float, default=INTERVALO_PADRAO_SEGUNDOS,
                        help="segundos mínimos entre requisições")
    parser.add_argument("--listar", action="store_true",
                        help="só lista os ids do GET /models da conta e sai")
    args = parser.parse_args(argv)

    if not settings.nvidia_nim_api_key.get_secret_value():
        print("NVIDIA_NIM_API_KEY não definida no ambiente.", file=sys.stderr)
        return 2
    if criar_provedor is None:
        from app.llm.nvidia import criar_provedor_nvidia

        def criar_provedor(modelo, variante):
            return criar_provedor_nvidia(modelo, raciocinio=VARIANTES_RACIOCINIO[variante])

    if args.listar:
        return listar(criar_provedor(None, RACIOCINIO_PADRAO[0]))
    invalidos = [f for f in args.formatos if f not in pipeline._INSTRUCOES_FORMATO]
    invalidos += [v for v in args.raciocinio if v not in VARIANTES_RACIOCINIO]
    if invalidos or not args.raciocinio:
        print(f"Formato ou raciocínio desconhecido: {', '.join(invalidos) or '(vazio)'}. "
              f"Raciocínio: {', '.join(VARIANTES_RACIOCINIO)}.", file=sys.stderr)
        return 2
    documentos = [carregar_documento(EXEMPLOS / nome) for nome in args.documentos]

    def avisar(m: Medicao) -> None:
        print(f"{m.modelo} | {m.raciocinio} | {m.documento} | {m.formato} | {m.status} | ancoragem "
              f"{_numero(m.ancoragem)} | {_numero(m.latencia_s, 1)} s | {m.erro or ''}", flush=True)

    interrompido = None
    try:
        medicoes = comparar(args.modelos, args.raciocinio, documentos, args.formatos, criar_provedor,
                            Ritmo(args.intervalo), avisar,
                            informar=lambda texto: print(texto, flush=True))
    except ComparacaoInterrompida as exc:
        medicoes, interrompido = exc.medicoes, str(exc)

    agora = datetime.now()
    destino = gravar_relatorio(
        montar_relatorio(medicoes, documentos, args.formatos, agora, interrompido), agora, pasta_relatorios
    )
    print()
    print(tabela_markdown(agregar(medicoes)))
    print(f"\nRelatório: {destino}")
    if interrompido:
        print(f"Interrompido: {interrompido} Relatório parcial gravado.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
