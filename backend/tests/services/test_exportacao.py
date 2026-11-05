"""Testes da exportação em Markdown, HTML/PDF e CSV-Anki (issue #47)."""

from __future__ import annotations

import io
import re

import pytest
from fastapi.testclient import TestClient
from markdown_it import MarkdownIt

from app.main import app
from app.models import (
    AdaptacaoPacote,
    ArmazenamentoOci,
    AvaliacaoQualidade,
    ConteudoFlashcards,
    ConteudoMarkdown,
    ConteudoQuiz,
    DocumentoRef,
    FlashcardItem,
    MetadadosAdaptacao,
    QuizItem,
)
from app.services import exportacao, repositorio

client = TestClient(app)

MALICIOSO = '<script>alert(1)</script> <img src="http://exemplo.invalido/x.png"> P&D'


def _pacote(conteudo, formato="Flashcards", adaptacao_id="EXP_TESTE") -> AdaptacaoPacote:
    return AdaptacaoPacote(
        adaptacao_id=adaptacao_id,
        criado_em="2026-11-05T12:00:00+00:00",
        documento=DocumentoRef(titulo="Manual de HTTP", origem="texto"),
        metadados=MetadadosAdaptacao(
            perfil_aplicado="LiderTecnico",
            formato_gerado=formato,
            nivel_detalhe_aplicado="Didatico",
            nicho_setor_aplicado="Saude",
            tempo_estimado_estudo_minutos=12,
            conceitos_chave=["HTTP"],
        ),
        conteudo_adaptado=conteudo,
        avaliacao_qualidade=AvaliacaoQualidade(ancoragem_fonte_score=0.9, clareza_pedagogica="Alta"),
        armazenamento_oci=ArmazenamentoOci(
            bucket="teste", objeto_id=f"novamente-{adaptacao_id.lower()}.json", status_upload="falha"
        ),
    )


def _flashcards(frente_extra: str = "", **kw) -> AdaptacaoPacote:
    return _pacote(
        ConteudoFlashcards(
            titulo="Fundamentos de HTTP",
            introducao_contextualizada="Revisão rápida dos conceitos de HTTP.",
            itens=[
                FlashcardItem(frente=f"O que é GET?{frente_extra}", verso="Busca um recurso.", dica_didatica="Pense em leitura."),
                FlashcardItem(frente='O que é "POST"?', verso="Cria um recurso.", dica_didatica=None),
                FlashcardItem(frente="O que é 404?", verso="Recurso não encontrado.", dica_didatica="Erro do cliente."),
            ],
        ),
        **kw,
    )


def _quiz(**kw) -> AdaptacaoPacote:
    return _pacote(
        ConteudoQuiz(
            titulo="Quiz de HTTP",
            introducao_contextualizada="Teste seus conhecimentos.",
            itens=[
                QuizItem(
                    pergunta="Qual código indica recurso não encontrado?",
                    opcoes=["200", "404", "500", "301"],
                    resposta_correta=1,
                    explicacao="404 é Not Found.",
                ),
                QuizItem(
                    pergunta="Qual método cria um recurso?",
                    opcoes=["GET", "DELETE", "POST", "HEAD"],
                    resposta_correta=2,
                    explicacao="POST cria recursos.",
                ),
            ],
        ),
        formato="Quiz",
        **kw,
    )


def _tutorial(itens: str, **kw) -> AdaptacaoPacote:
    return _pacote(
        ConteudoMarkdown(
            titulo="Tutorial de HTTP",
            introducao_contextualizada="Passo a passo.",
            itens=itens,
        ),
        formato="Tutorial",
        **kw,
    )


def _weasyprint():
    # O pacote pode estar instalado sem as bibliotecas do sistema (OSError).
    try:
        return pytest.importorskip("weasyprint")
    except OSError as exc:
        pytest.skip(f"WeasyPrint sem bibliotecas do sistema: {exc}")


def _texto_pdf(dados: bytes) -> str:
    """Texto extraído sem nenhum espaço em branco.

    Com letter-spacing, o pypdf pode devolver "F R E N T E"; sem espaços, os
    asserts valem para qualquer fonte.
    """
    from pypdf import PdfReader

    texto = "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(dados)).pages)
    return re.sub(r"\s+", "", texto)


# ── Markdown ──────────────────────────────────────────────────────────────────


def test_markdown_flashcards_frente_e_verso_em_paragrafos_diferentes():
    md = exportacao.gerar_markdown(_flashcards())
    html = MarkdownIt("commonmark").render(md)
    assert "<p><strong>Frente:</strong> O que é GET?</p>" in html
    assert "<p><strong>Verso:</strong> Busca um recurso.</p>" in html
    assert "<blockquote>\n<p><strong>Dica:</strong> Pense em leitura.</p>\n</blockquote>" in html
    assert "## Card 1\n\n**Frente:** O que é GET?\n\n**Verso:** Busca um recurso." in md


def test_markdown_tem_linha_de_metadados_com_rotulos_amigaveis():
    linhas = exportacao.gerar_markdown(_flashcards()).splitlines()
    assert linhas[0] == "# Fundamentos de HTTP"
    assert linhas[2] == (
        "Líder Técnico / Arquiteto · Flashcards · Didático · Saúde · 12 min de estudo"
    )


def test_markdown_quiz_alternativas_em_lista_com_resposta():
    md = exportacao.gerar_markdown(_quiz())
    html = MarkdownIt("commonmark").render(md)
    assert "<li><strong>A)</strong> 200</li>" in html
    assert "<li><strong>B)</strong> 404</li>" in html
    assert html.count("<li>") == 8
    assert "**Resposta correta:** B" in md
    assert "**Resposta correta:** C" in md
    assert "*404 é Not Found.*" in md
    assert "Quiz interativo" in md


def test_markdown_tutorial_mantem_conteudo():
    itens = "## Passo 1\n\nInstale o cliente HTTP.\n\n## Passo 2\n\nFaça a requisição."
    md = exportacao.gerar_markdown(_tutorial(itens))
    assert md.startswith("# Tutorial de HTTP\n\n")
    assert md.rstrip().endswith(itens)


# ── HTML ──────────────────────────────────────────────────────────────────────


def test_html_escapa_conteudo_do_pacote():
    html = exportacao.gerar_html(_flashcards(frente_extra=MALICIOSO))
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=&quot;http://exemplo.invalido/x.png&quot;&gt;" in html
    assert "P&amp;D" in html


def test_html_tutorial_nao_deixa_html_cru_nem_imagem():
    itens = f"## Passo\n\n{MALICIOSO}\n\n![logo](http://exemplo.invalido/logo.png)"
    html = exportacao.gerar_html(_tutorial(itens))
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html


def test_html_selos_usam_rotulos_amigaveis():
    html = exportacao.gerar_html(_quiz())
    for rotulo in [
        "Líder Técnico / Arquiteto",
        "Quiz interativo",
        "Didático",
        "Saúde",
        "12 min de estudo",
    ]:
        assert f'<span class="selo">{rotulo}</span>' in html
    assert "✓ CORRETA" in html


def test_bloquear_url_recusa_qualquer_esquema():
    for url in ["http://a.b/x", "https://a.b/x", "file:///etc/passwd", "ftp://a.b/x"]:
        with pytest.raises(ValueError):
            exportacao._bloquear_url(url)


# ── PDF ───────────────────────────────────────────────────────────────────────


def test_pdf_flashcards_tem_frente_verso_e_titulo():
    _weasyprint()
    dados = exportacao.gerar_pdf(_flashcards())
    assert dados.startswith(b"%PDF")
    texto = _texto_pdf(dados)
    assert "FRENTE" in texto
    assert "VERSO" in texto
    assert "FundamentosdeHTTP" in texto
    assert "Página1de" in texto


def test_pdf_url_longa_sem_espaco_nao_e_cortada():
    _weasyprint()
    url = "https://exemplo.invalido/" + "a1b2c3d4" * 25
    url = url[:200]
    pacote = _flashcards()
    pacote.conteudo_adaptado.itens[0].verso = f"Veja {url} para detalhes."
    texto = _texto_pdf(exportacao.gerar_pdf(pacote))
    assert len(url) == 200
    assert url in texto


@pytest.mark.parametrize("gerar", ["flashcards", "tutorial"])
def test_pdf_nao_busca_urls_de_conteudo_malicioso(gerar, monkeypatch):
    _weasyprint()
    chamadas = []

    def espiao(url, *args, **kwargs):
        chamadas.append(url)
        raise ValueError("bloqueado")

    monkeypatch.setattr(exportacao, "_bloquear_url", espiao)
    if gerar == "flashcards":
        pacote = _flashcards(frente_extra=MALICIOSO)
    else:
        pacote = _tutorial(f"## Passo\n\n{MALICIOSO}\n\n![logo](http://exemplo.invalido/logo.png)")
    texto = _texto_pdf(exportacao.gerar_pdf(pacote))
    assert chamadas == []
    assert "<script>" in texto  # a tag aparece como texto, não é interpretada


# ── Contrato da rota ──────────────────────────────────────────────────────────


@pytest.fixture
def salvar():
    salvos = []

    def _salvar(pacote):
        repositorio.salvar_pacote(pacote)
        salvos.append(pacote.adaptacao_id)
        return pacote

    yield _salvar
    for adaptacao_id in salvos:
        repositorio._pacotes.pop(adaptacao_id, None)


def test_rota_formato_desconhecido():
    resp = client.get("/api/v1/adaptacoes/EXP_QUALQUER/exportacao?formato=xml")
    assert resp.status_code == 400
    assert resp.json()["erro"]["codigo"] == "FORMATO_DESCONHECIDO"


def test_rota_adaptacao_nao_encontrada():
    resp = client.get("/api/v1/adaptacoes/EXP_NAO_EXISTE/exportacao?formato=md")
    assert resp.status_code == 404
    assert resp.json()["erro"]["codigo"] == "ADAPTACAO_NAO_ENCONTRADA"


def test_rota_csv_de_quiz_e_incompativel(salvar):
    salvar(_quiz(adaptacao_id="EXP_QUIZ_CSV"))
    resp = client.get("/api/v1/adaptacoes/EXP_QUIZ_CSV/exportacao?formato=csv")
    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "FORMATO_INCOMPATIVEL"


def test_rota_csv_de_flashcards_igual_ao_anterior(salvar):
    salvar(_flashcards(adaptacao_id="EXP_FLASH_CSV"))
    resp = client.get("/api/v1/adaptacoes/EXP_FLASH_CSV/exportacao?formato=csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    assert resp.headers["content-disposition"] == 'attachment; filename="novamente-exp_flash_csv.csv"'
    esperado = (
        "frente;verso;dica\n"
        '"O que é GET?";"Busca um recurso.";"Pense em leitura."\n'
        '"O que é ""POST""?";"Cria um recurso.";""\n'
        '"O que é 404?";"Recurso não encontrado.";"Erro do cliente."'
    )
    assert resp.content == esperado.encode("utf-8")


def test_rota_md_usa_o_novo_markdown(salvar):
    pacote = salvar(_flashcards(adaptacao_id="EXP_FLASH_MD"))
    resp = client.get("/api/v1/adaptacoes/EXP_FLASH_MD/exportacao?formato=md")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    assert resp.headers["content-disposition"] == 'attachment; filename="novamente-exp_flash_md.md"'
    assert resp.content.decode("utf-8") == exportacao.gerar_markdown(pacote)


def test_rota_pdf_sem_dependencias_responde_501(salvar, monkeypatch):
    salvar(_flashcards(adaptacao_id="EXP_FLASH_501"))

    def sem_dependencias(_pacote):
        raise exportacao.DependenciasPdfAusentes("Dependências de PDF não instaladas.")

    monkeypatch.setattr("app.api.v1.routers.adaptacoes.gerar_pdf", sem_dependencias)
    resp = client.get("/api/v1/adaptacoes/EXP_FLASH_501/exportacao?formato=pdf")
    assert resp.status_code == 501
    assert resp.json()["erro"]["codigo"] == "INTERNO"


def test_rota_pdf_responde_pdf(salvar):
    _weasyprint()
    salvar(_quiz(adaptacao_id="EXP_QUIZ_PDF"))
    resp = client.get("/api/v1/adaptacoes/EXP_QUIZ_PDF/exportacao?formato=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == 'attachment; filename="novamente-exp_quiz_pdf.pdf"'
    assert resp.content.startswith(b"%PDF")
