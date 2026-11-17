# Backend — alterações entregues: landing, empresa e aluno

**Data:** 2026-11-09  
**Branch:** `feat/Landing-page-tour`  
**Spec de referência:** `docs/superpowers/specs/2026-11-09-landing-tour-empresa-aluno-design.md`  
**Escopo deste documento:** somente backend (`backend/`). As mudanças de frontend, E2E e mocks não fazem parte deste handoff.

---

## 1. Resumo executivo

O backend deixou de manter pacotes apenas em memória e passou a persistir o catálogo em **SQLite via SQLAlchemy 2**. Com isso foram entregues:

- Persistência durável de pacotes/material, com criação automática de material em **rascunho** ao fim do pipeline.
- CRUD de **materiais** (listar, detalhar, editar título/visibilidade, excluir com remoção no OCI).
- CRUD de **alunos**, incluindo unicidade de e-mail sem diferenciar caixa.
- CRUD de **vínculos** aluno ↔ material (substituição atômica e operações individuais idempotentes).
- Área do aluno somente leitura: identificação e catálogo filtrados no servidor por aluno **ativo**, material **publicado** e vínculo existente.
- Compatibilidade com as rotas antigas de `adaptacoes`, que agora leem o mesmo banco.

**Fora de escopo e mantido como está:** autenticação, login, token, cookie e sessão. As colunas `owner_id` existem apenas como reserva para a evolução futura e permanecem sempre `NULL`, sem exposição no contrato público.

---

## 2. Dependências e configuração

### 2.1 Novas dependências de produção

Em `backend/requirements.txt`:

```text
email-validator>=2.2,<3
sqlalchemy>=2.0,<3
```

`email-validator` é necessário para o `EmailStr` dos schemas de aluno. `sqlalchemy` sustenta o SQLite.

### 2.2 Nova configuração

Em `backend/app/core/config.py`:

```python
database_url: str = "sqlite:///./data/novamente.db"
```

| Variável | Default | Observação |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/novamente.db` | Caminho relativo ao diretório de execução. `make dev-backend` executa dentro de `backend/`, então o arquivo fica em `backend/data/novamente.db`. |

### 2.3 Ignore de artefatos locais

No `.gitignore` da raiz foram adicionados:

```text
backend/data/*.db
backend/data/*.db-wal
backend/data/*.db-shm
```

### 2.4 Inicialização do banco

- `backend/app/core/db.py` cria o engine com `check_same_thread=False`.
- Ao conectar, aplica `PRAGMA foreign_keys=ON` e `PRAGMA journal_mode=WAL`.
- `SessionLocal`, `Base` e `get_db()` ficam nesse módulo.
- `backend/app/main.py` registra os modelos e executa `Base.metadata.create_all(bind=engine)` no `lifespan`.

> **Atenção:** não há Alembic/migrations nesta entrega. `create_all` apenas cria tabelas ausentes; ele **não altera colunas de tabelas já existentes**. Como o banco é novo nesta fase, o fluxo esperado é criar do zero. Se o time evoluir o schema depois, será necessário introduzir migração ou recriar o arquivo com backup.

---

## 3. Banco de dados

### 3.1 Tabelas criadas

Arquivo: `backend/app/models/db.py`.

```sql
CREATE TABLE alunos (
  aluno_id      TEXT PRIMARY KEY,
  nome          TEXT NOT NULL,
  email         TEXT NOT NULL COLLATE NOCASE UNIQUE,
  status        TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo','inativo')),
  owner_id      TEXT NULL,
  criado_em     TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);

CREATE TABLE materiais (
  material_id             TEXT PRIMARY KEY,
  adaptacao_id            TEXT NOT NULL UNIQUE,
  titulo                  TEXT NOT NULL,
  documento_titulo        TEXT NOT NULL,
  documento_origem        TEXT NOT NULL,
  documento_nome_arquivo  TEXT NULL,
  documento_tamanho_bytes INTEGER NULL,
  perfil                  TEXT NOT NULL,
  formato                 TEXT NOT NULL,
  nivel                   TEXT NOT NULL,
  nicho                   TEXT NOT NULL,
  tempo_estimado_minutos  INTEGER NOT NULL,
  ancoragem_score         REAL NOT NULL,
  status_upload           TEXT NOT NULL CHECK (status_upload IN ('concluido','falha')),
  conceitos_chave_json    TEXT NOT NULL,
  oci_objeto_id           TEXT NOT NULL,
  visibilidade            TEXT NOT NULL DEFAULT 'rascunho'
                          CHECK (visibilidade IN ('rascunho','publicado')),
  pacote_json             TEXT NOT NULL,
  owner_id                TEXT NULL,
  criado_em               TEXT NOT NULL,
  atualizado_em           TEXT NOT NULL
);

CREATE TABLE vinculos (
  aluno_id    TEXT NOT NULL REFERENCES alunos(aluno_id) ON DELETE CASCADE,
  material_id TEXT NOT NULL REFERENCES materiais(material_id) ON DELETE CASCADE,
  criado_em   TEXT NOT NULL,
  PRIMARY KEY (aluno_id, material_id)
);

CREATE INDEX ix_alunos_status ON alunos(status);
CREATE INDEX ix_materiais_visibilidade ON materiais(visibilidade);
CREATE INDEX ix_materiais_formato ON materiais(formato);
CREATE INDEX ix_materiais_ancoragem ON materiais(ancoragem_score);
CREATE INDEX ix_vinculos_material ON vinculos(material_id);
```

### 3.2 Regras importantes do modelo

- IDs são **ULID em texto**.
- `material_id` é **igual** a `adaptacao_id` nesta fase. O material é o registro de catálogo do pacote; os dois campos ficam no contrato para permitir versionamento futuro sem quebrar URLs.
- `email` é gravado normalizado em minúsculas; a coluna `NOCASE UNIQUE` também protege contra duplicidade por caixa.
- `pacote_json` guarda o `AdaptacaoPacote` completo e imutável.
- `titulo` do material é o nome de catálogo. Nasce de `pacote.conteudo_adaptado.titulo` truncado em 150 caracteres; editar o título **não** altera `pacote_json`.
- As colunas desnormalizadas (`documento_*`, `perfil`, `formato`, `nivel`, `nicho`, `tempo_estimado_minutos`, `ancoragem_score`, `status_upload`, `conceitos_chave_json`, `oci_objeto_id`) são cópias do pacote para permitir listagens sem abrir o JSON.
- `visibilidade` nasce `rascunho` quando o pipeline conclui.
- Excluir aluno remove os vínculos em cascata e **não** exclui materiais.
- Excluir material remove os vínculos em cascata.

---

## 4. Arquivos novos e alterados

### 4.1 Novos

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/core/db.py` | Engine, `SessionLocal`, `Base`, `get_db()` e pragmas do SQLite. |
| `backend/app/models/db.py` | Modelos ORM `AlunoDB`, `MaterialDB`, `VinculoDB`. |
| `backend/app/models/materiais.py` | Schemas Pydantic de material e visibilidade. |
| `backend/app/models/alunos.py` | Schemas Pydantic de aluno e vínculo. |
| `backend/app/models/aluno_catalogo.py` | Schemas somente leitura da área do aluno. |
| `backend/app/services/materiais.py` | Conversão pacote ↔ linha, resumos desnormalizados e item de catálogo. |
| `backend/app/services/alunos.py` | Regras de aluno, vínculos e catálogo do aluno. |
| `backend/app/api/v1/routers/materiais.py` | Rotas de materiais da empresa. |
| `backend/app/api/v1/routers/alunos.py` | Rotas de alunos e vínculos. |
| `backend/app/api/v1/routers/aluno.py` | Rotas somente leitura da área do aluno. |

### 4.2 Alterados

| Arquivo | Mudança |
|---|---|
| `backend/app/core/config.py` | Adiciona `database_url`. |
| `backend/app/main.py` | Importa modelos, registra os três routers novos e cria tabelas no `lifespan`. |
| `backend/app/models/__init__.py` | Reexporta os schemas novos sem criar ciclo de importação. |
| `backend/app/services/repositorio.py` | `salvar_pacote`, `obter_pacote` e `listar_pacotes` passam a usar SQLite; jobs continuam em memória; adiciona `listar_resumos()`. |
| `backend/app/services/oci.py` | Adiciona `remover_objeto(objeto_id) -> bool`. |
| `backend/app/api/v1/routers/adaptacoes.py` | `GET /adaptacoes` passa a usar resumos desnormalizados, sem desserializar `pacote_json`. |
| `backend/app/workers/job_worker.py` | O job só é marcado como `succeeded` depois de `salvar_pacote` (commit no banco). |
| `backend/requirements.txt` | `sqlalchemy` e `email-validator`. |
| `.gitignore` | Arquivos `*.db`, `*.db-wal` e `*.db-shm` de `backend/data/`. |

### 4.3 Testes novos

| Arquivo | Testes |
|---|---:|
| `backend/tests/test_db.py` | 2 |
| `backend/tests/test_repositorio_sqlite.py` | 5 |
| `backend/tests/api/test_materiais.py` | 22 |
| `backend/tests/api/test_alunos.py` | 22 |
| `backend/tests/api/test_vinculos.py` | 17 |
| `backend/tests/api/test_aluno_catalogo.py` | 20 |
| **Total novo** | **88** |

`backend/tests/conftest.py` foi ampliado com banco temporário por sessão, fixtures `db_session`, `cliente`, `pacote_exemplo`, `semear_aluno`, `semear_material` e `vincular`.

---

## 5. Persistência do pipeline

Fluxo após a geração:

1. O worker executa o pipeline e recebe um `AdaptacaoPacote`.
2. Chama `repositorio.salvar_pacote(pacote)`.
3. `material_de_pacote()` faz upsert por `adaptacao_id`:
   - cria a linha com `material_id = adaptacao_id`, `titulo = conteudo_adaptado.titulo[:150]` e `visibilidade = "rascunho"`;
   - atualiza `pacote_json` e todas as colunas desnormalizadas;
   - em uma linha existente, preserva `titulo` e `visibilidade` editados pela empresa.
4. Só depois do commit o job é marcado como `succeeded` e recebe `resultado`.
5. `obter_pacote`/`listar_pacotes` leem e validam `pacote_json` com `AdaptacaoPacote.model_validate_json`.

Comportamento em casos de borda:

- **Pacote corrompido:** as listagens continuam funcionando porque usam colunas desnormalizadas. O detalhe novo `GET /materiais/{id}` responde `500 INTERNO` com “Pacote de material corrompido.”. Nas rotas legadas de `adaptacoes`, o JSON inválido é tratado como ausência e a resposta é `404 ADAPTACAO_NAO_ENCONTRADA`.
- **Jobs:** continuam **em memória**, com TTL de 30 minutos (`JOB_TTL_SEGUNDOS`). Um reinício do processo perde jobs em andamento; pacotes já persistidos sobrevivem.
- **Sem backfill:** pacotes antigos que viviam só em memória não são recuperados.

---

## 6. Contrato HTTP

Base: `/api/v1`. JSON em `application/json; charset=utf-8`, exceto download/exportação. Erros no envelope `ApiProblema`.

### 6.1 Endpoints novos

| Grupo | Método | Rota | Sucesso |
|---|---|---|---|
| Materiais | GET | `/materiais` | 200 `PaginaMateriais` |
| Materiais | GET | `/materiais/{material_id}` | 200 `MaterialDetalhe` |
| Materiais | PATCH | `/materiais/{material_id}` | 200 `MaterialResumo` |
| Materiais | DELETE | `/materiais/{material_id}` | 200 `RemocaoMaterialResposta` |
| Alunos | POST | `/alunos` | 201 `AlunoResumo` |
| Alunos | GET | `/alunos` | 200 `PaginaAlunos` |
| Alunos | GET | `/alunos/{aluno_id}` | 200 `AlunoResumo` |
| Alunos | PATCH | `/alunos/{aluno_id}` | 200 `AlunoResumo` |
| Alunos | DELETE | `/alunos/{aluno_id}` | 204 sem corpo |
| Vínculos | GET | `/alunos/{aluno_id}/materiais` | 200 `VinculosAluno` |
| Vínculos | PUT | `/alunos/{aluno_id}/materiais` | 200 `VinculosAluno` |
| Vínculos | POST | `/alunos/{aluno_id}/materiais/{material_id}` | 201 novo / 200 existente |
| Vínculos | DELETE | `/alunos/{aluno_id}/materiais/{material_id}` | 204 idempotente |
| Aluno | GET | `/aluno/identificacao` | 200 `IdentificacaoAlunoResposta` |
| Aluno | GET | `/aluno/materiais` | 200 `PaginaCatalogoAluno` |
| Aluno | GET | `/aluno/materiais/{material_id}` | 200 `MaterialDetalhe` |

> **Não existe `POST /materiais`.** A criação continua sendo `POST /adaptacoes` ou `POST /adaptacoes/upload`; o pipeline cria o material em rascunho.

### 6.2 Materiais

**GET `/materiais`**

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `q` | string | — | 1..100; busca `titulo` e `documento_titulo` |
| `formato` | enum | — | `Flashcards`, `Quiz`, `Tutorial`, `ResumoExecutivo` |
| `perfil` | enum | — | `Iniciante`, `Desenvolvedor`, `LiderTecnico`, `Gestor` |
| `visibilidade` | enum | — | `rascunho` ou `publicado` |
| `ordenar` | enum | `criado_em:desc` | `criado_em:desc`, `criado_em:asc`, `ancoragem:desc`, `titulo:asc` |

A listagem usa apenas colunas desnormalizadas; nunca abre `pacote_json`.

**GET `/materiais/{material_id}`** devolve `{ material, pacote }`. Material inexistente → `404 MATERIAL_NAO_ENCONTRADO`.

**PATCH `/materiais/{material_id}`** aceita somente `titulo` (3..150 após trim) e `visibilidade`. Corpo vazio, campo desconhecido ou tentativa de alterar conteúdo → `422 VALIDACAO`. Renova `atualizado_em`.

**DELETE `/materiais/{material_id}`** remove a linha e os vínculos em cascata, depois tenta remover o objeto no OCI. Resposta:

```json
{
  "material_id": "01J...",
  "removido": true,
  "oci_removido": true
}
```

Se o OCI não estiver configurado ou falhar, `oci_removido` é `false` e o campo `aviso` é incluído; a remoção local **não** é desfeita:

```json
{
  "material_id": "01J...",
  "removido": true,
  "oci_removido": false,
  "aviso": "Material removido, mas o objeto no OCI não pôde ser excluído."
}
```

### 6.3 Alunos

**GET `/alunos`**

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `q` | string | — | 1..100; busca nome e e-mail |
| `status` | enum | — | `ativo` ou `inativo` |
| `ordenar` | enum | `nome:asc` | `nome:asc`, `nome:desc`, `criado_em:desc` |

`AlunoResumo` inclui `total_materiais`, calculado por contagem agregada de vínculos.

**POST `/alunos`**

```json
{
  "nome": "Ana Beatriz Silva",
  "email": "Ana@Exemplo.com",
  "status": "ativo"
}
```

Regras:
- `nome`: 3..120 após `trim`.
- `email`: válido, até 254, normalizado para minúsculas.
- `status` default `ativo`.
- E-mail já usado, inclusive com caixa diferente → `409 EMAIL_JA_CADASTRADO` com `campos.email`.
- Corrida entre duas requisições é tratada por `IntegrityError` e também vira 409.

**PATCH `/alunos/{aluno_id}`** aceita `nome`, `email` e/ou `status`. Ao menos um campo é obrigatório; campo desconhecido → 422. E-mail de outro aluno → 409. Renova `atualizado_em`.

**DELETE `/alunos/{aluno_id}`** remove o aluno e os vínculos em cascata; materiais permanecem.

### 6.4 Vínculos

**GET `/alunos/{aluno_id}/materiais`** devolve **todos** os vínculos, sem paginação, ordenados por `vinculado_em DESC`. Usa somente colunas de `materiais`, sem abrir `pacote_json`.

**PUT `/alunos/{aluno_id}/materiais`** substitui o conjunto inteiro de forma atômica:

```json
{ "material_ids": ["M1", "M2"] }
```

- Valida todos os ids antes de apagar/inserir. Se qualquer id não existir → `422 VALIDACAO` com `campos.material_ids` e nada é alterado.
- Duplicatas são deduplicadas preservando a primeira ocorrência.
- Materiais em rascunho podem ser vinculados; o aluno só os verá depois de publicados.
- A UI usa POST/DELETE individuais para não desvincular material fora da página/filtro; o PUT fica para operações em lote via API.

**POST/DELETE individuais** são idempotentes. POST responde 201 na criação e 200 se o vínculo já existia. DELETE responde 204 mesmo quando o vínculo não existia. Aluno ou material inexistente → 404 com o código correspondente.

### 6.5 Área do aluno

**GET `/aluno/identificacao`** lista apenas alunos `ativo`, ordenados por nome, devolvendo somente `aluno_id` e `nome`. **Nunca expõe e-mail.**

**GET `/aluno/materiais`**

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `aluno_id` | string | — | obrigatório |
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `q` | string | — | 1..100; busca título e documento |
| `formato` | enum | — | `FormatoSaida` |
| `perfil` | enum | — | `PerfilDestinatario` |
| `ordenar` | enum | `criado_em:desc` | `criado_em:desc`, `titulo:asc` |

O WHERE é sempre `vinculos.aluno_id = :aluno_id AND materiais.visibilidade = 'publicado'`, com filtros e paginação em SQL. Cada item traz no máximo 6 conceitos-chave.

**GET `/aluno/materiais/{material_id}?aluno_id=...`** devolve o detalhe apenas se o aluno existir, estiver ativo, o material estiver publicado e houver vínculo. Qualquer outro caso (material inexistente, rascunho ou não vinculado) responde o mesmo:

```json
{
  "erro": {
    "codigo": "MATERIAL_NAO_DISPONIVEL",
    "mensagem": "Material não disponível."
  }
}
```

Isso evita revelar a existência de material não liberado. Aluno inexistente → `404 ALUNO_NAO_ENCONTRADO`; aluno inativo → `403 ALUNO_INATIVO`.

---

## 7. Códigos de erro relevantes

| HTTP | Código | Quando |
|---:|---|---|
| 403 | `ALUNO_INATIVO` | Aluno inativo em rota da área do aluno. |
| 404 | `ALUNO_NAO_ENCONTRADO` | Aluno inexistente. |
| 404 | `MATERIAL_NAO_ENCONTRADO` | Material inexistente em rota da empresa. |
| 404 | `MATERIAL_NAO_DISPONIVEL` | Material não publicado, não vinculado ou inexistente em rota do aluno. |
| 404 | `ADAPTACAO_NAO_ENCONTRADA` | Rota legada de adaptação sem pacote válido. |
| 409 | `EMAIL_JA_CADASTRADO` | E-mail duplicado, comparado sem diferenciar caixa. |
| 422 | `VALIDACAO` | Corpo/query inválidos; inclui `campos` quando aplicável. |
| 500 | `INTERNO` | Erro inesperado ou `pacote_json` corrompido no detalhe de material. |

Formato do envelope:

```json
{
  "erro": {
    "codigo": "VALIDACAO",
    "mensagem": "Dados de entrada inválidos.",
    "campos": { "email": "E-mail inválido" },
    "request_id": "opcional"
  }
}
```

---

## 8. Remoção no OCI

`backend/app/services/oci.py` ganhou:

```python
def remover_objeto(objeto_id: str) -> bool
```

- Retorna `False` quando o OCI não está configurado ou a exclusão falha.
- Nunca lança exceção para o caller.
- A exclusão local do material acontece antes e não depende do OCI.
- O `DELETE /materiais/{id}` traduz o resultado em `oci_removido` e, quando falso, em `aviso`.

Após excluir o material, as rotas legadas `/adaptacoes/{id}`, `/download` e `/exportacao` passam a responder `404`, pois leem o mesmo registro.

---

## 9. Como validar

### 9.1 Preparar ambiente

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

> O `requirements-dev.txt` inclui `requirements.txt`, portanto instala SQLAlchemy e `email-validator`.

### 9.2 Rodar a suíte

```bash
cd backend
pytest tests/ -v
```

Ou, a partir da raiz, usando o Python do venv:

```bash
backend/.venv/bin/python -m pytest backend/tests -v
```

### 9.3 Smoke test manual

```bash
# sobe a API (a partir de backend/)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verificações mínimas:

1. `GET /api/v1/health` responde 200.
2. `GET /api/v1/alunos` responde 200 com página vazia em banco novo.
3. `POST /api/v1/alunos` cria aluno; repetir com o mesmo e-mail em caixa diferente deve retornar 409.
4. Gerar um material pelo pipeline e confirmar:
   - `GET /api/v1/materiais` mostra o item em `rascunho`;
   - `PATCH /api/v1/materiais/{id}` publica;
   - `GET /api/v1/aluno/materiais?aluno_id=...` só mostra depois de vincular e publicar.
5. `DELETE /api/v1/materiais/{id}` retorna `removido: true` e remove os vínculos.

### 9.4 Banco local

- O arquivo fica em `backend/data/novamente.db`.
- WAL cria `novamente.db-wal` e `novamente.db-shm`; os três estão no `.gitignore`.
- Para recomeçar do zero em desenvolvimento: pare a API, faça backup se necessário e remova os três arquivos.
- **Não** aponte `DATABASE_URL` para o banco de produção em testes; o `conftest.py` já usa diretório temporário.

---

## 10. Decisões e pontos de atenção para a equipe

1. **Sem autenticação nesta fase.** A identificação do aluno é apenas seleção de nome; não há senha, token nem cookie.
2. **`material_id = adaptacao_id`.** Não trate os dois como entidades independentes ainda.
3. **Material nasce como rascunho.** Publicar é uma ação explícita da empresa.
4. **Listagens não abrem `pacote_json`.** Mantenha essa regra ao criar novos endpoints; ela protege a listagem contra pacote corrompido.
5. **Detalhe de material corrompido é 500.** O frontend deve exibir estado de erro, não tela branca.
6. **404 unificado no aluno.** Não diferencie “não existe”, “é rascunho” e “não está vinculado” na resposta ao aluno.
7. **E-mail é case-insensitive por banco e por código.** A normalização para minúsculas acontece antes da gravação.
8. **PUT de vínculos é atômico.** A UI não deve enviar o conjunto inteiro se a lista estiver filtrada/paginada; use POST/DELETE de diferença.
9. **Exclusão local vence o OCI.** Falha ao remover objeto não restaura o material; apenas devolve aviso.
10. **SQLite é adequado ao MVP, não a múltiplas instâncias.** Evite escalar horizontalmente com o mesmo arquivo. Para produção com concorrência maior, planeje migração para Postgres.
11. **Sem migrações automáticas.** `create_all` não altera schema existente. Mudanças futuras exigem Alembic ou recriação controlada.
12. **Jobs continuam voláteis.** Persistir job/estado de pipeline é uma evolução separada.
13. **`owner_id` é reservado.** Não usar em queries nem expor no contrato até a autenticação existir.

---

## 11. Checklist de handoff

- [ ] Instalar `requirements-dev.txt` e confirmar `sqlalchemy`/`email-validator` no ambiente.
- [ ] Garantir que `backend/data/` existe e é gravável.
- [ ] Definir `DATABASE_URL` no `.env` se o caminho padrão não servir.
- [ ] Subir a API e confirmar criação das três tabelas.
- [ ] Rodar `pytest tests/ -v` e confirmar os 88 testes novos verdes.
- [ ] Gerar um material pelo pipeline e validar o fluxo rascunho → publicado → vínculo → catálogo do aluno.
- [ ] Validar 409 de e-mail duplicado com caixa diferente.
- [ ] Validar 403 de aluno inativo e 404 `MATERIAL_NAO_DISPONIVEL` para rascunho/não vinculado.
- [ ] Validar exclusão de material com e sem OCI disponível.
- [ ] Alinhar backup/rotação do arquivo SQLite antes de qualquer uso com dados reais.
