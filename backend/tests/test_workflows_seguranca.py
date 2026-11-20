"""Estrutura dos arquivos de CI de segurança (workflow e Dependabot).

Confere a sintaxe e as regras combinadas; quem executa os passos é o GitHub.
Os testes são ignorados se o PyYAML não estiver instalado ou se a pasta
.github não existir (por exemplo, numa imagem só com o backend).
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

RAIZ = Path(__file__).resolve().parents[2]
WORKFLOW = RAIZ / ".github" / "workflows" / "seguranca.yml"
DEPENDABOT = RAIZ / ".github" / "dependabot.yml"

pytestmark = pytest.mark.skipif(
    not (WORKFLOW.exists() and DEPENDABOT.exists()), reason="pasta .github ausente"
)


def _carregar(caminho: Path) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> dict:
    return _carregar(WORKFLOW)


@pytest.fixture(scope="module")
def passos(workflow) -> list[dict]:
    return [p for job in workflow["jobs"].values() for p in job["steps"]]


def _gatilhos(workflow: dict) -> dict:
    # No YAML 1.1 a chave "on" vira o booleano True.
    return workflow.get("on", workflow.get(True))


def test_gatilhos_pull_request_e_push_em_develop_e_main(workflow):
    gatilhos = _gatilhos(workflow)
    assert set(gatilhos) == {"push", "pull_request"}
    assert gatilhos["push"]["branches"] == ["develop", "main"]
    assert gatilhos["pull_request"]["branches"] == ["develop", "main"]


def test_permissoes_minimas(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job  # nenhum job pede mais que o mínimo


def test_actions_usam_tag_de_versao_maior(passos):
    for passo in passos:
        if "uses" in passo:
            _, _, versao = passo["uses"].partition("@")
            assert versao.startswith("v") and versao[1:].isdigit(), passo["uses"]


def test_gitleaks_por_container_com_tag_fixa_e_redact(workflow):
    job = workflow["jobs"]["segredos"]
    texto = "\n".join(p.get("run", "") for p in job["steps"])
    usos = [p.get("uses", "") for p in job["steps"]]

    assert not any("gitleaks" in uso for uso in usos)  # sem a gitleaks-action (exige licença)
    assert "docker run" in texto
    assert "--redact" in texto
    imagem = next(t for t in texto.split() if "gitleaks/gitleaks:" in t)
    tag = imagem.split(":", 1)[1]
    assert tag != "latest" and tag.startswith("v8.")


def test_gitleaks_le_o_historico_completo(workflow):
    checkout = next(
        p for p in workflow["jobs"]["segredos"]["steps"] if p.get("uses", "").startswith("actions/checkout")
    )
    assert checkout["with"]["fetch-depth"] == 0


def test_auditorias_sao_informativas(workflow):
    for nome in ("auditoria-backend", "auditoria-frontend"):
        job = workflow["jobs"][nome]
        assert job["continue-on-error"] is True
        passos_auditoria = [p for p in job["steps"] if "audit" in p.get("run", "") and "install" not in p["run"]]
        assert passos_auditoria and all(p["continue-on-error"] is True for p in passos_auditoria)
    assert "pip-audit" in "\n".join(p.get("run", "") for p in workflow["jobs"]["auditoria-backend"]["steps"])
    assert "npm audit" in "\n".join(p.get("run", "") for p in workflow["jobs"]["auditoria-frontend"]["steps"])


def test_o_gitleaks_reprova_o_job(workflow):
    # Só as auditorias são informativas; a varredura de segredos reprova.
    assert "continue-on-error" not in workflow["jobs"]["segredos"]
    assert all("continue-on-error" not in p for p in workflow["jobs"]["segredos"]["steps"])


def test_dependabot_cobre_pip_npm_e_actions():
    atualizacoes = _carregar(DEPENDABOT)["updates"]
    por_ecossistema = {u["package-ecosystem"]: u for u in atualizacoes}

    assert set(por_ecossistema) == {"pip", "npm", "github-actions"}
    assert por_ecossistema["pip"]["directory"] == "/backend"
    assert por_ecossistema["npm"]["directory"] == "/frontend"
    assert por_ecossistema["github-actions"]["directory"] == "/"
    for atualizacao in atualizacoes:
        assert atualizacao["schedule"]["interval"] == "weekly"
        assert 1 <= atualizacao["open-pull-requests-limit"] <= 3
