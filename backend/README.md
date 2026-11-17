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

## Índice do Chroma (descartável)

O pipeline indexa o documento no ChromaDB (em `CHROMA_DIR`) só para recuperar
trechos durante a geração. Depois que o pacote é salvo, nada mais lê o índice.

- **Collection única:** todos os documentos ficam na collection
  `novamente_trechos`, uma linha por trecho com o `documento_id` nos
  metadados; a busca filtra pelo documento. Neste Chroma (1.5.9), apagar uma
  collection não tira do disco o diretório do índice HNSW, nem libera a
  memória do processo. Por isso não há mais uma collection por documento.
- **Limpeza no fim de cada job:** ao terminar (sucesso, falha, cancelamento
  ou prazo excedido), o worker apaga as linhas do documento, depois de salvar
  o estado final do job. Uma falha ao apagar vira aviso no log e não muda o
  resultado do job.
- **Limpeza automática na subida** (`app/services/limpeza_indice.py` e
  `limpeza_disco_chroma.py`): ninguém precisa apagar nada à mão. Neste Chroma
  (1.5.9), `delete_collection` tira a collection do catálogo, mas deixa no
  disco o diretório do seu segmento HNSW (`<CHROMA_DIR>/<uuid>/`, cerca de
  1,2 MB cada), mesmo depois de reabrir. Por isso a subida faz quatro etapas,
  todas best-effort: um erro em qualquer uma vira aviso no log e a subida
  continua.
  1. **Linhas órfãs:** apaga as linhas de documentos do pipeline (`doc_<ULID>`)
     cujo job não está `queued` nem `running` no banco.
  2. **Legado:** apaga as collections de versões anteriores (uma por
     documento): só as de nome com prefixo `doc_` e `documento_id` no formato
     `doc_<ULID>` nos metadados. As outras não são tocadas.
  3. **Rotação:** se a collection compartilhada ficou sem nenhuma linha, não há
     job em andamento e o índice HNSW dela já existe no disco, ela é recriada,
     sob o mesmo lock da indexação, para o HNSW recomeçar vazio. Se algo falhar
     no meio, a próxima indexação a recria.
  4. **Coleta de diretórios órfãos**, o que de fato libera o disco. Um
     diretório só é apagado se passar por todas as travas:
     - o nome é um UUID canônico;
     - fica diretamente dentro de `CHROMA_DIR` e não é link simbólico;
     - `CHROMA_DIR` não é vazio, a raiz do sistema, a pasta pessoal nem uma
       pasta acima dela;
     - só tem arquivos de índice HNSW (`data_level0.bin`, `header.bin`,
       `length.bin`, `link_lists.bin`, `index_metadata.pickle`);
     - nenhum segmento vivo do catálogo (`chroma.sqlite3`, tabela `segments`,
       lido em modo somente leitura) tem esse id;
     - ninguém o modifica há mais de 1 hora.

     Se o catálogo não abre, está travado ou não tem a tabela e a coluna
     esperadas, nada é apagado. Na dúvida, não apaga.

  Um resumo vai para o log em INFO, com uma linha que começa com
  "Varredura do índice do Chroma". Uma segunda subida não faz nada. Ela também
  não cria a pasta do Chroma: se a pasta não existe, não há nada a limpar.
- **Disco:** em 300 jobs de 8 trechos com vetores de 3072 dimensões, apagar só
  as linhas deixou a pasta com 32 MB e o processo com 164 MB de memória. Com
  uma collection por documento, foram 373 MB e 602 MB. Entre reinícios a pasta
  cresce cerca de 0,1 MB por job, porque o HNSW só marca as linhas como
  apagadas; a rotação na subida descarta esse espaço. Num ambiente com 93
  collections legadas e 20 diretórios órfãos, a primeira subida levou a pasta
  de 158 MB para 17 MB, em 0,1 s. O que sobra é o `chroma.sqlite3`, que não
  encolhe sozinho.
- **Ao atualizar o `chromadb`:** a coleta depende do formato interno do
  Chroma. O teste canário de `tests/services/test_limpeza_disco_chroma.py`
  falha se o catálogo ou os segmentos mudarem; revise
  `limpeza_disco_chroma.py` antes de aceitar a atualização.
- **Recursos futuros:** um recurso que precise do índice depois da geração
  (chat sobre o documento, regeneração) deve reindexar a partir do texto.

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
