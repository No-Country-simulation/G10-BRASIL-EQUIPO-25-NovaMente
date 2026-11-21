"""Esquema do catálogo com o login: versão 2 (alunos.senha_hash e codigos_login).

A política (app/core/esquema.py) não migra: banco de versão anterior impede a
subida com a instrução de recriar.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from app.core.db import Base
from app.core.esquema import (
    ESQUEMA_VERSAO,
    TABELA_METADADOS,
    EsquemaDefasadoError,
    verificar_esquema_catalogo,
)


@pytest.fixture
def engine_temp(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path}/catalogo.db")
    yield eng
    eng.dispose()


def _colunas(eng, tabela: str) -> set[str]:
    with eng.connect() as c:
        return {linha[1] for linha in c.exec_driver_sql(f'PRAGMA table_info("{tabela}")')}


def _versao_gravada(eng) -> int:
    with eng.connect() as c:
        return c.exec_driver_sql(f"SELECT versao FROM {TABELA_METADADOS}").scalar()


def test_versao_do_esquema_inclui_o_login():
    assert ESQUEMA_VERSAO == 2
    tabelas = Base.metadata.tables
    assert "codigos_login" in tabelas
    assert "senha_hash" in tabelas["alunos"].columns


def test_banco_novo_sobe_com_as_tabelas_do_login(engine_temp):
    Base.metadata.create_all(bind=engine_temp)
    verificar_esquema_catalogo(engine_temp)

    assert _versao_gravada(engine_temp) == ESQUEMA_VERSAO
    assert "senha_hash" in _colunas(engine_temp, "alunos")
    assert {"email", "perfil", "proposito", "codigo_hash"} <= _colunas(engine_temp, "codigos_login")


def test_banco_carimbado_na_versao_anterior_impede_a_subida(engine_temp):
    Base.metadata.create_all(bind=engine_temp)
    verificar_esquema_catalogo(engine_temp, versao=ESQUEMA_VERSAO - 1)

    with pytest.raises(EsquemaDefasadoError) as erro:
        verificar_esquema_catalogo(engine_temp)
    mensagem = str(erro.value)
    assert f"versão {ESQUEMA_VERSAO - 1}" in mensagem
    assert f"versão {ESQUEMA_VERSAO}" in mensagem
    assert "recriar" in mensagem


def test_banco_de_antes_do_login_impede_a_subida_e_nada_e_alterado(engine_temp):
    # Banco antigo: sem a coluna e sem a tabela. O create_all da subida recria a
    # tabela que falta, mas não acrescenta coluna em tabela existente.
    Base.metadata.create_all(bind=engine_temp)
    with engine_temp.begin() as c:
        c.exec_driver_sql("DROP TABLE codigos_login")
        c.exec_driver_sql("ALTER TABLE alunos DROP COLUMN senha_hash")
    Base.metadata.create_all(bind=engine_temp)

    with pytest.raises(EsquemaDefasadoError, match="alunos: falta coluna 'senha_hash'"):
        verificar_esquema_catalogo(engine_temp)
    assert "senha_hash" not in _colunas(engine_temp, "alunos")
