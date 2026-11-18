"""Funções do comparador de modelos (scripts/comparar_modelos.py), com provedor falso.

O script em si não roda no pytest: aqui só a medição com o pipeline real e
um provedor que não acessa a rede, a agregação, o relatório e a linha de
comando com o provedor injetado.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.llm import (
    ErroAutenticacao,
    ErroLimiteTaxa,
    ErroModeloIndisponivel,
    ErroRequisicaoRecusada,
    ErroRespostaInvalida,
)

_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "comparar_modelos.py"
_spec = importlib.util.spec_from_file_location("comparar_modelos", _CAMINHO)
cm = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cm  # os dataclasses do script procuram o módulo aqui
_spec.loader.exec_module(cm)

DOCUMENTO = cm.carregar_documento(cm.EXEMPLOS / "http_apis_rest.md")
SQL = cm.carregar_documento(cm.EXEMPLOS / "sql_consultas.md")

FLASHCARDS = json.dumps({
    "tipo": "flashcards",
    "titulo": "Métodos do protocolo HTTP",
    "introducao_contextualizada": "O protocolo HTTP troca mensagens entre cliente e servidor.",
    "itens": [
        {"frente": "GET", "verso": "Busca um recurso sem alterá-lo.", "dica_didatica": None},
        {"frente": "POST", "verso": "Cria um recurso novo.", "dica_didatica": None},
        {"frente": "DELETE", "verso": "Remove o recurso.", "dica_didatica": None},
    ],
})


class _Cortada(ErroRespostaInvalida):
    """Imita o provedor NVIDIA com finish_reason "length"."""


class _ProvedorFalso:
    """Devolve, em ordem, os itens do roteiro (texto ou exceção); o último se repete."""

    nome = "falso"

    def __init__(self, roteiro, disponivel=True, tokens=100, catalogo=()):
        self.roteiro = list(roteiro)
        self.disponivel = disponivel
        self.tokens = tokens
        self.catalogo = catalogo if isinstance(catalogo, BaseException) else list(catalogo)
        self.ultimo_uso = None
        self.ultimo_motivo_fim = None
        self.chamadas = 0

    def modelo_disponivel(self):
        if isinstance(self.disponivel, BaseException):
            raise self.disponivel
        return self.disponivel

    def listar_modelos(self):
        if isinstance(self.catalogo, BaseException):
            raise self.catalogo
        return sorted(self.catalogo)

    def gerar(self, mensagens, *, timeout_segundos):
        self.chamadas += 1
        item = self.roteiro[min(self.chamadas, len(self.roteiro)) - 1]
        self.ultimo_motivo_fim = "length" if isinstance(item, _Cortada) else "stop"
        if isinstance(item, BaseException):
            raise item
        self.ultimo_uso = {"total_tokens": self.tokens} if self.tokens is not None else None
        return item


class _Relogio:
    def __init__(self):
        self.agora = 0.0
        self.esperas = []

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.agora += segundos


@pytest.fixture
def relogio():
    return _Relogio()


def _ritmo(relogio, intervalo=0.0):
    return cm.Ritmo(intervalo, dormir=relogio.dormir, relogio=relogio)


def _medir(provedor, relogio, formato="Flashcards", raciocinio="padrao"):
    medido = cm.ProvedorMedido(provedor, _ritmo(relogio), relogio=relogio)
    return cm.medir_geracao(medido, "org/modelo", raciocinio, DOCUMENTO, formato)


def _comparar(provedores, relogio, variantes=("padrao",), documentos=(DOCUMENTO, SQL),
              formatos=("Flashcards", "Tutorial"), avisos=None):
    """``provedores``: {modelo: provedor} ou {(modelo, variante): provedor}."""

    def criar(modelo, variante):
        return provedores.get((modelo, variante)) or provedores[modelo]

    modelos = list(dict.fromkeys(m if isinstance(m, str) else m[0] for m in provedores))
    return cm.comparar(modelos, list(variantes), list(documentos), list(formatos), criar,
                       _ritmo(relogio), avisar=(avisos.append if avisos is not None else lambda _m: None))


# ── Documentos ────────────────────────────────────────────────────────────────


def test_carrega_documento_com_titulo_da_primeira_linha():
    assert DOCUMENTO.nome == "http_apis_rest.md"
    assert DOCUMENTO.titulo == "Introdução a APIs REST com HTTP"
    assert 1 <= len(cm.trechos_do_documento(DOCUMENTO)) <= cm.TRECHOS_NO_PROMPT


def test_documentos_padrao_existem():
    for nome in cm.DOCUMENTOS_PADRAO:
        assert (cm.EXEMPLOS / nome).is_file()


# ── Medição de uma geração ────────────────────────────────────────────────────


def test_geracao_valida_na_primeira_resposta(relogio):
    medicao = _medir(_ProvedorFalso([FLASHCARDS]), relogio, raciocinio="desligado")
    assert medicao.status == cm.OK
    assert medicao.raciocinio == "desligado"
    assert medicao.json_valido_primeira is True
    assert medicao.cortada is False
    assert medicao.chamadas == 1
    assert 0.5 < medicao.ancoragem <= 1.0  # conteúdo tirado do documento
    assert medicao.clareza in {"Alta", "Media", "Baixa"}
    assert medicao.tokens == 100
    assert medicao.erro is None


def test_prompt_e_o_do_pipeline(relogio):
    recebidos = []

    class _Espiao(_ProvedorFalso):
        def gerar(self, mensagens, *, timeout_segundos):
            recebidos.append((mensagens, timeout_segundos))
            return super().gerar(mensagens, timeout_segundos=timeout_segundos)

    _medir(_Espiao([FLASHCARDS]), relogio)
    ((mensagens, timeout),) = recebidos
    esperado = cm.pipeline._montar_prompt(
        DOCUMENTO.titulo, cm.trechos_do_documento(DOCUMENTO), cm.PERFIL, "Flashcards", cm.NICHO, cm.NIVEL
    )
    assert [m.conteudo for m in mensagens] == [esperado]
    assert timeout == settings.llm_timeout_segundos


def test_json_invalido_depois_valido_nao_conta_como_valido_na_primeira(relogio):
    medicao = _medir(_ProvedorFalso(["isto não é json", FLASHCARDS]), relogio)
    assert medicao.status == cm.OK
    assert medicao.json_valido_primeira is False
    assert medicao.chamadas == 2
    assert medicao.tokens == 200


def test_resposta_vazia_depois_valida_nao_aparece_como_erro(relogio):
    medicao = _medir(_ProvedorFalso([ErroRespostaInvalida("vazia"), FLASHCARDS]), relogio)
    assert medicao.status == cm.OK
    assert medicao.erro is None


def test_json_invalido_nas_duas_tentativas_e_falha(relogio):
    medicao = _medir(_ProvedorFalso(["{quebrado", "nada"]), relogio)
    assert medicao.status == cm.FALHA
    assert medicao.erro == "RespostaInvalida"
    assert medicao.ancoragem is None
    assert medicao.chamadas == 2


def test_resposta_cortada_conta_como_cortada(relogio):
    cortada_e_depois_ok = _medir(_ProvedorFalso([_Cortada("length"), FLASHCARDS]), relogio)
    assert (cortada_e_depois_ok.status, cortada_e_depois_ok.cortada) == (cm.OK, True)
    assert cortada_e_depois_ok.json_valido_primeira is False
    sempre_cortada = _medir(_ProvedorFalso([_Cortada("length")]), relogio)
    assert (sempre_cortada.status, sempre_cortada.cortada, sempre_cortada.erro) == (
        cm.FALHA, True, "_Cortada",
    )


def test_erro_do_provedor_vira_falha_com_o_tipo(relogio):
    medicao = _medir(_ProvedorFalso([ErroLimiteTaxa("429")]), relogio)
    assert (medicao.status, medicao.erro, medicao.chamadas) == (cm.FALHA, "ErroLimiteTaxa", 1)


def test_modelo_404_fica_indisponivel(relogio):
    medicao = _medir(_ProvedorFalso([ErroModeloIndisponivel("404")]), relogio)
    assert (medicao.status, medicao.erro) == (cm.INDISPONIVEL, "ErroModeloIndisponivel")


def test_variante_recusada_fica_nao_suportada(relogio):
    medicao = _medir(_ProvedorFalso([ErroRequisicaoRecusada("400")]), relogio, raciocinio="ligado")
    assert (medicao.status, medicao.erro) == (cm.NAO_SUPORTADO, "ErroRequisicaoRecusada")


def test_chave_recusada_na_geracao_sobe(relogio):
    with pytest.raises(ErroAutenticacao):
        _medir(_ProvedorFalso([ErroAutenticacao("HTTP 401")]), relogio)


def test_sem_usage_os_tokens_ficam_vazios(relogio):
    assert _medir(_ProvedorFalso([FLASHCARDS], tokens=None), relogio).tokens is None


def test_latencia_e_medida_por_chamada(relogio):
    class _Lento(_ProvedorFalso):
        def gerar(self, mensagens, *, timeout_segundos):
            relogio.agora += 2.5
            return super().gerar(mensagens, timeout_segundos=timeout_segundos)

    assert _medir(_Lento([FLASHCARDS]), relogio).latencia_s == pytest.approx(2.5)


# ── Ritmo ─────────────────────────────────────────────────────────────────────


def test_ritmo_respeita_o_intervalo_entre_requisicoes(relogio):
    ritmo = _ritmo(relogio, intervalo=1.6)
    medido = cm.ProvedorMedido(_ProvedorFalso([FLASHCARDS]), ritmo, relogio=relogio)
    for _ in range(3):
        cm.medir_geracao(medido, "m", "padrao", DOCUMENTO, "Flashcards")
    assert relogio.esperas == [pytest.approx(1.6), pytest.approx(1.6)]


# ── Comparação de vários modelos ──────────────────────────────────────────────


def test_comparar_marca_indisponivel_e_segue_para_o_proximo(relogio):
    provedores = {
        "fora/catalogo": _ProvedorFalso([FLASHCARDS], disponivel=False),
        "some/404": _ProvedorFalso([ErroModeloIndisponivel("404")]),
        "bom/modelo": _ProvedorFalso([FLASHCARDS]),
        "catalogo/fora-do-ar": _ProvedorFalso([FLASHCARDS], disponivel=ErroLimiteTaxa("429")),
    }
    avisos = []
    medicoes = _comparar(provedores, relogio, avisos=avisos)
    por_modelo = {m: [x for x in medicoes if x.modelo == m] for m in provedores}
    assert [x.status for x in por_modelo["fora/catalogo"]] == [cm.INDISPONIVEL]
    assert provedores["fora/catalogo"].chamadas == 0
    assert [x.status for x in por_modelo["some/404"]] == [cm.INDISPONIVEL]  # parou no primeiro 404
    assert len(por_modelo["bom/modelo"]) == 4  # 2 documentos x 2 formatos
    assert len(por_modelo["catalogo/fora-do-ar"]) == 4  # catálogo inacessível: tenta gerar mesmo assim
    assert avisos == medicoes


def test_comparar_mede_cada_variante_de_raciocinio(relogio):
    provedores = {
        ("m", "padrao"): _ProvedorFalso([FLASHCARDS]),
        ("m", "desligado"): _ProvedorFalso([FLASHCARDS]),
        ("m", "ligado"): _ProvedorFalso([FLASHCARDS]),
    }
    medicoes = _comparar(provedores, relogio, variantes=("padrao", "desligado", "ligado"))
    assert [(x.raciocinio, x.documento, x.formato) for x in medicoes] == [
        (v, d, f) for v in ("padrao", "desligado", "ligado")
        for d in ("http_apis_rest.md", "sql_consultas.md") for f in ("Flashcards", "Tutorial")
    ]
    # Flashcards vale na 1ª; Tutorial recebe JSON de flashcards (inválido) e tenta 2 vezes.
    assert all(p.chamadas == 2 * 1 + 2 * 2 for p in provedores.values())


def test_variante_nao_suportada_pula_o_resto_dela_e_segue(relogio):
    provedores = {
        ("m", "padrao"): _ProvedorFalso([FLASHCARDS]),
        ("m", "ligado"): _ProvedorFalso([ErroRequisicaoRecusada("HTTP 400")]),
        ("m", "desligado"): _ProvedorFalso([FLASHCARDS]),
        "outro": _ProvedorFalso([FLASHCARDS]),
    }
    medicoes = _comparar(provedores, relogio, variantes=("padrao", "ligado", "desligado"))
    ligado = [x for x in medicoes if x.modelo == "m" and x.raciocinio == "ligado"]
    assert [x.status for x in ligado] == [cm.NAO_SUPORTADO]  # parou na primeira recusa
    assert provedores[("m", "ligado")].chamadas == 1
    assert len([x for x in medicoes if x.modelo == "m" and x.raciocinio == "desligado"]) == 4
    assert len([x for x in medicoes if x.modelo == "outro"]) == 12


def test_404_numa_variante_pula_as_outras_do_modelo(relogio):
    provedores = {"m": _ProvedorFalso([ErroModeloIndisponivel("404")]), "outro": _ProvedorFalso([FLASHCARDS])}
    medicoes = _comparar(provedores, relogio, variantes=("padrao", "ligado"))
    assert [(x.modelo, x.raciocinio, x.status) for x in medicoes if x.modelo == "m"] == [
        ("m", "padrao", cm.INDISPONIVEL)
    ]
    assert len([x for x in medicoes if x.modelo == "outro"]) == 8


def test_chave_recusada_interrompe_com_o_que_ja_foi_medido(relogio):
    provedores = {
        "primeiro": _ProvedorFalso([FLASHCARDS]),
        "segundo": _ProvedorFalso([FLASHCARDS, ErroAutenticacao("NVIDIA NIM: chave inválida (HTTP 401).")]),
        "terceiro": _ProvedorFalso([FLASHCARDS]),
    }
    with pytest.raises(cm.ComparacaoInterrompida) as erro:
        _comparar(provedores, relogio)
    assert "HTTP 401" in str(erro.value)
    assert [x.modelo for x in erro.value.medicoes] == ["primeiro"] * 4 + ["segundo"]
    assert provedores["terceiro"].chamadas == 0


def test_chave_recusada_no_catalogo_interrompe(relogio):
    provedores = {"m": _ProvedorFalso([FLASHCARDS], disponivel=ErroAutenticacao("HTTP 403"))}
    with pytest.raises(cm.ComparacaoInterrompida) as erro:
        _comparar(provedores, relogio)
    assert erro.value.medicoes == []


# ── Agregação e relatório ─────────────────────────────────────────────────────


def _medicoes():
    M = cm.Medicao
    return [
        M("a/modelo", "padrao", "d1", "Flashcards", cm.OK, 0.8, "Alta", True, False, 1, 2.0, 100),
        M("a/modelo", "padrao", "d2", "Flashcards", cm.OK, 0.6, "Media", False, True, 2, 4.0, 300),
        M("a/modelo", "padrao", "d3", "Tutorial", cm.FALHA, chamadas=1, latencia_s=3.0, erro="ErroLimiteTaxa"),
        M("a/modelo", "ligado", "d1", "Flashcards", cm.NAO_SUPORTADO, chamadas=1, erro="ErroRequisicaoRecusada"),
        M("b/modelo", "-", "-", "-", cm.INDISPONIVEL, erro="fora do catálogo (GET /models)"),
    ]


def test_agregar_por_modelo_e_variante():
    a, a_ligado, b = cm.agregar(_medicoes())
    assert (a.modelo, a.raciocinio, a.situacao, a.geracoes, a.ok, a.falhas) == (
        "a/modelo", "padrao", "disponível", 3, 2, 1,
    )
    assert a.cortadas == 1
    assert a.ancoragem_media == pytest.approx(0.7)
    assert a.json_valido_taxa == pytest.approx(1 / 3)
    assert a.latencia_media_s == pytest.approx(3.0)
    assert a.tokens_medios == pytest.approx(200)
    assert a.erros == {"ErroLimiteTaxa": 1}
    assert (a_ligado.raciocinio, a_ligado.situacao, a_ligado.geracoes) == ("ligado", cm.NAO_SUPORTADO, 0)
    assert (b.situacao, b.geracoes, b.ancoragem_media, b.json_valido_taxa) == (cm.INDISPONIVEL, 0, None, None)


def test_tabela_markdown():
    tabela = cm.tabela_markdown(cm.agregar(_medicoes()))
    linhas = tabela.splitlines()
    assert linhas[0].startswith("| Modelo | Raciocínio | Situação |")
    assert "| Cortadas |" in linhas[0]
    assert len(linhas) == 5
    assert ("| `a/modelo` | padrao | disponível | 2/3 | 0,700 | 33% | 1 | 3,0 | 200 "
            "| ErroLimiteTaxa ×1 |") in tabela
    assert "| `a/modelo` | ligado | não suportado | 0/0 | — | — | 0 | — | — | ErroRequisicaoRecusada ×1 |" in tabela
    assert "| `b/modelo` | - | indisponível | 0/0 | — | — | 0 | — | — | fora do catálogo (GET /models) ×1 |" in tabela


def test_relatorio_tem_resumo_detalhe_e_documentos():
    relatorio = cm.montar_relatorio(_medicoes(), [DOCUMENTO], ["Flashcards"], datetime(2026, 11, 18, 10, 0))
    assert relatorio.startswith("# Comparação de modelos (NVIDIA NIM), 2026-11-18 10:00")
    assert "Relatório parcial" not in relatorio
    assert f"http_apis_rest.md ({len(DOCUMENTO.texto)} caracteres)" in relatorio
    assert "## Resumo por modelo e raciocínio" in relatorio and "## Gerações" in relatorio
    assert "| `a/modelo` | padrao | d2 | Flashcards | ok | 0,600 | Media | não | sim | 2 |" in relatorio


def test_relatorio_parcial_diz_por_que_parou():
    relatorio = cm.montar_relatorio([], [DOCUMENTO], ["Quiz"], datetime(2026, 11, 18), "HTTP 401")
    assert "**Relatório parcial:** comparação interrompida (HTTP 401)." in relatorio


# ── Linha de comando ──────────────────────────────────────────────────────────


@pytest.fixture
def chave(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr("nvapi-falsa-so-para-teste"))


def test_main_sem_chave_nao_faz_nada(monkeypatch, capsys):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(""))
    assert cm.main([]) == 2
    assert "NVIDIA_NIM_API_KEY não definida" in capsys.readouterr().err


@pytest.mark.parametrize("argumentos,trecho", [
    (["--formatos", "Poema"], "Poema"),
    (["--raciocinio", "talvez"], "talvez"),
    (["--raciocinio", ","], "(vazio)"),
])
def test_main_recusa_opcao_desconhecida(chave, capsys, argumentos, trecho):
    assert cm.main(argumentos, criar_provedor=lambda *_a: pytest.fail("não devia criar provedor")) == 2
    erro = capsys.readouterr().err
    assert trecho in erro and "padrao, desligado, ligado" in erro


def test_listar_imprime_os_ids_ordenados_e_sai(chave, capsys):
    provedor = _ProvedorFalso([], catalogo=["z/modelo", "a/modelo", "m/modelo"])
    assert cm.main(["--listar"], criar_provedor=lambda *_a: provedor) == 0
    assert capsys.readouterr().out.splitlines() == ["a/modelo", "m/modelo", "z/modelo"]
    assert provedor.chamadas == 0  # nada foi gerado


def test_listar_com_chave_recusada(chave, capsys):
    provedor = _ProvedorFalso([], catalogo=ErroAutenticacao("NVIDIA NIM: chave inválida (HTTP 401)."))
    assert cm.main(["--listar"], criar_provedor=lambda *_a: provedor) == 1
    assert "Não foi possível listar os modelos: NVIDIA NIM: chave inválida (HTTP 401)." in capsys.readouterr().err


def test_main_interrompido_grava_relatorio_parcial_e_sai_com_1(chave, capsys, tmp_path):
    provedores = {
        "primeiro": _ProvedorFalso([FLASHCARDS]),
        "segundo": _ProvedorFalso([ErroAutenticacao("NVIDIA NIM: chave inválida ou sem acesso (HTTP 403).")]),
    }
    codigo = cm.main(
        ["--modelos", "primeiro,segundo", "--documentos", "http_apis_rest.md", "--formatos", "Flashcards",
         "--intervalo", "0"],
        criar_provedor=lambda modelo, _variante: provedores[modelo],
        pasta_relatorios=tmp_path,
    )
    assert codigo == 1
    (relatorio,) = tmp_path.glob("comparacao_modelos_*.md")
    texto = relatorio.read_text(encoding="utf-8")
    assert "**Relatório parcial:**" in texto and "HTTP 403" in texto
    assert "| `primeiro` | padrao | http_apis_rest.md | Flashcards | ok |" in texto
    saida = capsys.readouterr()
    assert "Interrompido: NVIDIA NIM: chave inválida ou sem acesso (HTTP 403)." in saida.err
    assert "nvapi-falsa-so-para-teste" not in saida.out + saida.err + texto


def test_main_completo_grava_relatorio_e_sai_com_0(chave, tmp_path):
    provedor = _ProvedorFalso([FLASHCARDS])
    codigo = cm.main(
        ["--modelos", "m", "--raciocinio", "padrao,desligado", "--documentos", "http_apis_rest.md",
         "--formatos", "Flashcards", "--intervalo", "0"],
        criar_provedor=lambda _m, _v: provedor,
        pasta_relatorios=tmp_path,
    )
    assert codigo == 0
    (relatorio,) = tmp_path.glob("comparacao_modelos_*.md")
    texto = relatorio.read_text(encoding="utf-8")
    assert "| `m` | padrao | disponível | 1/1 |" in texto
    assert "| `m` | desligado | disponível | 1/1 |" in texto
