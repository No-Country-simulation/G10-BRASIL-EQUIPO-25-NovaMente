# Como executar o backend NovaMente

## Configuração

```bash
# 1. Instale as dependências (produção: requirements.txt;
#    desenvolvimento e testes: requirements-dev.txt)
cd backend
pip install -r requirements-dev.txt

# 2. Crie o arquivo de variáveis de ambiente
cp .env.example .env
# Edite .env e preencha GOOGLE_API_KEY e (opcionalmente) as credenciais OCI

# 3. Inicie o servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | ✅ | Chave da API Google Gemini |
| `OCI_NAMESPACE` | — | Namespace do OCI Object Storage |
| `OCI_BUCKET` | — | Nome do bucket (default: `novamente-conteudos-educativos`) |
| `OCI_REGIAO` | — | Região OCI (ex: `sa-saopaulo-1`) |
| `LLM_TIMEOUT_SEGUNDOS` | — | Tempo limite de cada chamada ao Gemini, em segundos (default: `120`) |
| `CHROMA_DIR` | — | Diretório do ChromaDB (default: `/data/chroma`) |
| `MODELO_LLM` | — | Modelo Gemini (default: `gemini-3.5-flash-lite`) |
| `DATABASE_URL` | ✅ | URL do PostgreSQL dos jobs e do histórico (ex.: `postgresql://usuario:senha@host:5432/banco`). Senhas com caracteres especiais precisam ser codificadas na URL (`%40` para `@`, `%2F` para `/`) |

## Jobs e histórico (PostgreSQL)

Jobs de geração e pacotes gerados ficam no PostgreSQL indicado por
`DATABASE_URL`. As tabelas são criadas e migradas sozinhas na primeira
operação. Ao subir, o backend marca como `failed` os jobs que estavam em
andamento quando o processo anterior parou. Jobs expiram `JOB_TTL_SEGUNDOS`
depois da última atualização; o histórico de materiais não expira.

Para desenvolvimento, um Postgres local com credenciais descartáveis:

```bash
docker run -d --name novamente-postgres -e POSTGRES_USER=novamente -e POSTGRES_PASSWORD=senha_dev -e POSTGRES_DB=novamente -p 127.0.0.1:5432:5432 postgres:16
```

e no `.env`: `DATABASE_URL=postgresql://novamente:senha_dev@localhost:5432/novamente`.

- **Produção:** a `DATABASE_URL` vem do ambiente (segredo da plataforma),
  nunca do repositório.
- **Um processo só:** na subida, a recuperação marca como `failed` todo job
  `queued` ou `running`, inclusive os de outro processo ainda vivo. Não use
  vários workers (`uvicorn --workers N`) nem suba duas instâncias em paralelo
  sobre o mesmo banco. O cancelamento de jobs também fica em memória.
- **Banco fora do ar:** se o PostgreSQL não responder na subida, o backend
  não sobe; ele espera até 10 s pela primeira conexão e então falha.
- **`uvicorn --reload`:** cada recarga é uma nova subida, então marca como
  `failed` os jobs que estavam em andamento.

## Documentação Interativa

Com o servidor rodando, acesse:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testes

Os testes precisam das dependências de desenvolvimento e de um PostgreSQL em
`DATABASE_URL` (pode ser o de desenvolvimento acima). Cada teste usa um
schema próprio, criado e apagado por ele; sem `DATABASE_URL`, os testes que
usam o repositório falham com a mensagem "DATABASE_URL não definida".

```bash
cd backend
pip install -r requirements-dev.txt
DATABASE_URL=postgresql://novamente:senha_dev@localhost:5432/novamente pytest tests/ -v
```

## Integração com o Frontend

O frontend Next.js espera o backend em `http://localhost:8000` (configurável
em `frontend/.env.local` via `API_BASE_URL`). O rewrite `/api/v1/:path*` do
Next.js roteia as chamadas automaticamente.
