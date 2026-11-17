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
| `LLM_PROVIDER` | - | Provedor de LLM usado na geração (default: `gemini`; valores válidos: os provedores registrados) |
| `DB_PATH` | - | Arquivo SQLite dos jobs (default: `./data/novamente.db`, o mesmo do catálogo) |

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

## Qualidade do material

`avaliacao_qualidade` é calculada sobre o conteúdo gerado, sem nova chamada ao
LLM nem aos embeddings (`app/services/ancoragem.py`).

### Ancoragem na fonte (`ancoragem_fonte_score`, de 0 a 1)

Mede quanto do vocabulário do material gerado existe no documento de origem.

- **Fonte de referência:** o texto completo do documento, e não só os trechos
  recuperados. Um termo do documento que não caiu entre os trechos continua
  sendo fiel à fonte.
- **Termos:** palavras com 4 letras ou mais, e números ("404"). A comparação
  ignora maiúsculas e acentos.
- **Raiz:** o termo sem o plural simples, cortado em 6 letras
  (`TAMANHO_RAIZ`). Assim casam as flexões e as derivações da mesma raiz:
  - "métodos"/"método";
  - "idempotência"/"idempotente";
  - "versionação"/"versionamento";
  - "metodologia"/"método", de propósito.

  Palavras sem relação, como "metal" e "método", ou "servir" e "servidor",
  continuam sem casar.
- **Palavras ignoradas:** ficam todas em `app/services/ancoragem.py`, em
  minúsculas e sem acento, em dois grupos:
  - `STOPWORDS`: palavras funcionais (artigos, preposições, pronomes,
    conectivos, numerais, verbos auxiliares). São comparadas inteiras, para
    que "contra" não engula "contrato".
  - `PALAVRAS_GENERICAS`: vocabulário genérico de registro didático, por
    categoria (verbos frequentes, verbos de aprendizagem, advérbios, adjetivos
    e substantivos genéricos, e o enquadramento do material, como "aluno",
    "júnior" e "tutorial"). São comparadas pela raiz, então basta o lema:
    "utilizar" cobre "utilizando".

  Advérbios terminados em "-mente" também são ignorados. A lista foi escrita a
  partir do português geral, não das saídas medidas, e não pode conter termos
  de domínio (tabela, chave, commit, branch, consulta, requisição...): há teste
  para isso. Para estender, acrescente o lema à categoria certa.
- **O que é medido:**
  - em todos os formatos, o título e a introdução gerados;
  - Flashcards: frente, verso e dica de cada cartão;
  - Quiz: pergunta, opção correta e explicação. As opções incorretas ficam de
    fora, porque são inventadas por construção;
  - Tutorial e Resumo: cada parágrafo ou linha de lista, sem a sintaxe
    markdown e sem os títulos (`##`).
- **Nota:** para cada item, a cobertura é a fração dos seus termos presentes
  na fonte. O item vale `min(1, cobertura / 0,65)`
  (`COBERTURA_DE_REFERENCIA`), e a nota é a média dos itens. Assim, um item
  inventado puxa a nota para baixo em vez de se diluir entre os outros.
- **Por que 0,65:** uma paráfrase fiel sempre traz vocabulário próprio
  (conectivos, elaboração em registro técnico), então mesmo um item fiel cobre
  cerca de 60% da fonte. 0,65 é a mediana da cobertura dos itens fiéis no
  treino, arredondada. Um item que cobre o típico de um item fiel vale 1.
- **Título e introdução:** contam como um item cada, como os demais. Excluí-los
  ou dar peso menor mudou a nota em menos de 0,01 na calibração. Mantê-los
  ainda detecta uma introdução inventada.
- **Último recurso:** se o conteúdo não tiver nenhum termo mensurável, usa a
  relevância média dos trechos recuperados, o cálculo antigo.

#### Calibração

A calibração usou 12 saídas reais (3 documentos × 4 formatos), guardadas em
`tests/fixtures/ancoragem/`:

- **Controle fiel:** cada saída medida contra a fonte do próprio documento.
- **Controle cruzado:** cada saída medida contra a fonte de outro documento
  (Git contra HTTP, por exemplo), o que mede falso positivo sem texto escrito
  à mão.
- **Controle misto:** parte dos itens trocada por itens de outro documento.
- **Treino e validação:** os ajustes foram feitos só com `http_apis_rest` e
  `git_versionamento`; `sql_consultas` foi medido no fim, sem novos ajustes.

| | Fiel | Cruzado (máx.) |
|---|---|---|
| Antes da calibração (12 saídas) | de 0,36 a 0,53 | 0,08 |
| Treino (8 saídas) | de 0,71 a 1,00 (média 0,86) | 0,14 |
| Validação (4 saídas de SQL) | de 0,73 a 0,91 (média 0,83) | 0,19 |

No controle misto, trocar 1/3 dos itens tira de 0,2 a 0,4 da nota. Os testes
de `tests/services/test_ancoragem_calibracao.py` fixam esses limites: fiel ≥
0,70, cruzado ≤ 0,30 e separação ≥ 0,45.

As outras alternativas também foram medidas:

- remover sufixos derivacionais: separação um pouco pior e regra mais frágil;
- prefixo de 5 letras: mais falso positivo no cruzado;
- medir só termos específicos (números, siglas, identificadores): o fiel caiu
  para 0,46 e algumas saídas ficaram em 0.

Sem a escala por item, as melhores combinações de raiz e lista ficaram com o
fiel em cerca de 0,62, porque o que falta é sobretudo elaboração legítima do
material.

### Clareza (`clareza_pedagogica`: Alta, Media ou Baixa)

É um indicador de **estrutura e legibilidade**, não um julgamento didático.
Usa dois sinais, com limiares em constantes no módulo:

- **Palavras por frase**, em média, no texto corrido: introdução, versos e
  dicas, perguntas e explicações, parágrafos do markdown.
- **Estrutura completa:** introdução com pelo menos 5 palavras e, conforme o
  formato, todo cartão com frente e verso, toda pergunta com explicação, ou o
  markdown com pelo menos 2 seções (`##`).

| Clareza | Regra |
|---|---|
| Alta | estrutura completa e até 20 palavras por frase |
| Media | estrutura completa e de 21 a 30 palavras por frase, ou estrutura incompleta e até 20 |
| Baixa | mais de 30 palavras por frase, estrutura incompleta e mais de 20, ou nenhum texto |

### Limites

- **É uma medida lexical.** Não detecta uma afirmação errada escrita com o
  vocabulário da fonte (trocar "GET busca" por "GET cria" não muda a nota) e
  penaliza a paráfrase com sinônimos.
- **Conteúdo correto de fora da fonte é penalizado:** nomes padrão em inglês
  ("Forbidden", "Unauthorized") e exemplos acrescentados contam como estranhos,
  de propósito, sem exceção. Nas 12 saídas, esses termos custaram até 0,07.
- **A escala suaviza a invenção parcial:** um item com metade dos termos
  inventados vale cerca de 0,77, não 0,5. Um item todo inventado continua
  valendo perto de 0.
- **Raiz de 6 letras:** junta derivações próximas ("metodologia"/"método") e
  pode juntar palavras que só compartilham o começo.
- **Pouca calibração:** são 3 documentos curtos em português, e 12 saídas de
  um só modelo. Documentos muito curtos ou de outro domínio podem precisar de
  outra referência.
- **Clareza:** os limiares da clareza não foram recalibrados. Nas 12 saídas
  reais a distribuição foi de 6 "Alta", 6 "Media" e nenhuma "Baixa".

Leia a nota como indicador de risco, não como prova de fidelidade.

**Por que não LLM-as-a-judge:** pedir a outro modelo que avalie a fidelidade
detectaria afirmações erradas e paráfrases. Mas cada geração passaria a gastar
uma segunda chamada, com mais cota e mais tempo de espera. Fica como
alternativa futura.

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
