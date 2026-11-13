"""Um provedor registrado só no teste roda o pipeline inteiro, sem mudar o pipeline.

Indexa e recupera com o RAG de verdade (embedding falso e Chroma temporário),
gera com o provedor falso e monta o pacote, nos quatro formatos de saída.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.llm import Mensagem, registrar_provedor
from app.services.pipeline import executar_pipeline

TEXTO = "\n\n".join(
    [
        "O protocolo HTTP define métodos como GET, POST, PUT e DELETE para manipular recursos.",
        "Os códigos de status informam o resultado: 200 para sucesso e 404 para recurso não encontrado.",
    ]
    * 3
)

RESPOSTAS = {
    "Flashcards": {
        "tipo": "flashcards", "titulo": "Cartões", "introducao_contextualizada": "Intro.",
        "itens": [{"frente": f"F{i}", "verso": f"V{i}", "dica_didatica": None} for i in range(3)],
    },
    "Quiz": {
        "tipo": "quiz", "titulo": "Quiz", "introducao_contextualizada": "Intro.",
        "itens": [{"pergunta": "O que é 404?", "opcoes": ["Sucesso", "Não encontrado"],
                   "resposta_correta": 1, "explicacao": "404 é Not Found."}],
    },
    "Tutorial": {
        "tipo": "markdown", "titulo": "Tutorial", "introducao_contextualizada": "Intro.",
        "itens": "## Passo 1\n\nFaça a requisição GET e confira o código de status.",
    },
    "ResumoExecutivo": {
        "tipo": "markdown", "titulo": "Resumo", "introducao_contextualizada": "Intro.",
        "itens": "## Pontos-chave\n\n- HTTP usa métodos e códigos de status.",
    },
}
TIPOS = {"Flashcards": "flashcards", "Quiz": "quiz", "Tutorial": "markdown", "ResumoExecutivo": "markdown"}


class _ProvedorDeTeste:
    nome = "de-teste"
    recebidas: list[list[Mensagem]] = []
    formato = "Flashcards"

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str:
        _ProvedorDeTeste.recebidas.append(mensagens)
        return json.dumps(RESPOSTAS[_ProvedorDeTeste.formato])


@pytest.mark.usefixtures("embedding_falso", "chroma_temporario")
@pytest.mark.parametrize("formato", list(RESPOSTAS))
def test_provedor_registrado_no_teste_gera_os_quatro_formatos(monkeypatch, formato):
    _ProvedorDeTeste.recebidas = []
    _ProvedorDeTeste.formato = formato
    registrar_provedor("de-teste", _ProvedorDeTeste)
    monkeypatch.setattr(settings, "llm_provider", "de-teste")
    monkeypatch.setattr(settings, "oci_namespace", "")  # OCI em modo degradado, sem rede

    etapas = []
    pacote = executar_pipeline(
        documento_id=f"doc-troca-{formato.lower()}",
        titulo="Manual de HTTP",
        texto=TEXTO,
        origem="texto",
        nome_arquivo=None,
        tamanho_bytes=None,
        perfil="Desenvolvedor",
        formato=formato,
        nicho="Geral",
        nivel="Tecnico",
        on_progresso=lambda etapa, _pct, _msg: etapas.append(etapa),
    )

    assert pacote.conteudo_adaptado.tipo == TIPOS[formato]
    assert pacote.conteudo_adaptado.titulo == RESPOSTAS[formato]["titulo"]
    assert pacote.metadados.formato_gerado == formato
    assert etapas == ["chunking", "embeddings", "gerando", "gerando", "revisando", "armazenando"]
    assert len(_ProvedorDeTeste.recebidas) == 1
    (mensagem,) = _ProvedorDeTeste.recebidas[0]
    assert mensagem.papel == "user"
    assert "404" in mensagem.conteudo  # trecho recuperado do RAG chegou ao prompt
