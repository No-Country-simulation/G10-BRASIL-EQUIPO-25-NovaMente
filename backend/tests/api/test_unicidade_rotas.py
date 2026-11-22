"""Unicidade das rotas registradas no app."""

from __future__ import annotations

import re

from starlette.routing import Route

from app.main import app

_PARAMETRO = re.compile(r"\{[^}]+\}")


def _rotas() -> list[tuple[int, str, str, Route]]:
    """(posição, método, caminho, rota) de cada rota HTTP, na ordem de registro."""
    saida = []
    for posicao, rota in enumerate(app.routes):
        if not isinstance(rota, Route) or not rota.methods:
            continue
        for metodo in sorted(rota.methods - {"HEAD"}) or sorted(rota.methods):
            saida.append((posicao, metodo, rota.path, rota))
    return saida


def test_nao_ha_rota_duplicada():
    vistas: dict[tuple[str, str], int] = {}
    duplicadas = []
    for posicao, metodo, caminho, _ in _rotas():
        chave = (metodo, caminho)
        if chave in vistas:
            duplicadas.append(chave)
        vistas[chave] = posicao
    assert duplicadas == []


def test_nao_ha_caminhos_equivalentes_com_parametros_diferentes():
    por_forma: dict[tuple[str, str], set[str]] = {}
    for _, metodo, caminho, _ in _rotas():
        forma = _PARAMETRO.sub("{}", caminho)
        por_forma.setdefault((metodo, forma), set()).add(caminho)
    equivalentes = {chave: nomes for chave, nomes in por_forma.items() if len(nomes) > 1}
    assert equivalentes == {}


def test_rota_estatica_nao_e_engolida_por_rota_com_parametro_anterior():
    rotas = _rotas()
    conflitos = []
    for posicao, metodo, caminho, _ in rotas:
        if _PARAMETRO.search(caminho):
            continue
        for posicao_antes, metodo_antes, caminho_antes, rota_antes in rotas:
            if (
                posicao_antes < posicao
                and metodo_antes == metodo
                and _PARAMETRO.search(caminho_antes)
                and rota_antes.path_regex.match(caminho)
            ):
                conflitos.append((metodo, caminho, caminho_antes))
    assert conflitos == []
