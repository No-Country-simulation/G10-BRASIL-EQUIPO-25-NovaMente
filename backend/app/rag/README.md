## Pipeline de RAG

O módulo RAG (`backend/app/rag/`) garante que o conteúdo gerado pelo NovaMente se apoie no documento original enviado pelo usuário. Ele divide o texto em trechos, transforma cada trecho em um vetor (embedding), guarda os vetores no ChromaDB e, na hora de gerar, devolve os trechos mais parecidos com a consulta para o LLM usar como fonte.

### Como funciona

```mermaid
flowchart LR
    A[Texto do documento] --> B[Chunking<br/>1000 caracteres, overlap 150]
    B --> C[Embeddings<br/>gemini-embedding-001]
    C --> D[(ChromaDB<br/>1 collection por documento)]
    Q[Consulta] --> E[Embedding da consulta]
    E --> D
    D --> F[Top-k trechos<br/>com relevância]
    F --> G[Prompt do LLM<br/>com as fontes]
```

| Etapa | O que faz | Arquivo |
|---|---|---|
| Chunking | Quebra o texto por parágrafo, linha, frase e palavra, nessa ordem de preferência, com sobreposição para não perder contexto na fronteira | `chunking.py` |
| Embeddings | Gera vetores de 3072 dimensões com `gemini-embedding-001` (`RETRIEVAL_DOCUMENT` na indexação, `RETRIEVAL_QUERY` na consulta), em lotes de 50, com nova tentativa em caso de erro 429 | `embeddings.py` |
| Armazenamento | Guarda os vetores no ChromaDB, uma collection por documento (`doc_<id>_<hash>`), com métrica cosseno | `armazenamento.py` |
| Serviço | Expõe as duas funções usadas pela API | `servico.py` |

Os valores (tamanho do chunk, overlap, limites de texto, `k` padrão) ficam em `config.py`.

### Como usar

```python
from app.rag import indexar_documento, recuperar

resultado = indexar_documento(
    documento_id="abc123",
    titulo="APIs REST",
    texto=texto_extraido,
    on_etapa=lambda etapa: print(etapa),  # "chunking" e depois "embeddings"
)
# resultado.total_trechos, resultado.caracteres

trechos = recuperar("abc123", "O que significa o erro 404?", k=4)
for t in trechos:
    print(t.indice, round(t.relevancia, 2), t.texto[:80])
```

| Função | Entrada | Saída |
|---|---|---|
| `indexar_documento(documento_id, titulo, texto, on_etapa=None)` | texto entre 200 e 50.000 caracteres | `ResultadoIndexacao` |
| `recuperar(documento_id, consulta, k=4)` | documento já indexado | lista de `Trecho` (`texto`, `indice`, `relevancia`, `documento_id`) |

**Erros:** `ValueError` quando a entrada é inválida (a API devolve HTTP 422) e `LookupError` quando o documento não foi indexado (HTTP 404).

**Relevância:** é `1 - distância cosseno`, limitada entre 0 e 1. Ela mede a proximidade vetorial entre o trecho e a consulta. Não é o `ancoragem_fonte_score` final, que combina essa distância com o LLM-as-a-judge e fica na camada de integração (veja *Pendências*).

### Configuração

| Variável | Para que serve |
|---|---|
| `GOOGLE_API_KEY` | Chave do Gemini, lida do ambiente. Nunca vai para o código nem para o repositório |
| `CHROMA_DIR` | Pasta do banco vetorial. Padrão: `/data/chroma`, fora do repositório |

Dependências do módulo: `backend/requirements-rag.txt`.

### Como testar

Os testes usam um embedding falso e **não chamam a API do Gemini**:

```bash
pytest backend/tests/rag
```

Para ver o RAG funcionando com o Gemini real, use os textos de `backend/data/exemplos/`. O script indexa o texto, faz perguntas e mostra os trechos com a relevância, usando uma pasta temporária:

```bash
export GOOGLE_API_KEY=...        # sua chave, sem colocar em arquivo versionado
python backend/scripts/demo_rag.py                      # http_apis_rest.md
python backend/scripts/demo_rag.py sql_consultas.md
python backend/scripts/demo_rag.py git_versionamento.md
```

### Cenários de demonstração

Execução real do `demo_rag.py` com o Gemini (`gemini-embedding-001`), pedindo os 2 trechos mais relevantes (`k=2`) para cada pergunta. Cada texto de exemplo tem cerca de 2.000 caracteres e gera 3 trechos. A coluna "Trecho esperado" indica em qual trecho está a resposta no texto, conferido manualmente.

**Cenário 1: `http_apis_rest.md` (3 trechos, 2.006 caracteres)**

| Pergunta | Trecho esperado | Trechos recuperados (relevância) | Acertou |
|---|---|---|---|
| O que significa o erro 404? | 1 | **1 (0,679)**, 0 (0,668) | Sim, em 1º |
| Qual a diferença entre PUT e PATCH? | 0 | **0 (0,704)**, 2 (0,654) | Sim, em 1º |
| Como versionar uma API? | 2 | **2 (0,734)**, 0 (0,684) | Sim, em 1º |

**Cenário 2: `sql_consultas.md` (3 trechos, 1.938 caracteres)**

| Pergunta | Trecho esperado | Trechos recuperados (relevância) | Acertou |
|---|---|---|---|
| Como encontrar clientes que nunca fizeram pedidos? | 1 | 0 (0,621), **1 (0,613)** | Sim, em 2º |
| Quando usar HAVING em vez de WHERE? | 1 | **1 (0,711)**, 0 (0,676) | Sim, em 1º |
| Índices deixam o banco mais lento? | 2 | **2 (0,756)**, 0 (0,656) | Sim, em 1º |

**Cenário 3: `git_versionamento.md` (3 trechos, 1.861 caracteres)**

| Pergunta | Trecho esperado | Trechos recuperados (relevância) | Acertou |
|---|---|---|---|
| O que acontece quando duas pessoas mudam a mesma linha? | 1 | **1 (0,689)**, 0 (0,661) | Sim, em 1º |
| Para que serve um pull request? | 2 | **2 (0,758)**, 1 (0,692) | Sim, em 1º |
| Qual a diferença entre merge e rebase? | 1 | **1 (0,739)**, 2 (0,670) | Sim, em 1º |

**Leitura dos resultados:**
- Nas 9 perguntas, o trecho com a resposta apareceu entre os 2 recuperados; em 8 delas ele foi o primeiro.
- Na pergunta sobre clientes sem pedidos, o trecho certo ficou em 2º lugar, com relevância muito próxima do 1º (0,613 contra 0,621). A busca por similaridade não garante a ordem exata, e a diferença é pequena.
- As relevâncias ficaram entre 0,61 e 0,76 mesmo quando o trecho está certo. Por isso a relevância sozinha não deve ser tratada como nota de qualidade: ela serve para ordenar trechos, e não para dizer se o conteúdo gerado está bem apoiado na fonte.
- Os textos de exemplo são curtos. Com documentos reais, que geram muito mais trechos, o resultado pode variar.

### Pendências

- **Fluxo completo de ponta a ponta:** depende do modelo do Gemini configurado no backend e do frontend. Os cenários acima mostram só a parte do RAG.
- **`ancoragem_fonte_score`:** hoje o backend usa a relevância média. O documento oficial pede combinar a distância vetorial com o LLM-as-a-judge e reescrever o conteúdo quando o score fica abaixo de 0,85.
- **Limpeza:** as collections do Chroma ainda não são removidas depois do job (o módulo já tem `remover_documento`).
