"""Medição da geração multiagente (scripts/medir_geracao.py), sem rede."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import get_args

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.llm.erros import ErroAutenticacao, ErroIndisponivel, ErroLimiteTaxa
from app.models import ConteudoFlashcards, FlashcardItem, NichoSetor, NivelDetalhe

_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "medir_geracao.py"
_spec = importlib.util.spec_from_file_location("medir_geracao", _CAMINHO)
mg = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mg  # os dataclasses do script procuram o módulo aqui
_spec.loader.exec_module(mg)

CHAVE_FALSA = "nvapi-chave-falsa-da-medicao-geracao-123"


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setattr(settings, "grafo_limiar_ancoragem", 0.75)
    monkeypatch.setattr(settings, "grafo_max_revisoes", 2)
    monkeypatch.setattr(settings, "job_timeout_segundos", 300)
    monkeypatch.setattr(settings, "llm_timeout_segundos", 120)
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))


def _rodar(argv, tmp_path, **kw):
    return mg.main([*argv, "--intervalo", "0", "--recuperacao", "lexical"], pasta_relatorios=tmp_path, dormir=lambda _s: None, **kw)


def _json(tmp_path) -> dict:
    (arquivo,) = tmp_path.glob("medicao_geracao_*.json")
    return json.loads(arquivo.read_text(encoding="utf-8"))


def _m(formato="Flashcards", **campos):
    base = dict(documento="d.md", formato=formato, perfil="Desenvolvedor", repeticao=1, status=mg.OK,
                rodadas=1, motivo_parada="aprovado", ancoragem_rodada1=0.8, ancoragem_final=0.8,
                chamadas_total=1, chamadas_rodada1=1, duracao_total_s=10.0, duracao_rodada1_s=10.0,
                copia_rodada1=0.2, copia_final=0.2)
    base.update(campos)
    return mg.Medicao(**base)


def _revisado(ganho=0.1, copia=0.0, chamadas=2, tempo=20.0):
    return _m(rodadas=2, motivo_parada="aprovado", ancoragem_rodada1=0.6, ancoragem_final=0.6 + ganho,
              chamadas_total=chamadas, chamadas_rodada1=1, duracao_total_s=tempo, duracao_rodada1_s=10.0,
              copia_rodada1=0.2, copia_final=0.2 + copia)


# ── Plano e --listar ──────────────────────────────────────────────────────────


def test_plano_estima_chamadas_e_tempo():
    p = mg.plano(9, 2, 3.0)
    assert (p["combinacoes"], p["chamadas_min"], p["chamadas_max"]) == (9, 9, 54)
    assert p["minutos_min"] == pytest.approx(0.45) and p["minutos_max"] == pytest.approx(2.7)


def test_listar_mostra_o_plano_sem_chamar(tmp_path, capsys, ambiente):
    class NaoChama:
        def gerar(self, *_a, **_k):
            raise AssertionError("não deveria chamar")

    assert mg.main(["--listar", "--intervalo", "3"], provedor=NaoChama(), pasta_relatorios=tmp_path) == 0
    saida = capsys.readouterr().out
    total = len(mg.documentos_disponiveis()) * 3
    assert f"Combinações: {total}" in saida
    assert f"de {total} (todas aprovam na rodada 1) a {total * 6}" in saida
    assert "Embeddings:" in saida
    assert list(tmp_path.iterdir()) == []


# ── Simulado ──────────────────────────────────────────────────────────────────


def test_simulado_gera_relatorios_sem_chave_nem_texto(tmp_path, ambiente, capsys):
    assert _rodar(["--simulado"], tmp_path) == 0
    dados = _json(tmp_path)
    total = len(mg.documentos_disponiveis()) * len(mg.FORMATOS_PADRAO)
    assert len(dados["medicoes"]) == total
    assert dados["configuracao"]["recuperacao"] == "lexical"
    assert dados["configuracao"]["provedor"] == "simulado"
    total_agregado = dados["agregados"][-1]
    assert total_agregado["grupo"] == "total" and total_agregado["n"] == total
    assert total_agregado["revisados"] == len(mg.documentos_disponiveis()) * 2  # Flashcards e Tutorial
    assert total_agregado["aprovados_rodada1"] == pytest.approx(1 / 3)  # Quiz
    assert total_agregado["ganho_medio_revisados"] > 0
    assert dados["veredito"]["decisao"] in ("RECOMENDADO", "NÃO RECOMENDADO")
    (md,) = tmp_path.glob("medicao_geracao_*.md")
    texto = md.read_text(encoding="utf-8")
    assert "## Veredito sobre ligar o grafo por padrão" in texto
    assert "jobs aprovaram na rodada 1" in texto and mg.NOTA in texto
    conteudo = texto + json.dumps(dados, ensure_ascii=False)
    assert CHAVE_FALSA not in conteudo + capsys.readouterr().out
    for nome in mg.documentos_disponiveis():
        documento = (mg.EXEMPLOS / nome).read_text(encoding="utf-8")
        for frase in [f for f in documento.split(". ") if len(f) > 60][:5]:
            assert frase not in conteudo, frase  # nada do documento nem do conteúdo gerado


def test_filtros(tmp_path, ambiente):
    assert _rodar(["--simulado", "--documentos", "sql_consultas.md", "--formatos", "Quiz",
                   "--repeticoes", "2"], tmp_path) == 0
    medicoes = _json(tmp_path)["medicoes"]
    assert [(m["documento"], m["formato"], m["repeticao"]) for m in medicoes] == [
        ("sql_consultas.md", "Quiz", 1), ("sql_consultas.md", "Quiz", 2),
    ]


@pytest.mark.parametrize("argv", [["--formatos", "Poema"], ["--documentos", "nao.md"], ["--perfil", "Chefe"],
                                  ["--limiar", "1.5"], ["--max-revisoes", "3"], ["--repeticoes", "0"]])
def test_opcoes_invalidas(tmp_path, ambiente, argv):
    assert mg.main(argv, pasta_relatorios=tmp_path) == 2


def test_nivel_e_nicho_sao_validos():
    assert mg.NIVEL in get_args(NivelDetalhe) and mg.NICHO in get_args(NichoSetor)


# ── Chaves ────────────────────────────────────────────────────────────────────


def test_sem_chave_sai_com_codigo_2_sem_eco(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "nvidia")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(""))
    assert mg.main([], pasta_relatorios=tmp_path) == 2
    erro = capsys.readouterr().err
    assert "NVIDIA_NIM_API_KEY não definida" in erro and "Traceback" not in erro
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))
    monkeypatch.setattr(settings, "google_api_key", "")
    assert mg.main(["--recuperacao", "real"], pasta_relatorios=tmp_path) == 2
    erro = capsys.readouterr().err
    assert "GOOGLE_API_KEY não definida" in erro and CHAVE_FALSA not in erro
    assert list(tmp_path.iterdir()) == []


# ── Erros ─────────────────────────────────────────────────────────────────────


class _Roteiro(mg.ProvedorSimulado):
    """O simulado, com erros injetados pela ordem das chamadas ou pelo título do documento."""

    def __init__(self, erros=(), titulo_com_erro=None):
        self.erros = list(erros)
        self.titulo_com_erro = titulo_com_erro
        self.chamadas = 0

    def gerar(self, mensagens, *, timeout_segundos):
        self.chamadas += 1
        if self.titulo_com_erro and self.titulo_com_erro in mensagens[-1].conteudo:
            raise ErroIndisponivel("503")
        if self.erros:
            erro = self.erros.pop(0)
            if erro is not None:
                raise erro
        return super().gerar(mensagens, timeout_segundos=timeout_segundos)


def test_limite_de_taxa_repete_a_combinacao_uma_vez(tmp_path, ambiente):
    esperas = []
    provedor = _Roteiro([ErroLimiteTaxa("429")])
    assert mg.main(["--documentos", "sql_consultas.md", "--formatos", "Quiz", "--intervalo", "0", "--recuperacao", "lexical"],
                   provedor=provedor, pasta_relatorios=tmp_path, dormir=esperas.append) == 0
    (medicao,) = _json(tmp_path)["medicoes"]
    assert (medicao["status"], medicao["tentativas"]) == ("ok", 2)
    assert esperas == [mg.ESPERA_LIMITE_TAXA_S]


def test_limite_de_taxa_repetido_vira_erro(tmp_path, ambiente):
    provedor = _Roteiro([ErroLimiteTaxa("429"), ErroLimiteTaxa("429")])
    assert mg.main(["--documentos", "sql_consultas.md", "--formatos", "Quiz", "--intervalo", "0", "--recuperacao", "lexical"],
                   provedor=provedor, pasta_relatorios=tmp_path, dormir=lambda _s: None) == 0
    (medicao,) = _json(tmp_path)["medicoes"]
    assert (medicao["status"], medicao["tentativas"], medicao["erro"]) == ("falha", 2, "RuntimeError")


def test_erro_numa_combinacao_nao_derruba_as_outras(tmp_path, ambiente):
    sql = mg.carregar_documento(mg.EXEMPLOS / "sql_consultas.md")
    provedor = _Roteiro(titulo_com_erro=f"DOCUMENTO: {sql.titulo}")
    assert mg.main(["--documentos", "http_apis_rest.md,sql_consultas.md", "--formatos", "Quiz",
                    "--intervalo", "0", "--recuperacao", "lexical"], provedor=provedor, pasta_relatorios=tmp_path) == 0
    dados = _json(tmp_path)
    situacoes = {m["documento"]: (m["status"], m["erro"]) for m in dados["medicoes"]}
    assert situacoes == {"http_apis_rest.md": ("ok", None), "sql_consultas.md": ("falha", "RuntimeError")}
    assert dados["agregados"][-1]["erros"] == 1


def test_chave_recusada_interrompe_e_grava_parcial(tmp_path, ambiente):
    provedor = _Roteiro([None, ErroAutenticacao("401")])
    codigo = mg.main(["--documentos", "http_apis_rest.md", "--formatos", "Quiz,Flashcards,Tutorial",
                      "--intervalo", "0", "--recuperacao", "lexical"], provedor=provedor, pasta_relatorios=tmp_path)
    assert codigo == 1
    dados = _json(tmp_path)
    assert dados["interrompido"].startswith("chave ou configuração recusada")
    assert [m["formato"] for m in dados["medicoes"]] == ["Quiz"]


# ── Métricas e veredito ───────────────────────────────────────────────────────


def test_agregar_a_mao():
    medicoes = [
        _m(),  # aprovou na rodada 1
        _revisado(ganho=0.2, copia=0.05, chamadas=3, tempo=30.0),
        _revisado(ganho=-0.1, copia=0.0, chamadas=2, tempo=20.0),
        _m(status=mg.FALHA, erro="RuntimeError", rodadas=0, ancoragem_rodada1=None, ancoragem_final=None,
           chamadas_total=0, chamadas_rodada1=0, duracao_total_s=None, duracao_rodada1_s=None,
           copia_rodada1=None, copia_final=None, motivo_parada=None),
    ]
    a = mg.agregar(medicoes)
    assert (a.n, a.erros, a.revisados) == (3, 1, 2)
    assert a.aprovados_rodada1 == pytest.approx(1 / 3)
    assert a.ganho_medio_revisados == pytest.approx(0.05)
    assert a.melhorou_revisados == 0.5
    assert a.ancoragem_rodada1_revisados == pytest.approx(0.6)
    assert a.chamadas_medias == pytest.approx(2.0)
    assert a.chamadas_extras_medias == pytest.approx(1.0)
    assert (a.tempo_p50_s, a.tempo_p95_s) == (20.0, 30.0)
    assert a.tempo_extra_medio_s == pytest.approx(10.0)
    assert a.aumento_copia_revisados == pytest.approx(0.025)
    assert a.motivos == {"aprovado": 3}


def test_veredito_recomendado():
    total = mg.agregar([_revisado() for _ in range(5)] + [_m()])
    assert mg.veredito(total, prazo_s=300) == ("RECOMENDADO", [])


def test_veredito_inconclusivo_com_poucos_revisados():
    decisao, motivos = mg.veredito(mg.agregar([_revisado() for _ in range(4)]), prazo_s=300)
    assert decisao == "INCONCLUSIVO"
    assert motivos[0] == "só 4 job(s) revisado(s); o mínimo é 5"


def test_veredito_nao_recomendado_lista_os_motivos():
    medicoes = [_revisado(ganho=0.01, copia=0.2, chamadas=4, tempo=400.0) for _ in range(5)]
    medicoes.append(_m(status=mg.FALHA, erro="X"))
    decisao, motivos = mg.veredito(mg.agregar(medicoes), prazo_s=300)
    assert decisao == "NÃO RECOMENDADO"
    assert len(motivos) == 5
    assert any("cópia literal" in m for m in motivos) and any("p95" in m for m in motivos)


def test_percentil():
    assert mg.percentil([], 95) is None
    assert mg.percentil([3.0, 1.0, 2.0], 50) == 2.0
    assert mg.percentil([float(i) for i in range(1, 21)], 95) == 19.0


# ── Cópia literal e recuperação lexical ───────────────────────────────────────


def test_copia_literal():
    documento = "O protocolo HTTP troca mensagens entre um cliente e um servidor pela web toda hora."
    copiado = ConteudoFlashcards(
        titulo="T", introducao_contextualizada="Introdução sem relação nenhuma com o texto original aqui",
        itens=[FlashcardItem(frente="F", verso="O protocolo HTTP troca mensagens entre um cliente e um servidor")] * 3,
    )
    fracao = mg.copia_literal(copiado, documento)
    assert 0 < fracao < 1
    proprio = ConteudoFlashcards(titulo="T", introducao_contextualizada="Curta.",
                                 itens=[FlashcardItem(frente="F", verso="Texto inventado sem nada do documento original")] * 3)
    assert mg.copia_literal(proprio, documento) == 0.0
    curto = ConteudoFlashcards(titulo="T", introducao_contextualizada="Curta.",
                               itens=[FlashcardItem(frente="F", verso="Pouco.")] * 3)
    assert mg.copia_literal(curto, documento) is None
    assert mg.ngramas("Á b C d e f g h i") == mg.ngramas("a B c D e f g h i")


def test_recuperacao_lexical():
    texto = (mg.EXEMPLOS / "sql_consultas.md").read_text(encoding="utf-8")
    recuperar = mg.recuperacao_lexical(texto)
    trechos = recuperar(documento_id="d", consulta="LEFT JOIN clientes sem pedidos", k=6)
    assert 1 <= len(trechos) <= 6
    assert "LEFT JOIN" in trechos[0].texto
    assert trechos[0].relevancia == 1.0
    assert all(0.0 <= t.relevancia <= 1.0 for t in trechos)
    assert len({t.indice for t in trechos}) == len(trechos)


def test_recuperacao_real_com_embedding_falso_limpa_tudo(tmp_path, ambiente, monkeypatch):
    """RAG da geração num Chroma temporário, com embeddings falsos (sem rede)."""
    import hashlib
    import re

    from langchain_core.embeddings import Embeddings

    from app.rag import config, embeddings

    class Falso(Embeddings):
        def _vetor(self, texto):
            v = [0.0] * 32
            for palavra in re.findall(r"\w+", texto.lower()):
                v[int(hashlib.md5(palavra.encode()).hexdigest(), 16) % 32] += 1.0
            return v if any(v) else [1.0] + [0.0] * 31

        def embed_documents(self, texts, task_type=None, **_):
            return [self._vetor(t) for t in texts]

        def embed_query(self, text, task_type=None, **_):
            return self._vetor(text)

    embeddings.definir_embeddings(Falso())
    anterior = config.CHROMA_DIR
    pastas = []
    original_enter = mg.RecuperacaoReal.__enter__

    def enter(self):
        resultado = original_enter(self)
        pastas.append(self.pasta)
        return resultado

    monkeypatch.setattr(mg.RecuperacaoReal, "__enter__", enter)
    try:
        assert mg.main(["--documentos", "sql_consultas.md", "--formatos", "Flashcards,Quiz",
                        "--recuperacao", "real", "--intervalo", "0"],
                       provedor=mg.ProvedorSimulado(), pasta_relatorios=tmp_path) == 0
    finally:
        embeddings.definir_embeddings(None)
    dados = _json(tmp_path)
    assert dados["configuracao"]["recuperacao"] == "real"
    assert [m["status"] for m in dados["medicoes"]] == ["ok", "ok"]
    assert config.CHROMA_DIR == anterior  # restaurado
    assert pastas and not Path(pastas[0]).exists()  # o Chroma temporário foi apagado
