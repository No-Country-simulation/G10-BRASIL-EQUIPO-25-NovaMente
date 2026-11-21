"""Versão e verificação do esquema do catálogo (alunos, materiais e vínculos).

O ``create_all`` do SQLAlchemy só cria tabelas ausentes: não altera as que já
existem. Sem migrações no MVP, a política é recriar o banco antes da release e
**falhar na subida** quando o arquivo tiver um esquema diferente do código, em
vez de quebrar depois com ``no such column``.

A tabela ``esquema_catalogo`` guarda duas coisas:

* ``versao``: o inteiro ``ESQUEMA_VERSAO``, que o dev incrementa junto com a
  mudança de modelo (aparece na mensagem de erro);
* ``impressao_digital``: hash estável das tabelas, colunas, índices e
  constraints declarados nos modelos, que protege contra esquecer de
  incrementar a versão.

A verificação só lê o catálogo (``PRAGMA`` e ``sqlite_master``) e só grava na
tabela ``esquema_catalogo``. Jobs e pacotes nunca são tocados.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, MetaData, Table, UniqueConstraint
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import URL, Connection, Engine

import app.models.db  # noqa: F401  # registra os modelos do catálogo no metadata
from app.core.db import Base

logger = logging.getLogger(__name__)

# Incremente junto com qualquer mudança nos modelos do catálogo (coluna nova,
# constraint, índice). Antes da release, o banco é recriado a cada mudança.
#   1: catálogo inicial (alunos, materiais e vínculos).
#   2: login (coluna alunos.senha_hash e tabela codigos_login).
ESQUEMA_VERSAO = 2

TABELA_METADADOS = "esquema_catalogo"

_CRIAR_METADADOS = f"""
CREATE TABLE IF NOT EXISTS {TABELA_METADADOS} (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    versao INTEGER NOT NULL,
    impressao_digital TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
)
"""


class EsquemaDefasadoError(RuntimeError):
    """O esquema do banco não corresponde ao dos modelos; a subida é abortada."""


# ── Estrutura declarada nos modelos ───────────────────────────────────────────


def _normalizar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _normalizar_default(valor: object) -> str | None:
    if valor is None:
        return None
    return str(valor).strip().strip("'\"")


def _tipo_e_colacao(tipo) -> tuple[str, str | None]:
    compilado = tipo.compile(dialect=sqlite.dialect()).upper()
    base, _, colacao = compilado.partition(" COLLATE ")
    return base, (colacao or None)


def _tabela_declarada(tabela: Table) -> dict:
    posicao_pk = {c.name: i for i, c in enumerate(tabela.primary_key.columns, start=1)}
    colunas = {}
    for coluna in tabela.columns:
        tipo, colacao = _tipo_e_colacao(coluna.type)
        padrao = coluna.server_default.arg if coluna.server_default is not None else None
        colunas[coluna.name] = {
            "tipo": tipo,
            "colacao": colacao,
            "obrigatoria": not coluna.nullable,
            "pk": posicao_pk.get(coluna.name, 0),
            "padrao": _normalizar_default(padrao),
        }
    indices = {
        indice.name: {
            "colunas": [c.name for c in indice.columns],
            "unico": bool(indice.unique),
        }
        for indice in tabela.indexes
    }
    unicos = sorted(
        [c.name for c in restricao.columns]
        for restricao in tabela.constraints
        if isinstance(restricao, UniqueConstraint)
    )
    fks = sorted(
        [
            elemento.parent.name,
            elemento.column.table.name,
            elemento.column.name,
            (restricao.ondelete or "NO ACTION").upper(),
        ]
        for restricao in tabela.foreign_key_constraints
        for elemento in restricao.elements
    )
    checks = sorted(
        _normalizar_espacos(str(restricao.sqltext))
        for restricao in tabela.constraints
        if isinstance(restricao, CheckConstraint)
    )
    return {
        "colunas": colunas,
        "indices": indices,
        "unicos": unicos,
        "fks": fks,
        "checks": checks,
    }


def estrutura_declarada(metadata: MetaData | None = None) -> dict:
    """Estrutura (tabelas, colunas, índices, constraints) declarada nos modelos."""
    metadata = Base.metadata if metadata is None else metadata
    return {t.name: _tabela_declarada(t) for t in metadata.sorted_tables}


def impressao_digital(metadata: MetaData | None = None) -> str:
    """Hash estável (SHA-256) da estrutura declarada; independe da ordem das colunas."""
    canonico = json.dumps(
        estrutura_declarada(metadata), sort_keys=True, ensure_ascii=True, separators=(",", ":")
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


# ── Estrutura real do banco (somente leitura) ─────────────────────────────────


def _extrair_checks(ddl: str) -> list[str]:
    """Extrai o texto de cada ``CHECK (...)`` do DDL da tabela."""
    achados = []
    for m in re.finditer(r"CHECK\s*\(", ddl, flags=re.IGNORECASE):
        nivel, aspas, inicio = 1, None, m.end()
        for pos in range(inicio, len(ddl)):
            c = ddl[pos]
            if aspas:
                if c == aspas:
                    aspas = None
            elif c in ("'", '"'):
                aspas = c
            elif c == "(":
                nivel += 1
            elif c == ")":
                nivel -= 1
                if nivel == 0:
                    achados.append(_normalizar_espacos(ddl[inicio:pos]))
                    break
    return sorted(achados)


def _tabela_real(conexao: Connection, nome: str) -> dict | None:
    linhas = conexao.exec_driver_sql(f'PRAGMA table_info("{nome}")').fetchall()
    if not linhas:
        return None
    colunas = {
        linha[1]: {
            "tipo": (linha[2] or "").upper(),
            "obrigatoria": bool(linha[3]),
            "pk": linha[5],
            "padrao": _normalizar_default(linha[4]),
        }
        for linha in linhas
    }
    indices, unicos = {}, []
    for _seq, nome_indice, unico, origem, *_ in conexao.exec_driver_sql(
        f'PRAGMA index_list("{nome}")'
    ).fetchall():
        info = conexao.exec_driver_sql(f'PRAGMA index_info("{nome_indice}")').fetchall()
        cols = [i[2] for i in sorted(info, key=lambda i: i[0])]
        if origem == "c":
            indices[nome_indice] = {"colunas": cols, "unico": bool(unico)}
        elif origem == "u":
            unicos.append(cols)
    fks = sorted(
        [fk[3], fk[2], fk[4], (fk[6] or "NO ACTION").upper()]
        for fk in conexao.exec_driver_sql(f'PRAGMA foreign_key_list("{nome}")').fetchall()
    )
    ddl = conexao.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (nome,)
    ).scalar()
    return {
        "colunas": colunas,
        "indices": indices,
        "unicos": sorted(unicos),
        "fks": fks,
        "checks": _extrair_checks(ddl or ""),
    }


# ── Comparação ────────────────────────────────────────────────────────────────


def _comparar_mapas(rotulo: str, esperado: dict, real: dict, ignorar: tuple[str, ...] = ()) -> list[str]:
    difs = []
    for chave in sorted(esperado.keys() - real.keys()):
        difs.append(f"falta {rotulo} '{chave}'")
    for chave in sorted(real.keys() - esperado.keys()):
        difs.append(f"{rotulo} '{chave}' existe no banco, mas não nos modelos")
    for chave in sorted(esperado.keys() & real.keys()):
        a = {k: v for k, v in esperado[chave].items() if k not in ignorar}
        b = {k: v for k, v in real[chave].items() if k not in ignorar}
        if a != b:
            difs.append(f"{rotulo} '{chave}' diferente (banco: {b}; modelos: {a})")
    return difs


def _comparar_listas(rotulo: str, esperado: list, real: list) -> list[str]:
    esp = {json.dumps(i) for i in esperado}
    rea = {json.dumps(i) for i in real}
    return [f"falta {rotulo} {i}" for i in sorted(esp - rea)] + [
        f"{rotulo} {i} existe no banco, mas não nos modelos" for i in sorted(rea - esp)
    ]


def _diferencas(conexao: Connection, declarado: dict) -> list[str]:
    """Diferenças entre o banco real e os modelos (vazio quando são compatíveis)."""
    difs = []
    for nome, esperado in declarado.items():
        real = _tabela_real(conexao, nome)
        if real is None:
            difs.append(f"{nome}: a tabela não existe")
            continue
        parciais = (
            _comparar_mapas("coluna", esperado["colunas"], real["colunas"], ignorar=("colacao",))
            + _comparar_mapas("índice", esperado["indices"], real["indices"])
            + _comparar_listas("restrição UNIQUE", esperado["unicos"], real["unicos"])
            + _comparar_listas("chave estrangeira", esperado["fks"], real["fks"])
            + _comparar_listas("restrição CHECK", esperado["checks"], real["checks"])
        )
        difs.extend(f"{nome}: {d}" for d in parciais)
    return difs


# ── Mensagens ─────────────────────────────────────────────────────────────────


def _descrever_banco(url: URL) -> tuple[str, str | None]:
    """Descrição do banco para a mensagem (sem senha) e o caminho do arquivo SQLite."""
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        return f"arquivo SQLite {url.database}", url.database
    return f"banco {url.render_as_string(hide_password=True)}", None


def _como_recriar(caminho: str | None) -> str:
    alvo = (
        f"o arquivo {caminho} (e também {caminho}-wal e {caminho}-shm, se existirem)"
        if caminho
        else "o banco configurado em DATABASE_URL"
    )
    return (
        "Para recriar o banco: (1) pare o backend; "
        f"(2) mova (para guardar uma cópia) ou apague {alvo}; "
        "(3) suba o backend de novo, que cria as tabelas do zero. "
        "Atenção: por padrão DB_PATH e DATABASE_URL apontam para o mesmo arquivo, "
        "então jobs e histórico de pacotes também serão perdidos; mova o arquivo "
        "se precisar de uma cópia."
    )


_POLITICA = (
    "A política do MVP é não migrar: antes da release, mudanças de esquema "
    "exigem recriar o banco. O backend não subiu para evitar erros em tempo de "
    "execução (como 'no such column')."
)


def _erro(url: URL, detalhe: str) -> EsquemaDefasadoError:
    descricao, caminho = _descrever_banco(url)
    return EsquemaDefasadoError(
        f"O esquema do catálogo no {descricao} não corresponde ao esperado "
        f"por esta versão do código. {detalhe} {_POLITICA} {_como_recriar(caminho)}"
    )


# ── Verificação ───────────────────────────────────────────────────────────────


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def verificar_esquema_catalogo(
    engine: Engine,
    metadata: MetaData | None = None,
    versao: int = ESQUEMA_VERSAO,
) -> None:
    """Confere o esquema do catálogo no banco do ``engine`` e carimba a versão.

    * Sem metadados e estrutura compatível com os modelos (banco novo ou criado
      antes desta política): grava versão e impressão digital.
    * Sem metadados e estrutura diferente: levanta ``EsquemaDefasadoError``.
    * Com metadados: versão ou impressão digital diferentes das do código
      levantam ``EsquemaDefasadoError``; iguais, nada é alterado.

    Deve rodar depois do ``create_all``. Nunca altera nem apaga dados.
    """
    declarado = estrutura_declarada(metadata)
    digital = impressao_digital(metadata)
    with engine.begin() as conexao:
        conexao.exec_driver_sql(_CRIAR_METADADOS)
        linha = conexao.exec_driver_sql(
            f"SELECT versao, impressao_digital FROM {TABELA_METADADOS} WHERE id = 1"
        ).fetchone()

        if linha is None:
            difs = _diferencas(conexao, declarado)
            if difs:
                resumo = "; ".join(difs[:10]) + (" ..." if len(difs) > 10 else "")
                raise _erro(
                    engine.url,
                    "O banco foi criado antes do controle de versão do esquema e "
                    f"sua estrutura difere dos modelos atuais: {resumo}.",
                )
            conexao.exec_driver_sql(
                f"INSERT OR IGNORE INTO {TABELA_METADADOS} "
                "(id, versao, impressao_digital, atualizado_em) VALUES (1, ?, ?, ?)",
                (versao, digital, _agora_iso()),
            )
            logger.info("Esquema do catálogo carimbado na versão %s.", versao)
            return

    versao_banco, digital_banco = linha
    if versao_banco != versao:
        raise _erro(
            engine.url,
            f"O banco está na versão {versao_banco} do esquema e o código espera a versão {versao}.",
        )
    if digital_banco != digital:
        raise _erro(
            engine.url,
            f"A versão do esquema é a mesma ({versao}), mas a estrutura das tabelas "
            "mudou (a impressão digital dos modelos é diferente da gravada no banco). "
            "Provavelmente um modelo foi alterado sem incrementar ESQUEMA_VERSAO em "
            "app/core/esquema.py.",
        )
