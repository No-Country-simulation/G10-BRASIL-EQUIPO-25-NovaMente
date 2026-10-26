"""Pipeline de geração de conteúdo didático via RAG + Gemini.

Este módulo orquestra:
  1. Extração de texto (PDF / MD / TXT já vem extraído pelo router)
  2. Indexação RAG (chunking + embeddings) — reutiliza app.rag
  3. Recuperação dos trechos mais relevantes
  4. Chamada ao LLM Gemini para gerar o conteúdo
  5. Avaliação de qualidade (ancoragem + clareza)
  6. Montagem do ``AdaptacaoPacote`` completo

O progresso é reportado via callback ``on_progresso`` para que o worker
atualize o job em memória a cada etapa.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone

from ulid import ULID  # type: ignore

from app.core.config import settings
from app.models import (
    AdaptacaoPacote,
    AvaliacaoQualidade,
    ConteudoAdaptado,
    DocumentoRef,
    EtapaJob,
    FlashcardItem,
    FormatoSaida,
    MetadadosAdaptacao,
    NivelDetalhe,
    OrigemDocumento,
    PerfilDestinatario,
    NichoSetor,
)

logger = logging.getLogger(__name__)

OnProgresso = Callable[[EtapaJob, int, str], None]


# ── Slug para nome do objeto OCI ──────────────────────────────────────────────


def _slug(texto: str) -> str:
    """Converte texto em slug ASCII em minúsculas, substituindo espaços por '-'."""
    nfkd = unicodedata.normalize("NFKD", texto)
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_str.lower()).strip("-")


def _objeto_id(titulo: str, perfil: str, formato: str, adaptacao_id: str) -> str:
    """Monta o nome do objeto OCI conforme a spec (seção 6.9)."""
    return (
        f"novamente-{_slug(titulo)}-{_slug(perfil)}-{_slug(formato)}"
        f"-{adaptacao_id[:8]}.json"
    )


# ── Prompts por formato ───────────────────────────────────────────────────────

_INSTRUCOES_FORMATO: dict[FormatoSaida, str] = {
    "Flashcards": (
        "Gere entre 5 e 20 flashcards no formato JSON:\n"
        '{"tipo":"flashcards","titulo":"...","introducao_contextualizada":"...",'
        '"itens":[{"frente":"...","verso":"...","dica_didatica":"..."}]}\n'
        "dica_didatica é opcional; use null se não se aplicar. "
        "Retorne APENAS o JSON, sem markdown."
    ),
    "Quiz": (
        "Gere entre 4 e 10 perguntas de quiz no formato JSON:\n"
        '{"tipo":"quiz","titulo":"...","introducao_contextualizada":"...",'
        '"itens":[{"pergunta":"...","opcoes":["a","b","c","d"],'
        '"resposta_correta":0,"explicacao":"..."}]}\n'
        "resposta_correta é o índice em opcoes (0-based). "
        "Retorne APENAS o JSON, sem markdown."
    ),
    "Tutorial": (
        "Gere um tutorial passo a passo em Markdown dentro do JSON:\n"
        '{"tipo":"markdown","titulo":"...","introducao_contextualizada":"...",'
        '"itens":"## Passo 1\\n...\\n## Passo 2\\n..."}\n'
        "Retorne APENAS o JSON, sem bloco de código markdown externo."
    ),
    "ResumoExecutivo": (
        "Gere um resumo executivo (TL;DR) em Markdown dentro do JSON:\n"
        '{"tipo":"markdown","titulo":"...","introducao_contextualizada":"...",'
        '"itens":"## Pontos-chave\\n- ...\\n## Conclusão\\n..."}\n'
        "Retorne APENAS o JSON, sem bloco de código markdown externo."
    ),
}

_PERFIL_DESC: dict[PerfilDestinatario, str] = {
    "Iniciante": "iniciante em tecnologia / transição de carreira",
    "Desenvolvedor": "desenvolvedor júnior ou pleno",
    "LiderTecnico": "líder técnico ou arquiteto de software",
    "Gestor": "gestor ou executivo não técnico",
}

_NIVEL_DESC: dict[NivelDetalhe, str] = {
    "Didatico": "didático e acessível, com analogias e exemplos simples",
    "Tecnico": "técnico e preciso, com terminologia correta",
    "Executivo": "conciso e orientado a impacto de negócio",
}


def _montar_prompt(
    titulo: str,
    trechos: list[str],
    perfil: PerfilDestinatario,
    formato: FormatoSaida,
    nicho: NichoSetor,
    nivel: NivelDetalhe,
) -> str:
    contexto = "\n\n---\n\n".join(trechos)
    instrucoes = _INSTRUCOES_FORMATO[formato]
    return (
        f"Você é um especialista em educação técnica.\n"
        f"Público-alvo: {_PERFIL_DESC[perfil]}.\n"
        f"Setor / nicho: {nicho}.\n"
        f"Tom: {_NIVEL_DESC[nivel]}.\n\n"
        f"DOCUMENTO: {titulo}\n\n"
        f"TRECHOS RELEVANTES DO DOCUMENTO:\n{contexto}\n\n"
        f"TAREFA:\n{instrucoes}"
    )


# ── Parser de resposta do LLM ─────────────────────────────────────────────────


def _extrair_json(texto: str) -> dict:
    """Extrai o primeiro objeto JSON encontrado na resposta do LLM."""
    # Remove blocos ```json ... ```
    limpo = re.sub(r"```(?:json)?\s*", "", texto).replace("```", "")
    inicio = limpo.find("{")
    fim = limpo.rfind("}") + 1
    if inicio == -1 or fim == 0:
        raise ValueError("LLM não retornou JSON válido.")
    return json.loads(limpo[inicio:fim])


def _parsear_conteudo(raw: dict, formato: FormatoSaida) -> ConteudoAdaptado:
    """Converte o dict cru do LLM no modelo Pydantic discriminado."""
    from app.models import ConteudoFlashcards, ConteudoMarkdown, ConteudoQuiz, QuizItem

    tipo_mapa = {
        "Flashcards": "flashcards",
        "Quiz": "quiz",
        "Tutorial": "markdown",
        "ResumoExecutivo": "markdown",
    }
    raw["tipo"] = tipo_mapa[formato]

    if raw["tipo"] == "flashcards":
        itens = [FlashcardItem(**i) for i in raw.get("itens", [])]
        return ConteudoFlashcards(
            titulo=raw["titulo"],
            introducao_contextualizada=raw["introducao_contextualizada"],
            itens=itens,
        )
    if raw["tipo"] == "quiz":
        itens = [QuizItem(**i) for i in raw.get("itens", [])]
        return ConteudoQuiz(
            titulo=raw["titulo"],
            introducao_contextualizada=raw["introducao_contextualizada"],
            itens=itens,
        )
    # markdown (Tutorial ou ResumoExecutivo)
    return ConteudoMarkdown(
        titulo=raw["titulo"],
        introducao_contextualizada=raw["introducao_contextualizada"],
        itens=raw["itens"],
    )


# ── Avaliação de qualidade simples ────────────────────────────────────────────


def _avaliar_qualidade(
    relevancia_media: float, conteudo_texto: str
) -> AvaliacaoQualidade:
    """Heurística básica; pode ser substituída por LLM-as-a-judge."""
    score = min(1.0, relevancia_media)
    if score >= 0.85:
        clareza = "Alta"
    elif score >= 0.65:
        clareza = "Media"
    else:
        clareza = "Baixa"
    return AvaliacaoQualidade(
        ancoragem_fonte_score=round(score, 4),
        clareza_pedagogica=clareza,
    )


# ── Pipeline principal ────────────────────────────────────────────────────────


def executar_pipeline(
    documento_id: str,
    titulo: str,
    texto: str,
    origem: OrigemDocumento,
    nome_arquivo: str | None,
    tamanho_bytes: int | None,
    perfil: PerfilDestinatario,
    formato: FormatoSaida,
    nicho: NichoSetor,
    nivel: NivelDetalhe,
    on_progresso: OnProgresso | None = None,
) -> AdaptacaoPacote:
    """Executa o pipeline completo e devolve o ``AdaptacaoPacote``.

    ``on_progresso(etapa, percentual, mensagem)`` é chamado a cada transição
    para que o worker atualize o job. Lança ``ValueError`` em erros de
    validação e ``RuntimeError`` em falhas de LLM.
    """

    def _prog(etapa: EtapaJob, pct: int, msg: str = "") -> None:
        if on_progresso:
            on_progresso(etapa, pct, msg)

    from app.rag import servico as rag_servico  # importação tardia

    # 1. Chunking + Embeddings via RAG ──────────────────────────────────────
    def _on_rag_etapa(etapa: str) -> None:
        if etapa == "chunking":
            _prog("chunking", 25, "Segmentando conteúdo...")
        elif etapa == "embeddings":
            _prog("embeddings", 45, "Gerando embeddings...")

    resultado_rag = rag_servico.indexar_documento(
        documento_id=documento_id,
        titulo=titulo,
        texto=texto,
        on_etapa=_on_rag_etapa,
    )

    # 2. Recuperação dos trechos mais relevantes ─────────────────────────────
    _prog("gerando", 55, "Recuperando trechos relevantes...")
    consulta = f"Conteúdo educacional sobre {titulo} para {perfil}"
    trechos = rag_servico.recuperar(documento_id=documento_id, consulta=consulta, k=6)
    relevancia_media = (
        sum(t.relevancia for t in trechos) / len(trechos) if trechos else 0.5
    )
    textos_trechos = [t.texto for t in trechos]

    # 3. Chamada ao LLM ──────────────────────────────────────────────────────
    _prog("gerando", 65, "Redigindo material didático...")
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=settings.google_api_key)
        model = genai.GenerativeModel(settings.modelo_llm)
        prompt = _montar_prompt(titulo, textos_trechos, perfil, formato, nicho, nivel)
        response = model.generate_content(prompt)
        resposta_texto = response.text
    except Exception as exc:
        logger.error("Falha na chamada ao LLM: %s", exc)
        raise RuntimeError(f"LLM indisponível: {exc}") from exc

    # 4. Parse do conteúdo gerado ────────────────────────────────────────────
    _prog("revisando", 82, "Revisando fidelidade...")
    raw = _extrair_json(resposta_texto)
    conteudo = _parsear_conteudo(raw, formato)

    # 5. Avaliação de qualidade ──────────────────────────────────────────────
    avaliacao = _avaliar_qualidade(relevancia_media, resposta_texto)

    # 6. Montar pacote ───────────────────────────────────────────────────────
    adaptacao_id = str(ULID())
    agora = datetime.now(timezone.utc).isoformat()

    # Estimativa de tempo de estudo
    _tempo_por_formato = {"Flashcards": 5, "Quiz": 8, "Tutorial": 12, "ResumoExecutivo": 4}
    tempo_estudo = _tempo_por_formato.get(formato, 5)

    # Conceitos-chave: primeiras palavras únicas do título + trechos (heurística)
    palavras = re.findall(r"\b[A-ZÀ-Ú][a-zA-ZÀ-ú]+\b", titulo + " " + " ".join(textos_trechos[:2]))
    conceitos = list(dict.fromkeys(palavras))[:8] or ["Conceito"]

    from app.services import oci as oci_service
    from app.models import ArmazenamentoOci

    obj_id = _objeto_id(titulo, perfil, formato, adaptacao_id)

    # Placeholder de OCI para montar o pacote completo antes do upload
    oci_placeholder = ArmazenamentoOci(
        bucket=settings.oci_bucket,
        objeto_id=obj_id,
        status_upload="falha",
    )

    pacote = AdaptacaoPacote(
        adaptacao_id=adaptacao_id,
        status="sucesso",
        criado_em=agora,
        documento=DocumentoRef(
            titulo=titulo,
            origem=origem,
            nome_arquivo=nome_arquivo,
            tamanho_bytes=tamanho_bytes,
        ),
        metadados=MetadadosAdaptacao(
            perfil_aplicado=perfil,
            formato_gerado=formato,
            nivel_detalhe_aplicado=nivel,
            tempo_estimado_estudo_minutos=tempo_estudo,
            conceitos_chave=conceitos,
        ),
        conteudo_adaptado=conteudo,
        avaliacao_qualidade=avaliacao,
        armazenamento_oci=oci_placeholder,
    )

    # Upload real para OCI com o pacote completo montado
    oci_result = oci_service.fazer_upload(pacote, obj_id)
    pacote = pacote.model_copy(update={"armazenamento_oci": oci_result})

    _prog("armazenando", 100, "Salvo no OCI.")
    return pacote
