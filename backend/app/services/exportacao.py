"""Exportação do pacote de adaptação em Markdown, HTML/PDF e CSV-Anki.

Funções puras, sem I/O de rede. No PDF, todo texto do pacote entra no HTML
escapado e o WeasyPrint não pode buscar nenhuma URL (``_bloquear_url``),
para que conteúdo gerado pelo LLM não provoque requisições de saída.
"""

from __future__ import annotations

import html

from app.models import AdaptacaoPacote

# ── Rótulos amigáveis (iguais aos do frontend) ───────────────────────────────

ROTULOS_PERFIL = {
    "Iniciante": "Iniciante / Transição de Carreira",
    "Desenvolvedor": "Desenvolvedor Júnior / Pleno",
    "LiderTecnico": "Líder Técnico / Arquiteto",
    "Gestor": "Gestor / Executivo (Não Técnico)",
}
ROTULOS_FORMATO = {
    "Flashcards": "Flashcards",
    "Quiz": "Quiz interativo",
    "Tutorial": "Tutorial",
    "ResumoExecutivo": "Resumo Executivo (TL;DR)",
}
ROTULOS_NIVEL = {"Didatico": "Didático", "Tecnico": "Técnico", "Executivo": "Executivo"}
ROTULOS_NICHO = {"Fintech": "Fintech", "Saude": "Saúde", "Ecommerce": "E-commerce", "Geral": "Geral"}


class DependenciasPdfAusentes(RuntimeError):
    """WeasyPrint ou markdown-it não instalados, ou bibliotecas do sistema ausentes."""


def _metadados(pacote: AdaptacaoPacote) -> list[str]:
    m = pacote.metadados
    return [
        ROTULOS_PERFIL.get(m.perfil_aplicado, m.perfil_aplicado),
        ROTULOS_FORMATO.get(m.formato_gerado, m.formato_gerado),
        ROTULOS_NIVEL.get(m.nivel_detalhe_aplicado, m.nivel_detalhe_aplicado),
        ROTULOS_NICHO.get(m.nicho_setor_aplicado, m.nicho_setor_aplicado),
        f"{m.tempo_estimado_estudo_minutos} min de estudo",
    ]


def _letra(indice: int) -> str:
    return chr(ord("A") + indice)


# ── Markdown ─────────────────────────────────────────────────────────────────


def gerar_markdown(pacote: AdaptacaoPacote) -> str:
    """Markdown do pacote, com uma linha de metadados abaixo do título."""
    conteudo = pacote.conteudo_adaptado
    blocos = [
        f"# {conteudo.titulo}",
        " · ".join(_metadados(pacote)),
        conteudo.introducao_contextualizada,
    ]

    if conteudo.tipo == "markdown":
        blocos.append(conteudo.itens)
    elif conteudo.tipo == "flashcards":
        for i, item in enumerate(conteudo.itens, 1):
            blocos.append(f"## Card {i}")
            blocos.append(f"**Frente:** {item.frente}")
            blocos.append(f"**Verso:** {item.verso}")
            if item.dica_didatica:
                blocos.append(f"> **Dica:** {item.dica_didatica}")
    else:  # quiz
        for i, item in enumerate(conteudo.itens, 1):
            blocos.append(f"## Questão {i}")
            blocos.append(item.pergunta)
            blocos.append(
                "\n".join(f"- **{_letra(j)})** {opcao}" for j, opcao in enumerate(item.opcoes))
            )
            if 0 <= item.resposta_correta < len(item.opcoes):
                blocos.append(f"**Resposta correta:** {_letra(item.resposta_correta)}")
            blocos.append(f"*{item.explicacao}*")

    return "\n\n".join(blocos) + "\n"


# ── HTML (usado só pelo PDF) ─────────────────────────────────────────────────

_FONTES = '"Inter", "DejaVu Sans", "Helvetica Neue", Arial, sans-serif'

CSS_PDF = """
@page {
  size: A4;
  margin: 20mm 19mm 22mm 19mm;
  @bottom-left { content: "NovaMente · material didático"; font: 7.5pt %(f)s; color: #8a8fa3; letter-spacing: .04em; }
  @bottom-right { content: "Página " counter(page) " de " counter(pages); font: 7.5pt %(f)s; color: #8a8fa3; }
}
@page :first { margin-top: 0; }
* { box-sizing: border-box; }
html { font-family: %(f)s; font-size: 9.6pt; line-height: 1.5; color: #1c1e2b; }
body { margin: 0; overflow-wrap: anywhere; }
.capa { margin: 0 -19mm 8mm -19mm; padding: 15mm 19mm 9mm 19mm; background: #0b0d14; color: #e8eaf2; border-bottom: 3px solid #8b5cf6; }
.marca { font-size: 8pt; font-weight: 700; letter-spacing: .28em; text-transform: uppercase; color: #a78bfa; margin: 0 0 7mm 0; }
.marca b { color: #e8eaf2; }
h1.titulo { font-size: 21pt; line-height: 1.18; font-weight: 700; margin: 0 0 5mm 0; color: #fff; letter-spacing: -.01em; }
.selos { margin: 0; }
.selo { display: inline-block; font-size: 7.4pt; font-weight: 600; padding: 1.1mm 2.6mm; margin: 0 1.6mm 1.6mm 0; border-radius: 10mm; background: rgba(139,92,246,.18); color: #d9ccff; border: .5pt solid rgba(167,139,250,.5); }
.intro { font-size: 10.4pt; line-height: 1.6; color: #3a3d50; margin: 0 0 7mm 0; padding-left: 4mm; border-left: 2.2pt solid #8b5cf6; }
.secao { font-size: 7.6pt; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; color: #7c3aed; margin: 0 0 3.5mm 0; }
.card { border: .6pt solid #e2def4; border-radius: 2.2mm; margin: 0 0 4.2mm 0; break-inside: avoid; overflow: hidden; background: #fff; }
.card .topo { background: #f6f4ff; padding: 1.6mm 4mm; border-bottom: .6pt solid #e2def4; font-size: 7.2pt; font-weight: 700; letter-spacing: .2em; color: #7c3aed; }
.card .topo span { float: right; color: #9a96b8; letter-spacing: .08em; }
.bloco { padding: 3mm 4mm; }
.rotulo { font-size: 6.8pt; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; color: #8b5cf6; margin: 0 0 1mm 0; }
.frente .texto { font-size: 10.4pt; font-weight: 700; color: #0b0d14; margin: 0; line-height: 1.4; }
.verso { background: #fbfaff; border-top: .6pt dashed #d6d0f0; }
.verso .texto { margin: 0; color: #2b2e40; }
.dica { margin: 0 4mm 3mm 4mm; padding: 2mm 3mm; background: #f1eeff; border-left: 2pt solid #8b5cf6; border-radius: 0 1.4mm 1.4mm 0; font-size: 8.6pt; color: #4c4570; }
.dica b { font-size: 6.8pt; letter-spacing: .2em; text-transform: uppercase; color: #7c3aed; margin-right: 1.5mm; }
.q .enun { font-size: 10.4pt; font-weight: 700; margin: 0 0 2.4mm 0; color: #0b0d14; }
.op { margin: 0 0 1.4mm 0; padding: 1.5mm 3mm 1.5mm 9mm; border: .6pt solid #e2def4; border-radius: 1.6mm; position: relative; }
.op .l { position: absolute; left: 3mm; top: 1.5mm; font-weight: 700; color: #7c3aed; }
.op.ok { background: #f1eeff; border-color: #8b5cf6; }
.op.ok .sel { float: right; font-size: 7pt; font-weight: 700; letter-spacing: .12em; color: #7c3aed; }
.expl { font-size: 8.6pt; color: #4c4570; margin: 2.2mm 0 0 0; }
.prosa h1 { display: none; }
.prosa h2 { font-size: 13pt; color: #0b0d14; margin: 7mm 0 2.5mm 0; padding-bottom: 1.4mm; border-bottom: .8pt solid #e2def4; break-after: avoid; }
.prosa h2::before { content: ""; display: inline-block; width: 2.2mm; height: 2.2mm; background: #8b5cf6; border-radius: .6mm; margin-right: 2.4mm; }
.prosa h3 { font-size: 10.6pt; color: #5b21b6; margin: 5mm 0 1.6mm 0; break-after: avoid; }
.prosa p { margin: 0 0 2.6mm 0; }
.prosa ul, .prosa ol { margin: 0 0 3mm 0; padding-left: 5mm; }
.prosa li { margin: 0 0 1.2mm 0; }
.prosa li::marker { color: #8b5cf6; }
.prosa code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.4pt; background: #f1eeff; color: #5b21b6; padding: .2mm 1.2mm; border-radius: .8mm; }
.prosa pre { background: #0b0d14; color: #e8eaf2; padding: 3mm 4mm; border-radius: 2mm; break-inside: avoid; font-size: 8pt; white-space: pre-wrap; }
.prosa pre code { background: none; color: inherit; padding: 0; }
.prosa blockquote { margin: 0 0 3mm 0; padding: 1.6mm 3.5mm; background: #f1eeff; border-left: 2pt solid #8b5cf6; color: #4c4570; }
.prosa strong { color: #0b0d14; }
""" % {"f": _FONTES}


def _markdown_seguro():
    """Renderizador CommonMark sem HTML cru e sem imagens (que virariam URLs)."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark", {"html": False}).disable("image")


def _capa(pacote: AdaptacaoPacote) -> str:
    conteudo = pacote.conteudo_adaptado
    e = html.escape
    selos = "".join(f'<span class="selo">{e(s)}</span>' for s in _metadados(pacote))
    return (
        '<header class="capa"><p class="marca"><b>Nova</b>Mente</p>'
        f'<h1 class="titulo">{e(conteudo.titulo)}</h1>'
        f'<p class="selos">{selos}</p></header>'
        f'<p class="intro">{e(conteudo.introducao_contextualizada)}</p>'
    )


def _corpo(pacote: AdaptacaoPacote) -> str:
    conteudo = pacote.conteudo_adaptado
    e = html.escape
    partes: list[str] = []

    if conteudo.tipo == "flashcards":
        total = len(conteudo.itens)
        partes.append(f'<p class="secao">Flashcards · {total} cartões</p>')
        for i, item in enumerate(conteudo.itens, 1):
            dica = (
                f'<div class="dica"><b>Dica</b>{e(item.dica_didatica)}</div>'
                if item.dica_didatica
                else ""
            )
            partes.append(
                f'<section class="card"><div class="topo">CARTÃO {i:02d}<span>{i} / {total}</span></div>'
                f'<div class="bloco frente"><p class="rotulo">Frente</p><p class="texto">{e(item.frente)}</p></div>'
                f'<div class="bloco verso"><p class="rotulo">Verso</p><p class="texto">{e(item.verso)}</p></div>'
                f"{dica}</section>"
            )
    elif conteudo.tipo == "quiz":
        partes.append(f'<p class="secao">Quiz · {len(conteudo.itens)} questões</p>')
        for i, item in enumerate(conteudo.itens, 1):
            opcoes = []
            for j, opcao in enumerate(item.opcoes):
                correta = j == item.resposta_correta
                opcoes.append(
                    f'<div class="op{" ok" if correta else ""}"><span class="l">{_letra(j)}</span>'
                    f"{e(opcao)}"
                    f'{"<span class=sel>✓ CORRETA</span>" if correta else ""}</div>'
                )
            partes.append(
                f'<section class="card"><div class="topo">QUESTÃO {i:02d}</div>'
                f'<div class="bloco q"><p class="enun">{e(item.pergunta)}</p>{"".join(opcoes)}'
                f'<p class="expl"><b>Explicação.</b> {e(item.explicacao)}</p></div></section>'
            )
    else:  # Tutorial e Resumo Executivo
        partes.append(f'<div class="prosa">{_markdown_seguro().render(conteudo.itens)}</div>')

    return "".join(partes)


def gerar_html(pacote: AdaptacaoPacote) -> str:
    """HTML completo, com CSS embutido, usado como entrada do PDF."""
    return (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{html.escape(pacote.conteudo_adaptado.titulo)}</title>"
        f"<style>{CSS_PDF}</style></head>"
        f"<body>{_capa(pacote)}{_corpo(pacote)}</body></html>"
    )


# ── PDF ──────────────────────────────────────────────────────────────────────


def _bloquear_url(url: str, *args, **kwargs):
    """``url_fetcher`` do WeasyPrint que recusa qualquer URL (http, https, file, ftp...)."""
    raise ValueError(f"Acesso a recurso externo bloqueado na exportação: {url}")


def gerar_pdf(pacote: AdaptacaoPacote) -> bytes:
    """PDF A4 do pacote. Levanta DependenciasPdfAusentes se o WeasyPrint não carregar."""
    try:
        import markdown_it  # noqa: F401
        import weasyprint
    except (ImportError, OSError) as exc:
        # OSError: o pacote está instalado, mas faltam bibliotecas do sistema (pango).
        raise DependenciasPdfAusentes("Dependências de PDF não instaladas.") from exc

    documento = weasyprint.HTML(string=gerar_html(pacote), url_fetcher=_bloquear_url)
    return documento.write_pdf()


# ── CSV-Anki ─────────────────────────────────────────────────────────────────


def gerar_csv(pacote: AdaptacaoPacote) -> bytes:
    """CSV (separador ';') com frente, verso e dica. Só para Flashcards."""
    conteudo = pacote.conteudo_adaptado
    linhas = ["frente;verso;dica"]
    for item in conteudo.itens:
        dica = item.dica_didatica or ""
        linhas.append(
            f'"{item.frente.replace(chr(34), chr(34)*2)}";'
            f'"{item.verso.replace(chr(34), chr(34)*2)}";'
            f'"{dica.replace(chr(34), chr(34)*2)}"'
        )
    return "\n".join(linhas).encode("utf-8")
