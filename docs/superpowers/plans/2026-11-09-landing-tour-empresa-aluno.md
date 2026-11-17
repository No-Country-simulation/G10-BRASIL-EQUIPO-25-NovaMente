# Landing, tour, empresa e aluno — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar landing pública, separação empresa × aluno, CRUD de alunos/materiais/vínculos com SQLite e tour guiado, sem autenticação.

**Architecture:** O Next.js passa a ter três áreas (`/`, `/empresa/*`, `/aluno/*`). O FastAPI ganha SQLite/SQLAlchemy para catálogo durável, mantendo jobs em memória e OCI para artefatos. O frontend continua com hooks → `NovaMenteApi` → `httpApiClient` → MSW em dev/teste. Materiais nascem como rascunho e só chegam ao aluno quando publicados e vinculados.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind 4, TanStack Query, Zustand, RHF + Zod, MSW, Vitest, Playwright; FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, OCI Object Storage; `driver.js` para o tour.

**Spec:** `docs/superpowers/specs/2026-11-09-landing-tour-empresa-aluno-design.md`

## Global Constraints

- Interface e textos em pt-BR; identificadores de código seguem o padrão existente (português no domínio, inglês em APIs de biblioteca).
- Nenhuma autenticação, token, cookie, sessão ou tela de login nesta entrega.
- `material_id` é igual a `adaptacao_id` nesta fase.
- Material criado pelo pipeline nasce com `visibilidade = "rascunho"`.
- Conteúdo do pacote é imutável; PATCH de material aceita apenas `titulo` e `visibilidade`.
- Rotas de aluno filtram no servidor por aluno `ativo` + material `publicado` + vínculo existente.
- Rotas de aluno nunca revelam existência de material não liberado: `404 MATERIAL_NAO_DISPONIVEL`.
- Listagens nunca desserializam `pacote_json`; usam as colunas desnormalizadas.
- Paginação padrão: página 1, 12 itens, máximo 50.
- Datas em ISO 8601 UTC com `Z`; IDs em ULID.
- Base HTTP `/api/v1`; erros no envelope `ApiProblema`.
- Rotas antigas `/historico` e `/resultado/:id` redirecionam permanentemente para `/empresa/...`.
- `nome` de aluno: 3..120 após `trim`; `email` válido, único case-insensitive, normalizado para minúsculas.
- Toda tela define carregando, vazio, erro e sucesso; nenhuma tela em branco.
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`, `npm run e2e` e `pytest` verdes ao final.
- Cobertura de `src/features/**` e `src/services/**` ≥ 80% de linhas, 80% statements/functions, 70% branches.
- Commits atômicos por tarefa, em branch descritiva (`feat/landing-tour-empresa-aluno`).

## Review Focus

1. **Pacote JSON corrompido** — listar materiais, histórico e catálogo do aluno devem continuar funcionando; apenas o detalhe falha com 500. Teste na tarefa 2 (repositório), 3 (API de materiais) e 6 (API do aluno).
2. **Material não publicado, não vinculado ou aluno inativo** — todos os casos de acesso indevido devem responder `404 MATERIAL_NAO_DISPONIVEL` ou `403 ALUNO_INATIVO`, sem revelar se o material existe. Teste na tarefa 6 e 14.
3. **Vínculo salvo com filtro/paginação** — desmarcar/alterar uma página não pode desvincular materiais fora dela. Teste na tarefa 5 (API) e 13 (painel).
4. **E-mail duplicado com caixa diferente** — `Ana@X.com` e `ana@x.com` devem colidir com 409, sem criar linha duplicada. Teste na tarefa 4 e 12.
5. **Alvo de tour ausente ou rota alterada** — o tour deve pular o passo e continuar, sem prender foco ou iniciar duas vezes. Teste na tarefa 15.

---

## File Structure

### Backend

```
backend/
  app/
    core/db.py                       engine, SessionLocal, Base, get_db
    core/config.py                   + database_url
    models/db.py                     AlunoDB, MaterialDB, VinculoDB
    models/alunos.py                 schemas Pydantic de aluno/vínculo
    models/materiais.py              schemas Pydantic de material
    models/aluno_catalogo.py         schemas de identificação/catálogo
    models/__init__.py               reexporta tudo
    services/repositorio.py          jobs em memória; pacotes em SQLite
    services/materiais.py            criação, consulta, serialização, exclusão
    services/alunos.py               CRUD e vínculos
    api/v1/routers/alunos.py
    api/v1/routers/materiais.py
    api/v1/routers/aluno.py
    api/v1/routers/adaptacoes.py     compatibilidade via repositório
    services/oci.py                  + remover_objeto
    main.py                          routers + lifespan/create_all
  tests/
    conftest.py                      banco temporário, schema, limpeza, fixtures
    test_db.py
    test_repositorio_sqlite.py
    api/test_materiais.py
    api/test_alunos.py
    api/test_vinculos.py
    api/test_aluno_catalogo.py
  requirements.txt                   + sqlalchemy, email-validator
```

### Frontend

```
frontend/src/
  app/
    (public)/page.tsx
    (empresa)/empresa/layout.tsx
    (empresa)/empresa/page.tsx
    (empresa)/empresa/gerar/page.tsx
    (empresa)/empresa/historico/page.tsx
    (empresa)/empresa/materiais/page.tsx
    (empresa)/empresa/alunos/page.tsx
    (empresa)/empresa/alunos/[id]/page.tsx
    (empresa)/empresa/resultado/[id]/page.tsx
    (aluno)/aluno/layout.tsx
    (aluno)/aluno/page.tsx
    (aluno)/aluno/materiais/[id]/page.tsx
  components/landing/                 LandingPage + seções
  components/layout/
    LandingHeader.tsx
    EmpresaShell.tsx
    EmpresaHeader.tsx
    AlunoShell.tsx
    AlunoHeader.tsx
    TourLauncher.tsx
  components/materiais/
    MateriaisView.tsx
    MaterialCard.tsx
    MaterialEditDialog.tsx
    MaterialDeleteDialog.tsx
  components/alunos/
    AlunosView.tsx
    AlunoCard.tsx
    AlunoFormDialog.tsx
    AlunoDeleteDialog.tsx
    AlunoDetalheView.tsx
    VinculosPanel.tsx
  components/aluno/
    IdentificacaoAluno.tsx
    CatalogoAlunoView.tsx
    AlunoMaterialView.tsx
  features/
    materiais/useMateriais.ts
    alunos/useAlunos.ts
    alunos/useVinculos.ts
    aluno/useIdentidadeAluno.ts
    aluno/useCatalogoAluno.ts
    aluno/useMaterialAluno.ts
    tour/useTour.ts
    tour/driver.ts
  lib/rotas.ts
  lib/mensagens.ts                    + M.landing, M.tour, M.alunos, M.materiais, M.aluno
  types/schemas.ts                    + schemas novos
  types/novamente.ts                  + tipos novos
  services/api/endpoints.ts           + URLs novas
  services/api/NovaMenteApi.ts        + métodos
  services/api/httpApiClient.ts       + implementações
  mocks/estadoCatalogo.ts
  mocks/handlers/alunos.ts
  mocks/handlers/materiais.ts
  mocks/handlers/aluno.ts
  mocks/fixtures/alunos.json
  mocks/fixtures/materiais.json
  next.config.ts                      + redirects
```

---

### Task 1: Base SQLite e modelos

**Files:**
- Create: `backend/app/core/db.py`
- Create: `backend/app/models/db.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Consumes: nada.
- Produces: `DATABASE_URL` em `Settings`; `engine`, `SessionLocal`, `Base`, `get_db()` em `app.core.db`; classes `AlunoDB`, `MaterialDB`, `VinculoDB` em `app.models.db`; fixtures pytest `db_session` e `cliente`.

- [x] **Step 1: Escrever o teste que falha**

```python
# backend/tests/test_db.py
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.db import AlunoDB

def agora(): return datetime.now(timezone.utc).isoformat()

def test_email_unico_ignora_caixa(db_session):
    db_session.add(AlunoDB(aluno_id="A1", nome="Ana", email="ana@exemplo.com",
                           status="ativo", criado_em=agora(), atualizado_em=agora()))
    db_session.commit()
    db_session.add(AlunoDB(aluno_id="A2", nome="Bia", email="ANA@exemplo.com",
                           status="ativo", criado_em=agora(), atualizado_em=agora()))
    with pytest.raises(IntegrityError):
        db_session.commit()

def test_excluir_aluno_remove_vinculos(db_session):
    # cria aluno, material, vínculo, exclui o aluno e verifica que o vínculo sumiu
    ...
```

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_db.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.core.db'`.

- [x] **Step 3: Implementar a fundação**

Criar `core/db.py`:

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def _pragmas(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

def get_db():
    with SessionLocal() as session:
        yield session
```

Em `models/db.py`, declarar as três tabelas com os nomes, colunas, checks, índices e FKs da seção 5.1 da spec. Usar `Mapped`/`mapped_column`, `ondelete="CASCADE"` e `collate("NOCASE")` no e-mail.

Em `core/config.py`, adicionar `database_url: str = "sqlite:///./data/novamente.db"`.
Em `main.py`, adicionar `lifespan` que executa `Base.metadata.create_all(bind=engine)`.
Em `requirements.txt`, adicionar `sqlalchemy>=2.0,<3` e `email-validator>=2.2,<3`.
No `.gitignore` raiz, adicionar `backend/data/*.db`, `backend/data/*.db-wal`, `backend/data/*.db-shm`.

Em `tests/conftest.py`, antes de importar `app`:

```python
import os, tempfile
_TMP = tempfile.mkdtemp(prefix="novamente-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
```

Adicionar `_schema` (session, autouse, `create_all`/`drop_all`), `_limpar` (function, autouse, `DELETE` em `vinculos`, `materiais`, `alunos`), `db_session` e `cliente`:

```python
@pytest.fixture
def cliente(db_session):
    from app.main import app
    from app.core.db import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_db.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/core backend/app/models/db.py backend/app/main.py backend/requirements.txt backend/tests .gitignore
git commit -m "feat(backend): adiciona base SQLite e modelos de alunos, materiais e vínculos"
```

---

### Task 2: Repositório durável e material automático

**Files:**
- Modify: `backend/app/services/repositorio.py`
- Create: `backend/app/services/materiais.py`
- Test: `backend/tests/test_repositorio_sqlite.py`

**Interfaces:**
- Consumes: `SessionLocal`, `MaterialDB`, `AdaptacaoPacote`.
- Produces: `salvar_pacote(pacote: AdaptacaoPacote) -> None`, `obter_pacote(adaptacao_id: str) -> AdaptacaoPacote | None`, `listar_pacotes() -> list[AdaptacaoPacote]` com assinaturas atuais preservadas; `material_de_pacote(session, pacote) -> MaterialDB`; `pacote_de_material(row) -> AdaptacaoPacote`; fixtures pytest `pacote_exemplo` e `semear_material(visibilidade="rascunho", **campos) -> str`.

- [x] **Step 1: Escrever o teste que falha**

```python
def test_salvar_pacote_cria_material_rascunho_e_sobrevive_a_nova_sessao(pacote_exemplo):
    repositorio.salvar_pacote(pacote_exemplo)
    with SessionLocal() as nova:
        row = nova.get(MaterialDB, pacote_exemplo.adaptacao_id)
        assert row.visibilidade == "rascunho"
        assert row.formato == pacote_exemplo.metadados.formato_gerado
        assert row.ancoragem_score == pacote_exemplo.avaliacao_qualidade.ancoragem_fonte_score
    assert repositorio.obter_pacote(pacote_exemplo.adaptacao_id).conteudo_adaptado == pacote_exemplo.conteudo_adaptado
```

Segundo teste: salvar de novo preserva `titulo` e `visibilidade` editados, atualizando o pacote. Terceiro: `listar_pacotes` não quebra com `pacote_json = "{"`.

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_repositorio_sqlite.py -v`
Expected: FAIL porque `salvar_pacote` ainda só grava em memória.

- [x] **Step 3: Implementar**

`services/materiais.py` (nesta tarefa apenas criação/leitura do pacote; a serialização de resumo entra na tarefa 3):

```python
def material_de_pacote(session, pacote: AdaptacaoPacote) -> MaterialDB
def pacote_de_material(row: MaterialDB) -> AdaptacaoPacote
```

Preencher as colunas desnormalizadas: `documento_*`, `perfil`, `formato`, `nivel`, `nicho`, `tempo_estimado_minutos`, `ancoragem_score`, `status_upload`, `conceitos_chave_json` (`json.dumps`), `oci_objeto_id`, `pacote_json` (`pacote.model_dump_json()`). `titulo` padrão = `pacote.conteudo_adaptado.titulo[:150]`.

Em `repositorio.py`, manter `_jobs` em memória e trocar `_pacotes` por acesso ao banco. `salvar_pacote` abre uma sessão, faz upsert por `adaptacao_id`, preservando `titulo`/`visibilidade` quando a linha já existe, e faz commit. `obter_pacote`/`listar_pacotes` leem `pacote_json` e validam com `AdaptacaoPacote.model_validate_json`. Nenhuma listagem chama `pacote_de_material`.

Adicionar em `tests/conftest.py` a fixture `pacote_exemplo` (3 flashcards, scores, OCI `concluido`) e a factory `semear_material(visibilidade="rascunho", **campos) -> str`, que grava via `db_session` e devolve o `material_id`.

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_repositorio_sqlite.py backend/tests/api/test_rotas.py -v`
Expected: PASS; `/adaptacoes` continua vazio antes de semear e lê o banco depois.

- [x] **Step 5: Commit**

```bash
git add backend/app/services backend/tests
git commit -m "feat(backend): persiste pacotes em SQLite e cria material rascunho automaticamente"
```

---

### Task 3: API de materiais e remoção no OCI

**Files:**
- Create: `backend/app/models/materiais.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/services/materiais.py`
- Create: `backend/app/api/v1/routers/materiais.py`
- Modify: `backend/app/services/oci.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_materiais.py`

**Interfaces:**
- Consumes: `MaterialDB`, `resumo_de_material`, `pacote_de_material`, `get_db`.
- Produces: schemas `VisibilidadeMaterial`, `MaterialResumo`, `MaterialDetalhe`, `MaterialAtualizacao`, `PaginaMateriais`, `RemocaoMaterialResposta`; `resumo_de_material(row) -> MaterialResumo`; `remover_objeto(objeto_id: str) -> bool`; rotas `GET /api/v1/materiais`, `GET /api/v1/materiais/{id}`, `PATCH /api/v1/materiais/{id}`, `DELETE /api/v1/materiais/{id}`.

- [x] **Step 1: Escrever o teste que falha**

```python
def test_listar_materiais_nao_quebra_com_pacote_corrompido(cliente, db_session, semear_material):
    semear_material(visibilidade="publicado")
    db_session.execute(text("UPDATE materiais SET pacote_json='{'"))
    db_session.commit()
    resp = cliente.get("/api/v1/materiais")
    assert resp.status_code == 200
    assert resp.json()["itens"][0]["visibilidade"] == "publicado"

def test_patch_rejeita_campo_de_conteudo(cliente, semear_material):
    mid = semear_material()
    resp = cliente.patch(f"/api/v1/materiais/{mid}", json={"conteudo_adaptado": {}})
    assert resp.status_code == 422
    assert resp.json()["erro"]["codigo"] == "VALIDACAO"

def test_delete_material_informa_falha_oci(cliente, semear_material, monkeypatch):
    mid = semear_material()
    monkeypatch.setattr("app.api.v1.routers.materiais.remover_objeto", lambda _: False)
    resp = cliente.delete(f"/api/v1/materiais/{mid}")
    assert resp.status_code == 200
    assert resp.json()["oci_removido"] is False
    assert cliente.get(f"/api/v1/materiais/{mid}").status_code == 404
```

Cobrir também filtros `q`, `formato`, `perfil`, `visibilidade`, `ordenar`, paginação e 404.

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_materiais.py -v`
Expected: FAIL com 404 nas rotas novas.

- [x] **Step 3: Implementar**

Schemas Pydantic idênticos à seção 6.1 da spec. `MaterialAtualizacao` deve ser `model_config = ConfigDict(extra="forbid")` e exigir ao menos um campo. Implementar `resumo_de_material(row)` a partir das colunas (`json.loads(conceitos_chave_json)`), sem abrir `pacote_json`.

Rotas:

```python
router = APIRouter(prefix="/materiais", tags=["materiais"])

@router.get("", response_model=PaginaMateriais)
def listar(...): ...

@router.get("/{material_id}", response_model=MaterialDetalhe)
def obter(...): ...

@router.patch("/{material_id}", response_model=MaterialResumo)
def atualizar(...): ...

@router.delete("/{material_id}", response_model=RemocaoMaterialResposta)
def excluir(...): ...
```

`listar` filtra e ordena em SQL, usando somente colunas; `obter` desserializa o pacote e, em `ValidationError`, lança `HTTPException(500, INTERNO)`. `excluir` guarda `oci_objeto_id`, remove a linha (cascata de vínculos), chama `remover_objeto` e devolve `aviso` quando falso.

Em `services/oci.py`:

```python
def remover_objeto(objeto_id: str) -> bool:
    client, namespace = _cliente_oci()
    if client is None:
        return False
    try:
        client.delete_object(namespace_name=namespace, bucket_name=settings.oci_bucket, object_name=objeto_id)
        return True
    except Exception as exc:
        logger.error("Falha ao remover objeto OCI: %s", exc)
        return False
```

Registrar o router em `main.py` e reexportar os schemas em `models/__init__.py`.

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_materiais.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app
git commit -m "feat(backend): adiciona CRUD de materiais com publicação e exclusão OCI"
```

---

### Task 4: API de alunos

**Files:**
- Create: `backend/app/models/alunos.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/services/alunos.py`
- Create: `backend/app/api/v1/routers/alunos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_alunos.py`

**Interfaces:**
- Consumes: `AlunoDB`, `get_db`.
- Produces: `StatusAluno`, `AlunoCriacao`, `AlunoAtualizacao`, `AlunoResumo`, `PaginaAlunos`; `criar_aluno`, `listar_alunos`, `obter_aluno`, `atualizar_aluno`, `excluir_aluno`; rota `/api/v1/alunos`; fixture pytest `semear_aluno(status="ativo", **campos) -> str`.

- [x] **Step 1: Escrever o teste que falha**

```python
def test_email_duplicado_case_insensitive_retorna_409(cliente):
    cliente.post("/api/v1/alunos", json={"nome": "Ana", "email": "Ana@Exemplo.com"})
    resp = cliente.post("/api/v1/alunos", json={"nome": "Bia", "email": "ana@exemplo.com"})
    assert resp.status_code == 409
    assert resp.json()["erro"]["codigo"] == "EMAIL_JA_CADASTRADO"
    assert resp.json()["erro"]["campos"]["email"]

def test_patch_aluno_e_404(cliente):
    ...
```

Cobrir create 201, normalização para minúsculas, listagem com `q`/`status`/ordenação/paginação, PATCH parcial, DELETE 204, 404 e cascata de vínculos.

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_alunos.py -v`
Expected: FAIL com 404.

- [x] **Step 3: Implementar**

Schemas com `EmailStr`, `nome` 3..120, `status` default `ativo`.
Serviço normaliza `email.strip().lower()`, detecta duplicidade antes do commit e devolve um resultado que o router converte em 409 com `campos.email`.
Listagem usa `LIKE` em nome/e-mail, filtro de status, ordenação permitida e paginação 1..50.
DELETE usa `session.delete` e deixa a cascata do banco remover vínculos.
Adicionar `semear_aluno` em `tests/conftest.py`, gravando via `db_session` e devolvendo `aluno_id`.

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_alunos.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app
git commit -m "feat(backend): adiciona CRUD de alunos sem autenticação"
```

---

### Task 5: API de vínculos aluno ↔ material

**Files:**
- Modify: `backend/app/models/alunos.py`
- Modify: `backend/app/services/alunos.py`
- Modify: `backend/app/api/v1/routers/alunos.py`
- Test: `backend/tests/api/test_vinculos.py`

**Interfaces:**
- Consumes: `VinculoDB`, `MaterialDB`, `AlunoDB`.
- Produces: `VinculoMaterial`, `VinculosAluno`, `AtualizarVinculosInput`; rotas `GET/PUT /api/v1/alunos/{id}/materiais`, `POST/DELETE /api/v1/alunos/{id}/materiais/{material_id}`; helper pytest `vincular(aluno_id, material_id)`.

- [x] **Step 1: Escrever o teste que falha**

```python
def test_put_vinculos_e_atomico(cliente, semear_aluno, semear_material):
    aluno = semear_aluno()
    m1, m2 = semear_material(), semear_material()
    resp = cliente.put(f"/api/v1/alunos/{aluno}/materiais",
                       json={"material_ids": [m1, "INEXISTENTE"]})
    assert resp.status_code == 422
    assert resp.json()["erro"]["campos"]["material_ids"]
    assert cliente.get(f"/api/v1/alunos/{aluno}/materiais").json()["itens"] == []

def test_post_e_delete_de_vinculo_sao_idempotentes(cliente, semear_aluno, semear_material):
    ...
```

Cobrir GET ordenado, POST 201 depois 200, DELETE 204 duas vezes, 404 para aluno/material e cascata.

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_vinculos.py -v`
Expected: FAIL com 404.

- [x] **Step 3: Implementar**

`GET` devolve todos os vínculos (sem paginação), ordenados por `vinculado_em DESC`.
`PUT` valida todos os ids antes de apagar/inserir, dentro de uma transação; deduplica; 422 com `campos.material_ids` se qualquer id não existir.
`POST` devolve 201 na criação e 200 se já existe. `DELETE` devolve 204 idempotente.
Serialização usa `MaterialDB` diretamente, sem abrir `pacote_json`.
Adicionar `vincular(aluno_id, material_id)` em `tests/conftest.py`, inserindo e commitando um `VinculoDB`.

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_vinculos.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app backend/tests/api/test_vinculos.py
git commit -m "feat(backend): adiciona vínculos entre alunos e materiais"
```

---

### Task 6: API do aluno (identificação e catálogo)

**Files:**
- Create: `backend/app/models/aluno_catalogo.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/services/materiais.py`
- Modify: `backend/app/services/alunos.py`
- Create: `backend/app/api/v1/routers/aluno.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_aluno_catalogo.py`

**Interfaces:**
- Consumes: `AlunoDB`, `MaterialDB`, `VinculoDB`, `resumo_de_material`.
- Produces: `IdentificacaoAlunoItem`, `IdentificacaoAlunoResposta`, `ItemCatalogoAluno`, `PaginaCatalogoAluno`; `GET /api/v1/aluno/identificacao`, `GET /api/v1/aluno/materiais`, `GET /api/v1/aluno/materiais/{material_id}`.

- [x] **Step 1: Escrever o teste que falha**

```python
def test_catalogo_so_publicado_e_vinculado(cliente, semear_aluno, semear_material):
    aluno = semear_aluno()
    publicado = semear_material(visibilidade="publicado")
    rascunho = semear_material(visibilidade="rascunho")
    outro = semear_material(visibilidade="publicado")
    vincular(aluno, publicado)
    resp = cliente.get(f"/api/v1/aluno/materiais?aluno_id={aluno}")
    assert [i["material_id"] for i in resp.json()["itens"]] == [publicado]
    assert cliente.get(f"/api/v1/aluno/materiais/{rascunho}?aluno_id={aluno}").status_code == 404
    assert cliente.get(f"/api/v1/aluno/materiais/{outro}?aluno_id={aluno}").status_code == 404

def test_aluno_inativo_recebe_403(cliente, semear_aluno):
    ...
```

Cobrir identificação apenas ativos e sem e-mail, filtros, paginação, 404 de aluno, 403 e os três casos de `MATERIAL_NAO_DISPONIVEL`.

- [x] **Step 2: Rodar para ver falhar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_aluno_catalogo.py -v`
Expected: FAIL com 404.

- [x] **Step 3: Implementar**

Identificação: `SELECT aluno_id, nome FROM alunos WHERE status='ativo' ORDER BY nome`.
Catálogo: `JOIN vinculos` + `WHERE materiais.visibilidade='publicado' AND vinculos.aluno_id=?`, filtros e paginação em SQL; `conceitos_chave` vem de `json.loads(conceitos_chave_json)[:6]`.
Detalhe: verifica aluno ativo, vínculo e publicação; qualquer falha → `404 MATERIAL_NAO_DISPONIVEL`. Não usar `pacote_json` na listagem; o detalhe usa `pacote_de_material`.
Registrar o router em `main.py`.

- [x] **Step 4: Rodar e confirmar**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/api/test_aluno_catalogo.py -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app backend/tests/api/test_aluno_catalogo.py
git commit -m "feat(backend): adiciona identificação e catálogo somente leitura do aluno"
```

---

### Task 7: Contrato frontend de alunos e vínculos

**Files:**
- Modify: `frontend/src/types/schemas.ts`
- Modify: `frontend/src/types/novamente.ts`
- Modify: `frontend/src/services/api/NovaMenteApi.ts`
- Modify: `frontend/src/services/api/endpoints.ts`
- Modify: `frontend/src/services/api/httpApiClient.ts`
- Create: `frontend/src/mocks/estadoCatalogo.ts`
- Create: `frontend/src/mocks/handlers/alunos.ts`
- Modify: `frontend/src/mocks/handlers/index.ts`
- Create: `frontend/src/mocks/fixtures/alunos.json`
- Test: `frontend/src/services/api/httpApiClient.alunos.test.ts`
- Test: `frontend/src/mocks/estadoCatalogo.test.ts`

**Interfaces:**
- Consumes: `httpApiClient`, `NovaMenteApi`.
- Produces: `StatusAluno`, `AlunoCriacao`, `AlunoAtualizacao`, `AlunoResumo`, `PaginaAlunos`, `VinculoMaterial`, `VinculosAluno`, `AtualizarVinculosInput`; métodos `listarAlunos`, `criarAluno`, `obterAluno`, `atualizarAluno`, `excluirAluno`, `listarVinculos`, `substituirVinculos`, `adicionarVinculo`, `removerVinculo`; estado mock `listarAlunosMock`, `criarAlunoMock`, etc.

- [x] **Step 1: Escrever o teste que falha**

```ts
it('cria aluno e envia o corpo normalizado', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({ aluno_id: 'A1', nome: 'Ana', email: 'ana@exemplo.com', status: 'ativo', total_materiais: 0, criado_em: ISO, atualizado_em: ISO }, 201));
  vi.stubGlobal('fetch', fetchMock);
  const aluno = await httpApiClient.criarAluno({ nome: 'Ana', email: 'ana@exemplo.com' });
  expect(aluno.aluno_id).toBe('A1');
  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/alunos');
});

it('excluirAluno aceita 204 sem corpo', async () => { ... });
```

Testar também 409 com `campos.email`, paginação e os quatro endpoints de vínculo (incluindo DELETE 204).

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.alunos.test.ts`
Expected: FAIL com `listarAlunos is not a function`.

- [x] **Step 3: Implementar**

Adicionar schemas zod estritos em `schemas.ts` e reexports em `novamente.ts`.
Adicionar as URLs:

```ts
alunos: `${BASE}/alunos`,
aluno: (id: string) => `${BASE}/alunos/${id}`,
alunoMateriais: (id: string) => `${BASE}/alunos/${id}/materiais`,
alunoVinculo: (id: string, materialId: string) => `${BASE}/alunos/${id}/materiais/${materialId}`,
```

`httpApiClient` ganha os métodos. Criar helper `pedirSemCorpo(caminho, init)` para 204:

```ts
async function pedirSemCorpo(caminho: string, init?: RequestInit): Promise<void> {
  const resposta = await fetch(caminho, init);
  if (!resposta.ok) throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
}
```

Mocks: `estadoCatalogo.ts` mantém arrays em memória, `limparEstadoCatalogo()` e operações CRUD. Semear 6 alunos de `alunos.json` (um inativo). Handlers MSW replicam todas as rotas e erros 404/409/422.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.alunos.test.ts src/mocks/estadoCatalogo.test.ts`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/types frontend/src/services frontend/src/mocks
git commit -m "feat(frontend): adiciona contrato e mocks de alunos e vínculos"
```

---

### Task 8: Contrato frontend de materiais

**Files:**
- Modify: `frontend/src/types/schemas.ts`
- Modify: `frontend/src/types/novamente.ts`
- Modify: `frontend/src/services/api/NovaMenteApi.ts`
- Modify: `frontend/src/services/api/endpoints.ts`
- Modify: `frontend/src/services/api/httpApiClient.ts`
- Modify: `frontend/src/mocks/estadoCatalogo.ts`
- Create: `frontend/src/mocks/handlers/materiais.ts`
- Modify: `frontend/src/mocks/handlers/index.ts`
- Create: `frontend/src/mocks/fixtures/materiais.json`
- Test: `frontend/src/services/api/httpApiClient.materiais.test.ts`

**Interfaces:**
- Consumes: `AdaptacaoPacoteSchema`, `estadoCatalogo`.
- Produces: `VisibilidadeMaterial`, `MaterialResumo`, `MaterialDetalhe`, `MaterialAtualizacao`, `PaginaMateriais`, `RemocaoMaterialResposta`; métodos `listarMateriais`, `obterMaterial`, `atualizarMaterial`, `excluirMaterial`.

- [x] **Step 1: Escrever o teste que falha**

```ts
it('valida MaterialDetalhe com pacote', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ material: materialResumo(), pacote: flashcardsFixture })));
  const detalhe = await httpApiClient.obterMaterial('M1');
  expect(detalhe.material.visibilidade).toBe('rascunho');
  expect(detalhe.pacote.adaptacao_id).toBe(flashcardsFixture.adaptacao_id);
});

it('excluirMaterial devolve o resultado da remoção', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ material_id: 'M1', removido: true, oci_removido: false, aviso: 'OCI indisponível' })));
  const r = await httpApiClient.excluirMaterial('M1');
  expect(r.oci_removido).toBe(false);
});
```

Cobrir listagem com filtros/ordenação, PATCH inválido 422 e 404.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.materiais.test.ts`
Expected: FAIL.

- [x] **Step 3: Implementar**

Schemas, tipos, URLs:

```ts
materiais: `${BASE}/materiais`,
material: (id: string) => `${BASE}/materiais/${id}`,
```

Métodos no `NovaMenteApi`/`httpApiClient`.
`estadoCatalogo` ganha materiais semeados a partir de `materiais.json` + pacotes das fixtures existentes; `excluirMaterialMock` remove vínculos; `atualizarMaterialMock` só aceita `titulo`/`visibilidade`.
Handlers MSW cobrem 200, 404 e 422.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.materiais.test.ts`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/types frontend/src/services frontend/src/mocks
git commit -m "feat(frontend): adiciona contrato e mocks de materiais"
```

---

### Task 9: Contrato frontend da área do aluno

**Files:**
- Modify: `frontend/src/types/schemas.ts`
- Modify: `frontend/src/types/novamente.ts`
- Modify: `frontend/src/services/api/NovaMenteApi.ts`
- Modify: `frontend/src/services/api/endpoints.ts`
- Modify: `frontend/src/services/api/httpApiClient.ts`
- Modify: `frontend/src/mocks/estadoCatalogo.ts`
- Create: `frontend/src/mocks/handlers/aluno.ts`
- Modify: `frontend/src/mocks/handlers/index.ts`
- Test: `frontend/src/services/api/httpApiClient.aluno.test.ts`

**Interfaces:**
- Consumes: `MaterialDetalhe`, `estadoCatalogo`.
- Produces: `IdentificacaoAlunoItem`, `IdentificacaoAlunoResposta`, `ItemCatalogoAluno`, `PaginaCatalogoAluno`; métodos `listarIdentificacaoAluno`, `listarCatalogoAluno`, `obterMaterialAluno`.

- [x] **Step 1: Escrever o teste que falha**

```ts
it('lista catálogo com aluno_id e filtros', async () => {
  const fetchMock = vi.fn().mockResolvedValue(json({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 }));
  vi.stubGlobal('fetch', fetchMock);
  await httpApiClient.listarCatalogoAluno('A1', { formato: 'Quiz', q: 'vcn' });
  expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/aluno/materiais?aluno_id=A1');
  expect(fetchMock.mock.calls[0][0]).toContain('formato=Quiz');
});
```

Cobrir 403/404 e `obterMaterialAluno`.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.aluno.test.ts`
Expected: FAIL.

- [x] **Step 3: Implementar**

Schemas e métodos. URLs:

```ts
alunoIdentificacao: `${BASE}/aluno/identificacao`,
alunoCatalogo: `${BASE}/aluno/materiais`,
alunoMaterial: (materialId: string) => `${BASE}/aluno/materiais/${materialId}`,
```

Handlers MSW filtram por aluno ativo + vínculo + publicado, exatamente como o backend. Semear 6 alunos e vínculos para o primeiro aluno ativo.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/services/api/httpApiClient.aluno.test.ts`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src/types frontend/src/services frontend/src/mocks
git commit -m "feat(frontend): adiciona contrato e mocks da área do aluno"
```

---

### Task 10: Landing, separação de rotas e shells

**Files:**
- Delete: `frontend/src/app/page.tsx`
- Delete: `frontend/src/app/historico/page.tsx`
- Delete: `frontend/src/app/resultado/[id]/page.tsx`
- Create: `frontend/src/app/(public)/page.tsx`
- Create: `frontend/src/app/(empresa)/empresa/layout.tsx`
- Create: `frontend/src/app/(empresa)/empresa/page.tsx`
- Create: `frontend/src/app/(empresa)/empresa/gerar/page.tsx`
- Create: `frontend/src/app/(empresa)/empresa/historico/page.tsx`
- Create: `frontend/src/app/(empresa)/empresa/resultado/[id]/page.tsx`
- Create: `frontend/src/app/(empresa)/empresa/materiais/page.tsx` (placeholder)
- Create: `frontend/src/app/(empresa)/empresa/alunos/page.tsx` (placeholder)
- Create: `frontend/src/app/(aluno)/aluno/layout.tsx`
- Create: `frontend/src/app/(aluno)/aluno/page.tsx` (placeholder)
- Create: `frontend/src/components/landing/*`
- Create: `frontend/src/components/layout/LandingHeader.tsx`
- Create: `frontend/src/components/layout/EmpresaShell.tsx`
- Create: `frontend/src/components/layout/EmpresaHeader.tsx`
- Create: `frontend/src/components/layout/AlunoShell.tsx`
- Create: `frontend/src/components/layout/AlunoHeader.tsx`
- Create: `frontend/src/components/layout/EmConstrucao.tsx`
- Create: `frontend/src/lib/rotas.ts`
- Modify: `frontend/src/components/layout/AppShell.tsx` (remover após migração)
- Modify: `frontend/src/components/layout/Header.tsx` (remover após migração)
- Modify: `frontend/src/components/views/GerarView.tsx`
- Modify: `frontend/src/components/views/HistoricoView.tsx`
- Modify: `frontend/src/features/adaptations/useAdaptationHistory.ts`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/next.config.ts`
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/components/landing/LandingPage.test.tsx`
- Test: `frontend/src/components/views/HistoricoView.test.tsx` (atualizar expectativas)

**Interfaces:**
- Consumes: `GerarView`, `HistoricoView`, `ResultadoView`.
- Produces: `ROTAS` com `landing`, `empresaGerar`, `empresaHistorico`, `empresaResultado(id)`, `empresaMateriais`, `empresaAlunos`, `empresaAluno(id)`, `aluno`, `alunoMaterial(id)`; `LandingPage`, `LandingHeader`, `EmpresaShell`, `EmpresaHeader`, `AlunoShell`, `AlunoHeader`; redirects de `/historico` e `/resultado/:id`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
// LandingPage.test.tsx
it('apresenta a proposta e os dois CTAs', () => {
  render(<SkinProvider><LandingPage /></SkinProvider>);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/material didático/i);
  expect(screen.getByRole('link', { name: /área da empresa/i })).toHaveAttribute('href', '/empresa/gerar');
  expect(screen.getByRole('link', { name: /sou aluno/i })).toHaveAttribute('href', '/aluno');
  for (const titulo of [/flashcards/i, /quiz/i, /tutorial/i, /resumo executivo/i]) {
    expect(screen.getAllByText(titulo).length).toBeGreaterThan(0);
  }
});
```

Atualizar `HistoricoView.test.tsx`: esperar `href="/empresa/resultado/id-1"` e `replace('/empresa/historico...')`.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/components/landing/LandingPage.test.tsx src/components/views/HistoricoView.test.tsx`
Expected: FAIL (LandingPage inexistente e rotas antigas).

- [x] **Step 3: Implementar**

Criar `lib/rotas.ts`:

```ts
export const ROTAS = {
  landing: '/',
  empresaGerar: '/empresa/gerar',
  empresaHistorico: '/empresa/historico',
  empresaResultado: (id: string) => `/empresa/resultado/${id}`,
  empresaMateriais: '/empresa/materiais',
  empresaAlunos: '/empresa/alunos',
  empresaAluno: (id: string) => `/empresa/alunos/${id}`,
  aluno: '/aluno',
  alunoMaterial: (id: string) => `/aluno/materiais/${id}`,
} as const;
```

Landing: compor `LandingPage` com as 10 seções da spec, copy em `M.landing`, `data-tour="landing-hero"` e `data-tour="landing-publicos"`. Header com âncoras, `SkinSwitcher`, "Sou aluno" e "Área da empresa". O CTA "Ver tour" entra só na tarefa 15, junto com o `TourLauncher`. Metadata em `(public)/page.tsx`.

`EmpresaShell`/`EmpresaHeader`: migrar `AppShell`/`Header`; nav Gerar/Histórico/Materiais/Alunos, link "Área do aluno", `SkinSwitcher`, `data-tour="empresa-nav"`. `(empresa)/empresa/page.tsx` usa `redirect(ROTAS.empresaGerar)`.

As páginas de materiais, alunos e aluno são criadas como placeholders com `EmConstrucao` para que nenhum link do header ou da landing fique morto nesta entrega intermediária. As tarefas 11, 12 e 14 substituem os placeholders.

`AlunoShell`/`AlunoHeader`: logo, "Trocar aluno", `SkinSwitcher`, link "Área da empresa". Nesta tarefa, sem nome do aluno e sem `TourLauncher`; a tarefa 14 adiciona o nome e a tarefa 15 adiciona o tour.

Mover as páginas e atualizar todos os links/`router.replace` com `ROTAS` (grep por `/historico`, `/resultado` e `href="/"`). Em `next.config.ts`:

```ts
async redirects() {
  return [
    { source: '/historico', destination: '/empresa/historico', permanent: true },
    { source: '/resultado/:id', destination: '/empresa/resultado/:id', permanent: true },
  ];
}
```

`/empresa/gerar` usa `GerarView`; `/empresa/historico` usa `HistoricoView`; `/empresa/resultado/[id]` usa `ResultadoView`.
Adicionar `robots: { index: false }` nos layouts de empresa e aluno.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm run typecheck && npm run lint && npm test -- src/components/landing/LandingPage.test.tsx src/components/views/HistoricoView.test.tsx && npm run build`
Expected: PASS; build contém `/`, `/empresa/gerar`, `/empresa/historico`, `/empresa/resultado/[id]`, `/aluno`.

- [x] **Step 5: Commit**

```bash
git add frontend/src frontend/next.config.ts
git commit -m "feat(frontend): adiciona landing e separa as áreas da empresa e do aluno"
```

---

### Task 11: Tela de materiais e resultado por material

**Files:**
- Create: `frontend/src/features/materiais/useMateriais.ts`
- Create: `frontend/src/components/materiais/MateriaisView.tsx`
- Create: `frontend/src/components/materiais/MaterialCard.tsx`
- Create: `frontend/src/components/materiais/MaterialEditDialog.tsx`
- Create: `frontend/src/components/materiais/MaterialDeleteDialog.tsx`
- Modify: `frontend/src/app/(empresa)/empresa/materiais/page.tsx` (substitui placeholder)
- Create: `frontend/src/features/materiais/useMaterial.ts`
- Modify: `frontend/src/components/views/ResultadoView.tsx`
- Modify: `frontend/src/components/views/ResultadoHeader.tsx`
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/components/materiais/MateriaisView.test.tsx`
- Test: `frontend/src/features/materiais/useMateriais.test.tsx`
- Test: `frontend/src/components/views/ResultadoView.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `ROTAS`, `MaterialResumo`, `MaterialDetalhe`.
- Produces: `useMateriais()` (filtros via URL: `q`, `formato`, `perfil`, `visibilidade`, `ordenar`, `pagina`); `useAtualizarMaterial()`; `useExcluirMaterial()`; `useMaterial(materialId)`; `MateriaisView`, `MaterialEditDialog`, `MaterialDeleteDialog`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
it('publica um rascunho', async () => {
  const atualizar = vi.fn().mockResolvedValue({ ...material(), visibilidade: 'publicado' });
  renderComApi(<MateriaisView />, { listarMateriais: vi.fn().mockResolvedValue(pagina([material()])), atualizarMaterial: atualizar });
  await userEvent.click(await screen.findByRole('button', { name: /publicar/i }));
  expect(atualizar).toHaveBeenCalledWith('M1', { visibilidade: 'publicado' });
});

it('exclui com confirmação e mostra aviso de OCI', async () => { ... });
```

`ResultadoView.test.tsx`: `obterMaterial` é chamado com o id; título editado aparece; 404 mostra link para `/empresa/materiais`.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/components/materiais/MateriaisView.test.tsx src/components/views/ResultadoView.test.tsx`
Expected: FAIL.

- [x] **Step 3: Implementar**

`useMateriais` espelha `useAdaptationHistory` (debounce 300 ms, URL validada, `LIMITES.paginaPadrao`, `staleTime` 30 s) e usa `PaginaMateriais` do tipo. Mutações invalidam `['materiais']`, `['material', id]`, `['aluno-catalogo']` e `['vinculos']`.

`MateriaisView`: grade responsiva, filtros, skeleton, vazio com CTA para `ROTAS.empresaGerar`, erro com retry, paginação, `data-tour="empresa-materiais-lista"`. Ações: Abrir → `ROTAS.empresaResultado(material_id)`, Editar, Publicar/Despublicar (otimista com rollback), Excluir com confirmação. Toast `role="status"` para sucesso e aviso de OCI.

`ResultadoView` passa a usar `useMaterial(id)` e a exibir `material.titulo`, badge de visibilidade e ações Editar/Publicar; o corpo continua com `pacote`, `ContentRenderer` e `OCIPanel`. O estado 404 aponta para `/empresa/materiais`.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/components/materiais/MateriaisView.test.tsx src/features/materiais/useMateriais.test.tsx src/components/views/ResultadoView.test.tsx`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): adiciona gestão de materiais e resultado por catálogo"
```

---

### Task 12: Tela de alunos (lista, criação, edição e exclusão)

**Files:**
- Create: `frontend/src/features/alunos/useAlunos.ts`
- Create: `frontend/src/components/alunos/AlunosView.tsx`
- Create: `frontend/src/components/alunos/AlunoCard.tsx`
- Create: `frontend/src/components/alunos/AlunoFormDialog.tsx`
- Create: `frontend/src/components/alunos/AlunoDeleteDialog.tsx`
- Modify: `frontend/src/app/(empresa)/empresa/alunos/page.tsx` (substitui placeholder)
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/components/alunos/AlunosView.test.tsx`
- Test: `frontend/src/features/alunos/useAlunos.test.tsx`

**Interfaces:**
- Consumes: `AlunoCriacao`, `AlunoAtualizacao`, `PaginaAlunos`, `ROTAS`.
- Produces: `useAlunos()` (filtros `q`, `status`, `ordenar`, `pagina`); `useAluno(alunoId)`; `useCriarAluno()`, `useAtualizarAluno()`, `useExcluirAluno()`; `AlunosView`, `AlunoFormDialog`, `AlunoDeleteDialog`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
it('mapeia 409 de e-mail para o campo', async () => {
  const criar = vi.fn().mockRejectedValue(new ErroApi({ codigo: 'EMAIL_JA_CADASTRADO', mensagem: 'E-mail já cadastrado.', campos: { email: 'E-mail já cadastrado.' } }, 409));
  renderComApi(<AlunosView />, { listarAlunos: vi.fn().mockResolvedValue(pagina([])), criarAluno: criar });
  await userEvent.click(screen.getByRole('button', { name: /novo aluno/i }));
  await userEvent.type(screen.getByLabelText(/nome/i), 'Ana');
  await userEvent.type(screen.getByLabelText(/e-mail/i), 'ana@exemplo.com');
  await userEvent.click(screen.getByRole('button', { name: /salvar/i }));
  expect(await screen.findByText('E-mail já cadastrado.')).toBeInTheDocument();
});

it('exclui com confirmação e avisa sobre vínculos', async () => { ... });
```

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/components/alunos/AlunosView.test.tsx src/features/alunos/useAlunos.test.tsx`
Expected: FAIL.

- [x] **Step 3: Implementar**

`useAlunos` espelha os filtros URL e pagina. Mutações invalidam `['alunos']`, `['aluno', id]` e `['vinculos', id]`.
`AlunosView`: tabela desktop/cards mobile, filtros, estados, `data-tour="empresa-alunos-lista"`. `AlunoFormDialog` usa RHF + zod (`nome` 3..120, `email` válido, `status`), com `aria-invalid`/`aria-describedby`; erro 409 vai para `setError('email')`. `AlunoDeleteDialog` confirma e avisa que vínculos serão removidos. Card tem link "Materiais" → `ROTAS.empresaAluno(id)`.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/components/alunos/AlunosView.test.tsx src/features/alunos/useAlunos.test.tsx`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): adiciona CRUD de alunos"
```

---

### Task 13: Detalhe do aluno e painel de vínculos

**Files:**
- Create: `frontend/src/features/alunos/useVinculos.ts`
- Create: `frontend/src/components/alunos/AlunoDetalheView.tsx`
- Create: `frontend/src/components/alunos/VinculosPanel.tsx`
- Create: `frontend/src/app/(empresa)/empresa/alunos/[id]/page.tsx`
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/components/alunos/VinculosPanel.test.tsx`
- Test: `frontend/src/components/alunos/AlunoDetalheView.test.tsx`

**Interfaces:**
- Consumes: `useAluno`, `useMateriais`, `useVinculos`, `adicionarVinculo`, `removerVinculo`.
- Produces: `useVinculos(alunoId)`; `useAplicarVinculos(alunoId)` com mutation `{ adicionar: string[]; remover: string[] }`; `VinculosPanel({ alunoId, aplicar? })`, onde `aplicar` permite injetar a mutation nos testes; `AlunoDetalheView`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
it('não desvincula material escondido pelo filtro', async () => {
  const aplicar = vi.fn().mockResolvedValue(undefined);
  renderComApi(<VinculosPanel alunoId="A1" aplicar={aplicar} />, {
    listarMateriais: vi.fn().mockResolvedValue(pagina([material({ material_id: 'M2' })])),
    listarVinculos: vi.fn().mockResolvedValue({ aluno_id: 'A1', itens: [vinculo('M1'), vinculo('M2')] }),
  });
  await screen.findByText('Material M2');
  await userEvent.click(screen.getByRole('checkbox', { name: /material m2/i }));
  await userEvent.click(screen.getByRole('button', { name: /salvar vínculos/i }));
  expect(aplicar).toHaveBeenCalledWith({ adicionar: [], remover: ['M2'] });
  expect(aplicar).not.toHaveBeenCalledWith(expect.objectContaining({ remover: ['M1'] }));
});
```

Segundo teste: marcar material não vinculado envia `adicionar`; falha parcial mostra aviso e refaz as consultas.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/components/alunos/VinculosPanel.test.tsx src/components/alunos/AlunoDetalheView.test.tsx`
Expected: FAIL.

- [x] **Step 3: Implementar**

`VinculosPanel` carrega `useMateriais` (página 12) e `useVinculos` (lista completa). Estado local guarda `adicionar`/`remover`; checkbox alterna apenas o material visível. Salvar chama `aplicar` com a diferença e depois invalida `['vinculos', alunoId]`, `['materiais']` e `['aluno', alunoId]`. Em erro, refetch e `role="alert"`.
`AlunoDetalheView` mostra dados, editar/excluir, `VinculosPanel`, link de volta com query. `data-tour` não é necessário aqui.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/components/alunos/VinculosPanel.test.tsx src/components/alunos/AlunoDetalheView.test.tsx`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): adiciona detalhe do aluno e gestão de vínculos"
```

---

### Task 14: Área do aluno (identificação, catálogo e visualização)

**Files:**
- Create: `frontend/src/features/aluno/useIdentidadeAluno.ts`
- Create: `frontend/src/features/aluno/useCatalogoAluno.ts`
- Create: `frontend/src/features/aluno/useMaterialAluno.ts`
- Create: `frontend/src/components/aluno/IdentificacaoAluno.tsx`
- Create: `frontend/src/components/aluno/CatalogoAlunoView.tsx`
- Create: `frontend/src/components/aluno/AlunoMaterialView.tsx`
- Modify: `frontend/src/app/(aluno)/aluno/page.tsx` (substitui placeholder)
- Create: `frontend/src/app/(aluno)/aluno/materiais/[id]/page.tsx`
- Modify: `frontend/src/components/layout/AlunoHeader.tsx`
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/components/aluno/IdentificacaoAluno.test.tsx`
- Test: `frontend/src/components/aluno/CatalogoAlunoView.test.tsx`
- Test: `frontend/src/components/aluno/AlunoMaterialView.test.tsx`
- Test: `frontend/src/features/aluno/useIdentidadeAluno.test.tsx`

**Interfaces:**
- Consumes: `listarIdentificacaoAluno`, `listarCatalogoAluno`, `obterMaterialAluno`, `ContentRenderer`.
- Produces: `useIdentidadeAluno()` `{ aluno, identificar, trocarAluno, limpar }`; `useCatalogoAluno()`; `useMaterialAluno(materialId)`; `IdentificacaoAluno`, `CatalogoAlunoView`, `AlunoMaterialView`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
it('identifica, persiste e mostra o catálogo', async () => {
  renderComApi(<AreaAluno />, {
    listarIdentificacaoAluno: vi.fn().mockResolvedValue([{ aluno_id: 'A1', nome: 'Ana' }]),
    listarCatalogoAluno: vi.fn().mockResolvedValue(paginaCatalogo([itemCatalogo()])),
  });
  await userEvent.click(await screen.findByRole('button', { name: /ana/i }));
  await userEvent.click(screen.getByRole('button', { name: /entrar/i }));
  expect(await screen.findByText('Material de VCN')).toBeInTheDocument();
  expect(localStorage.getItem('novamente.aluno')).toContain('A1');
});

it('403 na sessão limpa a identidade e volta ao cartão', async () => { ... });
it('não renderiza OCI nem exportação no material do aluno', async () => { ... });
```

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/components/aluno src/features/aluno`
Expected: FAIL.

- [x] **Step 3: Implementar**

`useIdentidadeAluno` lê/grava `novamente.aluno` (`{ aluno_id, nome }`), valida JSON e expõe `limpar` em 403/404.
`IdentificacaoAluno`: busca por nome, lista de ativos, botão "Entrar", aviso "Identificação sem senha nesta versão", estado sem alunos com link para `/empresa/alunos`, `data-tour="aluno-identificacao"`.
`CatalogoAlunoView`: saudação, grade, busca com debounce, filtro de formato, paginação, estados, `data-tour="aluno-catalogo"`; cards levam a `ROTAS.alunoMaterial(id)`.
`AlunoMaterialView`: usa `ContentRenderer`, badges, tempo, voltar ao catálogo; não renderiza `OCIPanel`, `ExportMenu` nem download; 404 mostra "Este material não está disponível.".
`AlunoHeader` passa a exibir o nome e "Trocar aluno" (limpa e volta a `/aluno`).

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/components/aluno src/features/aluno`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): adiciona identificação, catálogo e leitura do material pelo aluno"
```

---

### Task 15: Tour guiado

**Files:**
- Modify: `frontend/package.json` e lockfile (`driver.js`)
- Create: `frontend/src/features/tour/driver.ts`
- Create: `frontend/src/features/tour/useTour.ts`
- Create: `frontend/src/components/layout/TourLauncher.tsx`
- Modify: `frontend/src/components/layout/LandingHeader.tsx`
- Modify: `frontend/src/components/layout/EmpresaHeader.tsx`
- Modify: `frontend/src/components/layout/AlunoHeader.tsx`
- Modify: `frontend/src/components/landing/LandingPage.tsx`
- Modify: `frontend/src/components/landing/LandingPublicos.tsx`
- Modify: `frontend/src/components/views/GerarView.tsx`
- Modify: `frontend/src/components/views/HistoricoView.tsx`
- Modify: `frontend/src/components/materiais/MateriaisView.tsx`
- Modify: `frontend/src/components/alunos/AlunosView.tsx`
- Modify: `frontend/src/components/aluno/IdentificacaoAluno.tsx`
- Modify: `frontend/src/components/aluno/CatalogoAlunoView.tsx`
- Modify: `frontend/src/lib/mensagens.ts`
- Test: `frontend/src/features/tour/useTour.test.tsx`
- Test: `frontend/src/components/layout/TourLauncher.test.tsx`

**Interfaces:**
- Consumes: `ROTAS`, `router.push`.
- Produces: `iniciarTour(origem: 'landing' | 'empresa' | 'aluno' | 'completo'): Promise<void>`; `deveAutoIniciar(): boolean`; `marcarConcluido(): void`; `useTour()`; `TourLauncher({ origem, iniciar? })`; `criarDriver(passos)` em `driver.ts`.

- [x] **Step 1: Escrever o teste que falha**

```tsx
it('auto-inicia uma única vez em /empresa/gerar', async () => {
  mocks.pathname = '/empresa/gerar';
  localStorage.clear();
  const iniciar = vi.fn().mockResolvedValue(undefined);
  render(<TourLauncher origem="empresa" iniciar={iniciar} />);
  await vi.waitFor(() => expect(iniciar).toHaveBeenCalledWith('empresa'));
  expect(localStorage.getItem('novamente.tour')).toContain('versao');
});

it('pula passo cujo alvo não existe e continua', async () => {
  const passos = [
    { element: '[data-tour="a"]', popover: { title: 'A' } },
    { element: '[data-tour="ausente"]', popover: { title: 'Ausente' } },
    { element: '[data-tour="b"]', popover: { title: 'B' } },
  ];
  const disponiveis = await filtrarPassosDisponiveis(passos, (s) => s !== '[data-tour="ausente"]');
  expect(disponiveis.map((p) => p.element)).toEqual(['[data-tour="a"]', '[data-tour="b"]']);
});
```

Cobrir: subconjuntos por origem; `?tour=1` completo; `Esc`/pular persiste; não auto-inicia em `/aluno`.

- [x] **Step 2: Rodar para ver falhar**

Run: `cd frontend && npm test -- src/features/tour src/components/layout/TourLauncher.test.tsx`
Expected: FAIL.

- [x] **Step 3: Implementar**

Instalar `driver.js` (1.x). `useTour` importa `./driver` de forma dinâmica (`await import('./driver')`); `driver.ts` importa `driver.js/dist/driver.css`, faz `const { driver } = await import('driver.js')` e expõe `criarDriver(passos)`, `aguardarElemento(seletor, 2500)` com `MutationObserver`/timeout e `filtrarPassosDisponiveis(passos, existe = (s) => !!document.querySelector(s))`. Assim o wrapper, a lib e o CSS ficam fora do bundle inicial. `useTour` monta os 8 passos e os subconjuntos:

| Origem | Passos |
|---|---|
| `landing` | 1–8 |
| `empresa` | 3–8 |
| `aluno` | 8 |
| `completo` (`?tour=1`) | 1–8 |

Navegação com `router.push`; passo sem alvo é removido antes de `drive`. Persistência `novamente.tour = { versao: 1, concluido_em: ISO }`. Auto-start apenas em `/empresa/gerar`, 600 ms, uma vez; cancela se a rota mudar antes do início. `TourLauncher` renderiza botão "Ver tour" com `aria-label` e chama `iniciar ?? iniciarTour(origem)`; o prop `iniciar` existe para testes e para o auto-start injetável.

Adicionar `TourLauncher` ao `LandingHeader` (`origem="landing"`), `EmpresaHeader` (`origem="empresa"`) e `AlunoHeader` (`origem="aluno"`), e o auto-start no `EmpresaHeader`.

Adicionar os `data-tour` exatos da spec: `landing-hero`, `landing-publicos`, `empresa-nav`, `empresa-gerar-form`, `empresa-historico-lista`, `empresa-materiais-lista`, `empresa-alunos-lista`, `aluno-identificacao`, `aluno-catalogo`.

- [x] **Step 4: Rodar e confirmar**

Run: `cd frontend && npm test -- src/features/tour src/components/layout/TourLauncher.test.tsx && npm run build`
Expected: PASS; `driver.js` não aparece no bundle inicial.

- [x] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src
git commit -m "feat(frontend): adiciona tour guiado nas telas reais"
```

---

### Task 16: E2E, acessibilidade, documentação e verificação final

**Files:**
- Create: `frontend/e2e/6-landing-empresa.spec.ts`
- Create: `frontend/e2e/7-aluno-catalogo.spec.ts`
- Create: `frontend/e2e/8-tour.spec.ts`
- Modify: `frontend/e2e/4-acessibilidade.spec.ts`
- Modify: `frontend/e2e/1-gerar-flashcards.spec.ts`
- Modify: `frontend/e2e/3-historico-exportacao.spec.ts`
- Modify: `frontend/README.md`
- Modify: `backend/README.md`
- Modify: `README.md`
- Test: os próprios E2E.

**Interfaces:**
- Consumes: tudo das tarefas anteriores.
- Produces: suíte E2E verde, axe sem violação crítica, documentação atualizada.

- [x] **Step 1: Escrever os E2E**

`6-landing-empresa.spec.ts`:
1. Abre `/`, confere hero, CTAs e os quatro formatos.
2. "Área da empresa" → `/empresa/gerar`.
3. Gera material pelo cenário de demonstração, chega ao resultado.
4. Volta a `/empresa/materiais`, publica o material e edita o título.
5. `/empresa/alunos`, cria aluno, abre detalhe, vincula o material publicado.
6. Volta a `/empresa/materiais` e exclui o material, conferindo o aviso de OCI.

`7-aluno-catalogo.spec.ts`:
1. Cria aluno + material publicado + vínculo via UI/mock.
2. Abre `/aluno`, identifica, vê o material.
3. Abre o material e responde o quiz/flashcards.
4. Tenta abrir por URL um rascunho e um material não vinculado → estado indisponível.
5. "Trocar aluno" limpa a sessão.

`8-tour.spec.ts`:
1. Primeira visita a `/empresa/gerar` auto-inicia.
2. Recarregar não auto-inicia de novo.
3. "Ver tour" reinicia.
4. `/aluno?tour=1` não navega para `/empresa`.

Atualizar os E2E existentes para as rotas novas (`/empresa/gerar`, `/empresa/historico`, `/empresa/resultado/...`).

- [x] **Step 2: Rodar e ver falhar**

Run: `cd frontend && npm run e2e`
Expected: FAIL nos specs novos antes dos ajustes finais.

- [x] **Step 3: Corrigir e cobrir acessibilidade**

Adicionar às rotas `/`, `/empresa/materiais`, `/empresa/alunos`, `/aluno`, `/aluno/materiais/[id]` a checagem `@axe-core/playwright` sem violações críticas. Ajustar foco, rótulos, contraste e diálogos até passar.

Atualizar READMEs:

- Backend: banco em `backend/data/novamente.db`, `DATABASE_URL`, novas rotas, como rodar testes e semear via geração.
- Frontend: mapa de rotas `/`, `/empresa/*`, `/aluno/*`; tour; modo mock; comandos.
- README raiz: nova estrutura de telas e fluxo empresa × aluno.

- [x] **Step 4: Verificação final**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests -v`
Expected: PASS.

Run: `cd frontend && npm run typecheck && npm run lint && npm run test:coverage && npm run build && npm run e2e`
Expected: PASS; cobertura ≥ 80% em `features`/`services`; axe sem violação crítica.

- [x] **Step 5: Commit**

```bash
git add frontend/e2e frontend/README.md backend/README.md README.md
git commit -m "test: cobre landing, empresa, aluno e tour com E2E e acessibilidade"
```

---

## Self-Review

### Cobertura da spec

| Seção da spec | Tarefa |
|---|---|
| Landing e conteúdo | 10 |
| Rotas e redirects | 10 |
| CRUD de materiais | 2, 3, 8, 11 |
| CRUD de alunos | 4, 7, 12 |
| CRUD de vínculos | 5, 7, 13 |
| Área do aluno | 6, 9, 14 |
| SQLite e repositório | 1, 2 |
| Publicação/rascunho | 2, 3, 6 |
| Tour | 15 |
| Acessibilidade/performance | 10, 14, 15, 16 |
| Testes e mocks | 1–16 |
| Documentação | 16 |

### Consistência de tipos

- `material_id` é usado em todas as rotas de material e vínculo; `adaptacao_id` aparece no pacote e é igual a `material_id`.
- Schemas Pydantic e zod usam os mesmos nomes de campo da spec.
- `PaginaMateriais`, `PaginaAlunos`, `PaginaCatalogoAluno` têm os mesmos campos de paginação do contrato existente.
- `VinculosAluno.itens` usa `VinculoMaterial`; o painel compara por `material_id`.

### Riscos de execução

- Rodar `pytest` sem o venv atualizado (SQLAlchemy ausente) falha na tarefa 1; instalar `requirements-dev.txt` antes.
- `driver.js` precisa ser mockado nos testes; o carregamento dinâmico não pode entrar no bundle inicial.
- Testes E2E dependem de MSW semeado; limpar o estado entre specs com `limparEstadoCatalogo()`.
- O banco de teste é temporário por sessão; nunca apontar `DATABASE_URL` para `backend/data/novamente.db` nos testes.
