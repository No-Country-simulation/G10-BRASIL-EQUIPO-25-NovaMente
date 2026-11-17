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
| `LLM_PROVIDER` | — | Provedor de LLM usado na geração (default: `gemini`; valores válidos: os provedores registrados) |
| `LLM_TENTATIVAS` | — | Chamadas ao LLM por geração em falhas transitórias, contando a primeira (default: `3`; mínimo `1`, que desliga a retentativa) |
| `LLM_ESPERA_INICIAL_SEGUNDOS` | — | Espera antes da primeira retentativa; dobra a cada tentativa (default: `2`; mínimo `0`) |
| `JOB_TIMEOUT_SEGUNDOS` | — | Prazo total de um job de geração, em segundos (default: `300`) |
| `DB_PATH` | — | Arquivo SQLite dos jobs e do histórico (default: `./data/novamente.db`, o mesmo do catálogo) |

## Provedor de LLM

A geração de conteúdo chama o modelo por uma interface, `ProvedorLLM`
(`app/llm/`), e não por um SDK. O provedor é escolhido por `LLM_PROVIDER`;
o padrão `gemini` usa o SDK `google-genai`, o mesmo dos embeddings, com
`MODELO_LLM`, `LLM_TIMEOUT_SEGUNDOS` e a chave de `GOOGLE_API_KEY`.

Contrato:

```python
class ProvedorLLM(Protocol):
    nome: str

    def gerar(self, mensagens: list[Mensagem], *, timeout_segundos: float) -> str: ...
```

`Mensagem(papel, conteudo)` tem papel `"system"`, `"user"` ou `"assistant"`.
O provedor devolve só o texto da resposta e, em caso de falha, levanta
apenas os erros de `app/llm/erros.py` (nenhum erro de SDK pode escapar):

| Erro | Quando |
|---|---|
| `ErroTransitorio` (`ErroLimiteTaxa`, `ErroIndisponivel`) | limite de uso (429), serviço fora do ar (5xx, exceto 504) ou falha de conexão |
| `ErroTimeout` | o modelo não respondeu dentro de `timeout_segundos` (inclui 408 e 504) |
| `ErroRespostaInvalida` | resposta vazia, bloqueada ou sem texto |
| `ErroConfiguracao` | chave ausente ou inválida, modelo inexistente, argumento recusado |

O pipeline converte cada categoria na mensagem que o usuário vê; outros
erros (`ErroLLM`) viram "Erro interno ao gerar o material.".

Para acrescentar um provedor, implemente o contrato e registre um construtor
sem argumentos em `app/llm/fabrica.py`:

```python
registrar_provedor("meu-provedor", lambda: MeuProvedor(modelo=settings.modelo_llm))
```

e use `LLM_PROVIDER=meu-provedor`. Um `LLM_PROVIDER` desconhecido impede a
subida do backend, com uma mensagem que lista os valores válidos. A falta de
`GOOGLE_API_KEY` não impede a subida: a geração é que falha. O cliente do
Gemini é criado na primeira geração e reaproveitado pelos jobs seguintes.

### Retentativa de falhas transitórias

A fábrica entrega todo provedor embrulhado em `ProvedorComRetentativa`
(`app/llm/retentativa.py`), então a regra vale para qualquer provedor sem
mudar o adaptador nem o pipeline.

| Erro | Retentado? |
|---|---|
| `ErroLimiteTaxa`, `ErroIndisponivel`, `ErroTimeout` | sim, até `LLM_TENTATIVAS` chamadas |
| `ErroConfiguracao` (inclui `ProvedorDesconhecido`) | não, falha na primeira |
| `ErroRespostaInvalida` | não nesta camada; o pipeline já repete a geração uma vez |

- **Espera:** `LLM_ESPERA_INICIAL_SEGUNDOS`, dobrando a cada tentativa, com
  ±20% de variação aleatória e teto de 30 s por espera.
- **Prazo do job:** o worker passa ao pipeline o instante em que o job expira
  (`JOB_TIMEOUT_SEGUNDOS` a partir do início). Uma retentativa só começa se a
  espera mais uma chamada inteira (`LLM_TIMEOUT_SEGUNDOS`) couberem no que
  resta; se não couberem, o job falha com a mensagem da última falha.
- **Cancelamento:** a espera é feita em fatias de 0,5 s, e entre elas o
  pedido de cancelamento do job é conferido.
- **Mensagens:** quando as tentativas acabam, o usuário vê a mesma mensagem de
  antes para a categoria (indisponível, limite de uso ou tempo limite). Cada
  falha vai para o log com o provedor, a categoria e o número da tentativa,
  sem o conteúdo do documento.
- **Valores inválidos:** `LLM_TENTATIVAS` menor que 1 ou
  `LLM_ESPERA_INICIAL_SEGUNDOS` negativo impedem a subida do backend.

Pior caso com os padrões (`LLM_TENTATIVAS=3`, espera inicial 2 s,
`LLM_TIMEOUT_SEGUNDOS=120`, `JOB_TIMEOUT_SEGUNDOS=300`):

| Situação | Chamadas | Tempo gasto no LLM |
|---|---|---|
| Erros rápidos (429/503) em todas as tentativas | 3 | ~7 s de espera (2,4 s + 4,8 s no máximo) além das chamadas |
| Timeout em todas as tentativas, LLM chamado no início do job | 2 (a 3ª não cabe no prazo) | ~242 s (120 + 2,4 + 120) |
| Timeout, com o LLM chamado depois de 58 s de job | 1 (a 2ª não cabe) | 120 s |
| Retentativas seguidas de resposta inválida | +1 chamada do pipeline, sem checagem de prazo | até `JOB_TIMEOUT_SEGUNDOS` + 120 s desde o início do job |

## Conceitos-chave

`metadados.conceitos_chave` é o resumo do que o aluno deve dominar. Ele vem
da mesma chamada que gera o conteúdo: o prompt pede, no mesmo objeto JSON, o
campo `conceitos_chave`, com 5 a 8 termos curtos tirados do documento. Não há
chamada extra ao LLM nem aos embeddings. As regras ficam em
`app/services/conceitos.py`.

- **Campo opcional:** se o campo faltar, vier vazio ou com tipo errado, a
  geração segue normalmente. Ele não conta como resposta inválida e não gasta
  a retentativa do pipeline.
- **Validação:** a comparação ignora maiúsculas, acentos e espaços extras, e
  tolera o plural simples terminado em "s"/"es" ("API" e "APIs"; siglas em
  maiúsculas como "HTTPS" não entram nessa regra). São descartados os itens:
  - que não são texto, têm 1 caractere ou mais de 60 caracteres;
  - duplicados;
  - formados só por palavras genéricas;
  - iguais ao título do documento;
  - que não aparecem no texto de origem completo.

  Ficam no máximo 8, na ordem em que o LLM os devolveu.
- **Fallback:** se nenhum item do LLM for aproveitado, usa termos
  capitalizados e siglas do título e dos trechos recuperados, sem palavras
  genéricas. Eles são ordenados pela frequência nos trechos e depois pela
  ordem de aparição, no máximo 8. Se nada sobrar, usa o título do documento.
- **Palavras genéricas:** artigos, preposições, quantificadores ("cada",
  "um") e termos estruturais ("introdução", "resumo", "texto", "capítulo"...)
  ficam em `PALAVRAS_GENERICAS`, no mesmo módulo. Para cortar outra palavra,
  acrescente-a ali em minúsculas e sem acento; a validação e o fallback usam
  a mesma lista.

## Jobs e histórico

Jobs de geração ficam no arquivo SQLite apontado por `DB_PATH`; a pasta é
criada se não existir. Ao subir, o backend marca como `failed` os jobs que
estavam em andamento quando o processo anterior parou. Jobs expiram
`JOB_TTL_SEGUNDOS` depois da última atualização; o histórico de materiais não
expira.

Os pacotes são gravados na tabela legada `pacotes` (para compatibilidade com o
histórico) e no catálogo SQLAlchemy de materiais. Por padrão `DB_PATH` e
`DATABASE_URL` apontam para o mesmo arquivo `backend/data/novamente.db`.

- **Produção:** o arquivo precisa ficar num volume persistente (ao lado do
  `/data/chroma`). Sem volume, o histórico se perde quando o container é
  recriado.
- **Um processo só:** o cancelamento de jobs fica em memória. Com vários
  workers (`uvicorn --workers N`), um pedido de cancelamento só alcança o job
  se cair no mesmo processo que o executa.

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
