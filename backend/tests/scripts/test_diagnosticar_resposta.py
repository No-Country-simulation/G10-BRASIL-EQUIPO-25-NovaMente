"""Diagnóstico das respostas do modelo (scripts/diagnosticar_resposta.py), sem rede."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.llm.erros import ErroIndisponivel
from app.services import pipeline

_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "diagnosticar_resposta.py"
_spec = importlib.util.spec_from_file_location("diagnosticar_resposta", _CAMINHO)
dr = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = dr  # os dataclasses do script procuram o módulo aqui
_spec.loader.exec_module(dr)

CHAVE_FALSA = "nvapi-chave-falsa-do-diagnostico-123"
VALIDO = json.dumps(dr._QUIZ_VALIDO, ensure_ascii=False)


def _quiz(**mudancas_no_item):
    dados = json.loads(VALIDO)
    for chave, valor in mudancas_no_item.items():
        if valor is None:
            del dados["itens"][0][chave]
        else:
            dados["itens"][0][chave] = valor
    return json.dumps(dados, ensure_ascii=False)


# ── Classificação ─────────────────────────────────────────────────────────────


def test_resposta_valida():
    d = dr.classificar(VALIDO, "Quiz", "stop")
    assert (d.categoria, d.mensagem, d.sinais) == ("valida", None, [])
    assert d.tamanho == len(VALIDO)


@pytest.mark.parametrize(
    "texto,motivo,categoria",
    [
        (VALIDO[: len(VALIDO) // 2], "stop", "truncado"),
        (VALIDO[:-1], "length", "truncado"),
        ("Não consegui gerar.", "stop", "outro"),
        (VALIDO.replace('"Revisão do material."', '"Revisão\ndo material."'), "stop", "json_invalido"),
        (VALIDO.replace('"Quiz",', '"Quiz"'), "stop", "json_invalido"),
        ("```json\n" + VALIDO + "\n```\n\nExemplo: ```{\"a\": 1}```", "stop", "bloco_markdown"),
        (_quiz(explicacao=None), "stop", "campo_ausente"),
        (_quiz(opcoes=["POST"]), "stop", "valor_fora_do_intervalo"),
        (_quiz(resposta_correta=-1), "stop", "valor_fora_do_intervalo"),
        (_quiz(resposta_correta="B"), "stop", "outro"),
    ],
)
def test_categorias(texto, motivo, categoria):
    d = dr.classificar(texto, "Quiz", motivo)
    assert d.categoria == categoria, d
    # Mesma decisão do pipeline: só o que o pipeline aceita sai como válido.
    try:
        pipeline._parsear_conteudo(pipeline._extrair_json(texto), "Quiz")
        aceito = True
    except Exception:
        aceito = False
    assert aceito is False


def test_cerca_markdown_sozinha_nao_quebra():
    d = dr.classificar("```json\n" + VALIDO + "\n```", "Quiz", "stop")
    assert d.categoria == "valida" and "cerca_markdown" in d.sinais


def test_mensagens_e_posicoes_sem_conteudo():
    quebrado = VALIDO.replace('"Revisão do material."', '"Revisão\ndo material."')
    d = dr.classificar(quebrado, "Quiz", "stop")
    assert "quebra de linha" in d.mensagem
    assert d.posicao == quebrado.index("\ndo material")
    assert 0 < d.posicao_relativa < 1
    assert "Revisão" not in d.mensagem and "material" not in d.mensagem

    letra = dr.classificar(_quiz(resposta_correta="B"), "Quiz", "stop")
    assert letra.caminho == "resposta_correta"
    assert "int_parsing" in letra.mensagem and "letra" in letra.mensagem
    assert "'B'" not in letra.mensagem and '"B"' not in letra.mensagem  # sem o valor recebido

    sem_titulo = json.loads(VALIDO)
    del sem_titulo["titulo"]
    d = dr.classificar(json.dumps(sem_titulo), "Quiz", "stop")
    assert (d.categoria, d.caminho) == ("campo_ausente", "titulo")


def test_texto_antes_e_depois_do_json():
    d = dr.classificar("Aqui está: " + VALIDO + " Espero ter ajudado {fim}", "Quiz", "stop")
    assert d.categoria == "json_invalido"
    assert "texto_antes_do_json" in d.sinais and "texto_depois_do_json" in d.sinais
    assert d.mensagem == "Extra data"


def test_avisos_do_quiz_que_o_pipeline_aceita():
    d = dr.classificar(_quiz(resposta_correta=5, opcoes=["GET", "GET"]), "Quiz", "stop")
    assert d.categoria == "valida"
    assert "itens.0.resposta_correta_fora_das_opcoes" in d.sinais
    assert "itens.0.opcoes_repetidas" in d.sinais


def test_outros_formatos():
    tutorial = json.dumps({"tipo": "markdown", "titulo": "T", "introducao_contextualizada": "I",
                           "itens": "## Passo 1\nFaça isto com bastante detalhe e cuidado."})
    assert dr.classificar(tutorial, "Tutorial", "stop").categoria == "valida"
    curto = json.dumps({"tipo": "markdown", "titulo": "T", "introducao_contextualizada": "I", "itens": "## A"})
    assert dr.classificar(curto, "Tutorial", "stop").categoria == "valor_fora_do_intervalo"


# ── Execução ──────────────────────────────────────────────────────────────────


def test_simulado_reproduz_cada_categoria_e_grava_so_metadados(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(CHAVE_FALSA))
    n = len(dr.respostas_simuladas())
    assert dr.main(["--simulado", "--n", str(n), "--intervalo", "0"], pasta_relatorios=tmp_path) == 0
    (md,) = tmp_path.glob("diagnostico_resposta_*.md")
    (js,) = tmp_path.glob("diagnostico_resposta_*.json")
    dados = json.loads(js.read_text(encoding="utf-8"))
    assert set(dados["resumo"]) == set(dr.CATEGORIAS)
    assert dados["resumo"]["truncado"] == 2  # finish_reason length e JSON cortado
    truncado_pelo_provedor = dados["respostas"][1]
    assert (truncado_pelo_provedor["motivo_fim"], truncado_pelo_provedor["tamanho"]) == ("length", None)
    assert all(r["tokens_total"] for r in dados["respostas"])
    texto = md.read_text(encoding="utf-8") + js.read_text(encoding="utf-8") + capsys.readouterr().out
    documento = (dr.EXEMPLOS / dr.DOCUMENTO_PADRAO).read_text(encoding="utf-8")
    for frase in [f for f in documento.split(". ") if len(f) > 60][:5]:
        assert frase not in texto
    for conteudo in ("POST cria um recurso", "Qual método cria?", "Revisão do material"):
        assert conteudo not in texto
    assert CHAVE_FALSA not in texto
    assert "## Resumo por categoria" in texto


def test_usa_o_mesmo_prompt_da_medicao():
    documento = dr.carregar_documento(dr.EXEMPLOS / "sql_consultas.md")
    prompt = dr.montar_prompt(documento, "Quiz")
    assert prompt.startswith("Você é um especialista em educação técnica.")
    assert '"tipo":"quiz"' in prompt and "REVISÃO" not in prompt
    assert "Público-alvo: desenvolvedor júnior ou pleno." in prompt


def test_intervalo_entre_chamadas():
    esperas = []
    agora = [0.0]

    def relogio():
        return agora[0]

    ritmo = dr.Ritmo(3.0, dormir=lambda s: (esperas.append(s), agora.__setitem__(0, agora[0] + s)), relogio=relogio)
    dr.diagnosticar(dr.ProvedorSimulado([("stop", VALIDO)]), "prompt", "Quiz", 3, ritmo, relogio=relogio)
    assert esperas == [3.0, 3.0]


def test_erro_do_provedor_vira_outro():
    provedor = dr.ProvedorSimulado([("stop", ErroIndisponivel("503"))])
    (d,) = dr.diagnosticar(provedor, "prompt", "Quiz", 1, dr.Ritmo(0))
    assert (d.categoria, d.mensagem) == ("outro", "erro do provedor: ErroIndisponivel")


def test_sem_chave_sai_com_codigo_2(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "nvidia")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", SecretStr(""))
    assert dr.main([], pasta_relatorios=tmp_path) == 2
    erro = capsys.readouterr().err
    assert "NVIDIA_NIM_API_KEY não definida" in erro and "Traceback" not in erro
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("argv", [["--formato", "Poema"], ["--documento", "nao.md"], ["--n", "0"]])
def test_opcoes_invalidas(tmp_path, argv):
    assert dr.main([*argv, "--simulado"], pasta_relatorios=tmp_path) == 2
