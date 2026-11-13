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
| `LLM_PROVIDER` | — | Provedor de LLM usado na geração (default: `gemini`; valores válidos: os provedores registrados) |
| `DB_PATH` | — | Arquivo SQLite dos jobs e do histórico (default: `/data/novamente.sqlite3`) |

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

## Jobs e histórico

Jobs de geração e pacotes gerados ficam num arquivo SQLite em `DB_PATH`; a
pasta é criada se não existir. Ao subir, o backend marca como `failed` os
jobs que estavam em andamento quando o processo anterior parou. Jobs expiram
`JOB_TTL_SEGUNDOS` depois da última atualização; o histórico de materiais não
expira.

- **Produção:** o arquivo precisa ficar num volume persistente (ao lado do
  `/data/chroma`). Sem volume, o histórico se perde quando o container é
  recriado.
- **Um processo só:** o cancelamento de jobs fica em memória. Com vários
  workers (`uvicorn --workers N`), um pedido de cancelamento só alcança o job
  se cair no mesmo processo que o executa.

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

## Integração com o Frontend

O frontend Next.js espera o backend em `http://localhost:8000` (configurável
em `frontend/.env.local` via `API_BASE_URL`). O rewrite `/api/v1/:path*` do
Next.js roteia as chamadas automaticamente.
