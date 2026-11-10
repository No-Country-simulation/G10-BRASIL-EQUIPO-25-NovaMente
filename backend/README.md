# Como executar o backend NovaMente

## Configuração

### Atalho com Make (recomendado)

A partir da **raiz do repositório** (funciona em Linux/macOS e Windows com GNU Make instalado):

```bash
make install-backend-dev         # cria backend/.venv com requirements-dev.txt
cp backend/.env.example backend/.env   # depois preencha GOOGLE_API_KEY
make dev-backend                 # sobe a API em http://localhost:8000
make test-backend                # roda pytest
```

Use `make venv` se quiser apenas as dependências de produção
(`requirements.txt`).

> No Windows (PowerShell/CMD), use `copy backend\.env.example backend\.env`.

Os comandos `make` usam diretamente o Python de `backend/.venv`, então não é
necessário ativar o ambiente virtual.

### Passo a passo manual

```bash
cd backend

# 1. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\Activate.ps1       # Windows (PowerShell)

# 2. Instale as dependências
#    Produção: requirements.txt | Desenvolvimento e testes: requirements-dev.txt
pip install -r requirements-dev.txt

# 3. Crie o arquivo de variáveis de ambiente
cp .env.example .env
# Edite .env e preencha GOOGLE_API_KEY e (opcionalmente) as credenciais OCI

# 4. Inicie o servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ | Chave da API Google Gemini |
| `DATABASE_URL` | — | Banco SQLAlchemy. Default: `sqlite:///./data/novamente.db` (relativo a `backend/`) |
| `OCI_NAMESPACE` | — | Namespace do OCI Object Storage |
| `OCI_BUCKET` | — | Nome do bucket (default: `novamente-conteudos-educativos`) |
| `OCI_REGIAO` | — | Região OCI (ex: `sa-saopaulo-1`) |
| `LLM_TIMEOUT_SEGUNDOS` | — | Tempo limite de cada chamada ao Gemini, em segundos (default: `120`) |
| `CHROMA_DIR` | — | Diretório do ChromaDB (default: `/data/chroma`) |
| `MODELO_LLM` | — | Modelo Gemini (default: `gemini-3.5-flash-lite`) |

## Banco de dados e catálogo

O catálogo de materiais, alunos e vínculos é persistido em SQLite via SQLAlchemy 2.

- Arquivo padrão: `backend/data/novamente.db` (criado automaticamente no `lifespan`).
- O engine habilita `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL` e `check_same_thread=False`.
- Os arquivos `*.db`, `*.db-wal` e `*.db-shm` ficam fora do git.
- **Não há Alembic/migrations nesta fase.** `create_all` só cria tabelas ausentes; mudanças de schema exigem migração ou recriação controlada.
- Jobs continuam **em memória** (TTL de 30 min). Pacotes já finalizados sobrevivem ao reinício.
- `material_id` é igual a `adaptacao_id` nesta fase; todo material gerado nasce com `visibilidade = "rascunho"`.
- Excluir aluno remove vínculos em cascata; excluir material remove vínculos em cascata e tenta apagar o objeto do OCI.

### Rotas novas

Base: `/api/v1`.

| Grupo | Rotas |
|---|---|
| Materiais (empresa) | `GET/PATCH/DELETE /materiais`, `GET /materiais/{id}` |
| Alunos (empresa) | `POST/GET /alunos`, `GET/PATCH/DELETE /alunos/{id}` |
| Vínculos | `GET/PUT /alunos/{id}/materiais`, `POST/DELETE /alunos/{id}/materiais/{material_id}` |
| Área do aluno | `GET /aluno/identificacao`, `GET /aluno/materiais`, `GET /aluno/materiais/{id}` |

Não existe `POST /materiais`: a criação continua em `POST /adaptacoes` e `POST /adaptacoes/upload`, e o pipeline cria o material em rascunho ao concluir.

O guia completo de alterações, schema, erros e checklist de handoff está em
[`docs/backend-alteracoes-2026-11-09.md`](../docs/backend-alteracoes-2026-11-09.md).

## Documentação Interativa

Com o servidor rodando, acesse:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testes

Os testes precisam das dependências de desenvolvimento:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/ -v
```

O `conftest.py` aponta `DATABASE_URL` para um diretório temporário por sessão,
cria o schema e limpa as tabelas entre os testes. A suíte não toca em
`backend/data/novamente.db`. A entrega adiciona 88 testes cobrindo banco,
repositório, materiais, alunos, vínculos e catálogo do aluno.

## Integração com o Frontend

O frontend Next.js espera o backend em `http://localhost:8000` (configurável
em `frontend/.env.local` via `API_BASE_URL`). O rewrite `/api/v1/:path*` do
Next.js roteia as chamadas automaticamente.
