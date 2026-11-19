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
| `NVIDIA_NIM_API_KEY` | com `LLM_PROVIDER=nvidia` | Chave da NVIDIA NIM; só é exigida na geração |
| `NVIDIA_NIM_BASE_URL` | — | URL da API compatível com OpenAI (default: `https://integrate.api.nvidia.com/v1`) |
| `NVIDIA_NIM_MODELO` | — | Id do modelo no catálogo da NVIDIA (default sugerido: `nvidia/nemotron-3.5-lightning-30b-a3b`; o catálogo gratuito muda com frequência) |
| `NVIDIA_NIM_MAX_TOKENS` | — | Limite de tokens da resposta, raciocínio incluído; precisa ser maior que o orçamento de raciocínio (default: `8192`) |
| `NVIDIA_NIM_TEMPERATURA` | — | Temperatura da geração (default: vazia, vale a do modelo) |
| `NVIDIA_NIM_RACIOCINIO` | — | `ligado` ou `desligado` envia `chat_template_kwargs.enable_thinking`; vazio não envia (vale o padrão do modelo). Outro valor impede a subida |
| `NVIDIA_NIM_ORCAMENTO_RACIOCINIO` | — | Tokens de raciocínio (`reasoning_budget`); vazio não envia, e não vai com o raciocínio `desligado` |
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

### Provedor NVIDIA NIM (opcional)

Com `LLM_PROVIDER=nvidia`, a geração usa um modelo do catálogo da NVIDIA NIM
(`app/llm/nvidia.py`), por `POST {NVIDIA_NIM_BASE_URL}/chat/completions`, a
API compatível com OpenAI. Os embeddings continuam no Gemini.

- **Chave:** como no Gemini, só é exigida na geração. Sem
  `NVIDIA_NIM_API_KEY`, a geração falha com erro de configuração e a subida
  segue normal.
- **Retentativa:** a mesma dos outros provedores.
  - 429, 5xx, timeout e falha de conexão são passageiros e entram na
    retentativa.
  - 401/403 ("chave inválida ou sem acesso"), 404 ("modelo indisponível no
    catálogo") e 410 ("modelo removido do catálogo") falham na hora; 404 e
    410 viram `ErroModeloIndisponivel`.
  - Resposta sem `choices` ou sem texto é tratada como resposta inválida.
- **Raciocínio:** `NVIDIA_NIM_RACIOCINIO` e `NVIDIA_NIM_ORCAMENTO_RACIOCINIO`
  vão no nível raiz do JSON da requisição (`chat_template_kwargs`,
  `reasoning_budget`), que é o que o `extra_body` do cliente OpenAI produz. Da
  resposta vale só `message.content`, sem os blocos `<think>...</think>`;
  `reasoning_content` é ignorado.
- **Resposta cortada:** `finish_reason` igual a `length` é resposta inválida,
  mesmo com texto parcial, porque JSON cortado não serve. Aumente
  `NVIDIA_NIM_MAX_TOKENS` ou reduza o raciocínio.
- **Plano gratuito:** o plano gratuito da NVIDIA é para protótipo e testes, não
  para produção. Os limites de uso da conta aparecem em build.nvidia.com.

Para escolher o modelo, `scripts/comparar_modelos.py` gera material com as
funções do pipeline para cada modelo candidato, variante de raciocínio,
documento de `data/exemplos/` e formato. Ele mede:

- a ancoragem na fonte;
- se o JSON veio válido na primeira resposta;
- quantas gerações foram cortadas pelo limite de tokens (coluna "Cortadas");
- a latência;
- os tokens.

- **`--raciocinio`:** escolhe as variantes, entre `padrao` (não envia nada),
  `desligado` e `ligado`, separadas por vírgula; o padrão é `padrao`. Cada
  modelo é medido em cada variante.
- **Variante recusada:** fica como "não suportado" e o script segue para a
  próxima.
- **Chave recusada (401/403):** interrompe a comparação, grava o relatório
  parcial e sai com código 1.
- **`--listar`:** só imprime os ids do `GET /models` da conta, em ordem, e sai.

Precisa só de `NVIDIA_NIM_API_KEY`: a ancoragem não usa embeddings, então
`GOOGLE_API_KEY` não é necessária. As chamadas são sequenciais, com intervalo
mínimo configurável (padrão 1,6 s, abaixo de ~40 por minuto). Quem decide que
um modelo está indisponível é o HTTP 404 ou 410 na geração (os dois viram
`ErroModeloIndisponivel`): aí ele fica como
"indisponível" e o script segue para o próximo. Um modelo que não aparece no
`GET /models` é tentado mesmo assim, porque alguns modelos com endpoint
próprio não são listados; se gerar, fica como "disponível (fora do /models)".
O relatório em Markdown vai para `data/relatorios/`, que o git ignora.

```bash
cd backend
python scripts/comparar_modelos.py --listar
python scripts/comparar_modelos.py
python scripts/comparar_modelos.py --modelos org/modelo-a,org/modelo-b --raciocinio padrao,desligado --formatos Quiz --intervalo 3
```

Nas primeiras medições (18/11/2026; 3 documentos de exemplo, formatos
Flashcards e Tutorial, 6 gerações por célula), o nemotron-3.5-lightning com o
raciocínio no padrão teve latência média de 63 s, respostas cortadas e
ancoragem 0,871; com `NVIDIA_NIM_RACIOCINIO=desligado`, teve 6,9 s, nenhuma
resposta cortada e 0,923. No nemotron-3.5-bolt-e4b e no gemma-4-31b-it a opção
não mudou o consumo de tokens. É uma amostra pequena, e a ancoragem é lexical.

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

## Geração multiagente

Com `GERACAO_MULTIAGENTE=true`, a geração do material passa por um grafo em
LangGraph (`app/services/geracao_grafo.py`) que escreve, confere a ancoragem
e revisa. Desligada (o padrão), a geração é a passada única de sempre, com o
mesmo prompt; a passada única também é o fallback do grafo.

```
roteador -> pesquisador -> redator -> crítico -> fim (aprovado ou parada)
                 ^                        |
                 +-------- revisar -------+
```

- **Roteador** (sem LLM): plano com formato, perfil e `tem_diagrama`
  (sempre falso; reservado para a etapa de diagramas).
- **Pesquisador:** na 1ª rodada, a mesma recuperação da passada única (k=6);
  nas revisões, uma busca dirigida com o texto dos itens mal ancorados do
  rascunho, juntando os trechos novos aos já usados (sem repetir, até 12).
- **Redator:** o prompt da passada única; nas revisões, mais um bloco curto
  com os itens fracos e as palavras do próprio rascunho que não aparecem nos
  trechos. Nunca vai texto do documento nesse bloco.
- **Crítico** (sem LLM): a mesma avaliação que grava `ancoragem_fonte_score`,
  então as notas dos dois modos são comparáveis. Aprova com ancoragem igual
  ou acima do limiar; senão para quando as revisões acabam, quando a nota não
  melhora em relação à rodada anterior ou quando o prazo do job não comporta
  outra chamada.

O resultado é sempre o rascunho de maior ancoragem (não o último); não atingir
o limiar não faz o job falhar. O progresso usa só as etapas de hoje, e elas
só avançam: a pesquisa e a redação da 1ª rodada aparecem como `gerando`;
depois da primeira avaliação, tudo aparece como `revisando` (inclusive a
passada única do fallback), com a rodada no texto da mensagem ("Buscando
trechos para a revisão (rodada 2 de 3)..."). O percentual só sobe.

| Variável | Padrão | Para que serve |
|---|---|---|
| `GERACAO_MULTIAGENTE` | `false` | Liga o grafo |
| `GRAFO_MAX_REVISOES` | `2` | Revisões depois da primeira escrita (0 a 2) |
| `GRAFO_LIMIAR_ANCORAGEM` | `0.75` | Ancoragem que aprova o rascunho (0 a 1) |
| `GRAFO_MAX_SIMULTANEOS` | `2` | Jobs no grafo ao mesmo tempo; sem vaga, o job vai pela passada única |

Vazio vale o padrão. O limiar de 0,75 vem das 12 saídas reais da calibração
da ancoragem: as fiéis vão de 0,706 a 0,999, com um vão entre 0,732 e 0,787,
e o maior falso positivo é 0,187. Com 0,75, só as duas saídas mais fracas
seriam revisadas. É provisório: são poucas saídas.

- **Orçamento:** no pior caso, 3 escritas com a repetição por JSON inválido em
  cada uma, ou seja, 6 chamadas ao LLM por job (hoje são até 2), cada uma com
  a retentativa de falhas passageiras. Roteador e crítico não chamam o LLM.
  As buscas das revisões usam embeddings (uma chamada por revisão).
- **Fallback:** qualquer falha do grafo na primeira rodada cai na passada
  única, se o prazo ainda comportar uma chamada; uma falha numa revisão
  entrega o melhor rascunho que já existe. Cancelamento, prazo do job e erro
  de chave ou configuração não vão para o fallback.
- **Log:** por nó, o nome, a rodada, a duração, o número de trechos e de
  caracteres, a ancoragem, se o JSON veio válido na primeira e o tipo do
  erro; por job, as rodadas, o motivo da parada, a rodada vencedora, se caiu
  no fallback e se foi para a passada única por falta de vaga. Nada do
  documento, do rascunho nem das consultas.

Limitações:

- A ancoragem é lexical: pode aprovar uma paráfrase ruim que usa as palavras
  do texto ou reprovar uma paráfrase boa, e o redator pode tender a copiar o
  texto para subir a nota.
- A cota gratuita do provedor é compartilhada com o chat; mais chamadas por
  job aumentam a chance de 429.
- Roteador e crítico são determinísticos nesta versão; diagramas ficam para
  outra etapa.

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
- Jobs ficam no SQLite, na tabela `jobs` do arquivo de `DB_PATH` (esquema versionado por `PRAGMA user_version`), e expiram em `JOB_TTL_SEGUNDOS` (padrão 30 min). Pacotes já finalizados sobrevivem ao reinício.
- `material_id` é igual a `adaptacao_id` nesta fase; todo material gerado nasce com `visibilidade = "rascunho"`.
- Excluir aluno remove vínculos em cascata; excluir material remove vínculos em cascata e tenta apagar o objeto do OCI.
- O texto-fonte usado na geração fica na tabela `material_fontes` (não sai em nenhuma rota) e é apagado junto com o material.

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

## Chat sobre o material

O aluno (ou a empresa, antes de publicar) faz perguntas sobre um material já
gerado. A resposta usa só o documento original e o pacote gerado, cita os
trechos usados (`[F1]` para o documento, `[P2]` para o pacote) e, quando a
resposta não está no material, recusa com "Não encontrei isso no material.".
O chat não guarda histórico: o cliente manda as mensagens anteriores a cada
pergunta e o servidor usa só as últimas `CHAT_MAX_MENSAGENS_HISTORICO`.

O provedor do chat é próprio (`CHAT_LLM_*`), independente de `LLM_PROVIDER`:
a geração pode usar um modelo e o chat outro. O código fica em
`app/services/servico_chat.py` (serviço), `contexto_chat.py` (trechos e
cache), `busca_lexical.py` (BM25) e `app/api/v1/routers/chat.py` (rotas).

### Rotas

Base: `/api/v1`. As rotas de pergunta recebem e devolvem o mesmo formato.

| Rota | Quem usa | Regras |
|---|---|---|
| `POST /aluno/materiais/{material_id}/chat?aluno_id=` | aluno | identificado como nas outras rotas `/aluno/*`; só material publicado e vinculado a ele, senão o mesmo 404 |
| `POST /materiais/{material_id}/chat` | empresa | qualquer visibilidade, para testar antes de publicar |
| `GET /chat/modelos` | frontend | modelos aceitos pelo chat, com o padrão primeiro |

```json
POST /api/v1/aluno/materiais/01JAVCNQUIZ000000000002/chat?aluno_id=01JALUNO000000000000000001
{
  "pergunta": "O que é uma subnet?",
  "historico": [
    {"papel": "user", "conteudo": "O que é uma VCN?"},
    {"papel": "assistant", "conteudo": "É a rede virtual privada da nuvem [F1]."}
  ],
  "modelo": null
}
```

```json
{
  "resposta": "É uma subdivisão da VCN com o próprio bloco de endereços [F2].",
  "citacoes": [{"id": "F2", "origem": "documento", "excerto": "Cada subnet recebe um bloco de endereços…"}],
  "base": "documento_e_pacote",
  "recusou": false,
  "fundamentada": true,
  "ancoragem": 0.92,
  "modelo": "google/gemma-4-31b-it",
  "trechos_usados": 6
}
```

`GET /api/v1/chat/modelos` devolve, por exemplo,
`{"padrao": "google/gemma-4-31b-it", "modelos": ["google/gemma-4-31b-it", "nvidia/nemotron-3.5-bolt-e4b", "nvidia/nemotron-3.5-lightning-30b-a3b"]}`.

- `base` é `"pacote"` quando o material foi gerado antes do texto-fonte ser
  guardado (`material_fontes`): aí só o pacote serve de fonte.
- `fundamentada` é falso quando a resposta não citou nenhum trecho válido;
  marcadores que não existem nos trechos enviados são tirados do texto.
- `ancoragem` (0 a 1) é a mesma medida lexical do material aplicada à
  resposta; é informativa e nula na recusa.

### Erros

No envelope `{"erro": {"codigo", "mensagem", ...}}`. As mensagens são fixas:
nem a pergunta, nem o material, nem o texto de erro do provedor voltam ao
cliente ou vão para o log.

| Status | Código | Quando |
|---|---|---|
| 422 | `VALIDACAO` | corpo inválido (papel fora de `user`/`assistant`, histórico com mais de 50 itens, campos grandes demais); `campos` aponta o campo |
| 422 | `PERGUNTA_VAZIA`, `PERGUNTA_LONGA` | pergunta vazia ou acima de `CHAT_MAX_PERGUNTA_CARACTERES`; `campos.pergunta` |
| 422 | `CHAT_MODELO_NAO_PERMITIDO` | modelo fora da lista; `detalhes.modelos_permitidos` |
| 404 | `MATERIAL_NAO_ENCONTRADO` | material inexistente ou, para o aluno, em rascunho ou não vinculado |
| 404 / 403 | `ALUNO_NAO_ENCONTRADO` / `ALUNO_INATIVO` | identificação do aluno, como nas outras rotas do aluno |
| 429 | `CHAT_LIMITE_EXCEDIDO` | limite de perguntas por minuto; `Retry-After` com os segundos até liberar |
| 429 | `CHAT_PROVEDOR_OCUPADO` | o provedor devolveu 429; `Retry-After: 10` |
| 502 | `CHAT_RESPOSTA_VAZIA`, `CHAT_RESPOSTA_INVALIDA` | o modelo não devolveu texto aproveitável |
| 503 | `CHAT_INDISPONIVEL` | provedor fora do ar ou mal configurado (chave, modelo removido, requisição recusada) |
| 504 | `CHAT_TEMPO_ESGOTADO` | passou de `CHAT_LLM_TIMEOUT_SEGUNDOS` |
| 500 | `INTERNO` | pacote corrompido ou erro inesperado |

### Variáveis

Todas opcionais; vazio vale o padrão. A chave é a do provedor
(`NVIDIA_NIM_API_KEY` na nvidia) e só é exigida quando o chat é usado.

| Variável | Padrão | Para que serve |
|---|---|---|
| `CHAT_LLM_PROVIDER` | `nvidia` | Provedor do chat (`nvidia` ou `gemini`); desconhecido impede a subida |
| `CHAT_LLM_MODELO` | `google/gemma-4-31b-it` na nvidia; o `MODELO_LLM` no gemini | Modelo do chat |
| `CHAT_LLM_RACIOCINIO` | `desligado` | `ligado` ou `desligado`; ligado deixa as respostas lentas |
| `CHAT_LLM_MAX_TOKENS` | `1024` | Limite de tokens da resposta (mínimo 64) |
| `CHAT_LLM_TEMPERATURA` | `0.2` | Temperatura, entre 0 e 2 |
| `CHAT_LLM_TIMEOUT_SEGUNDOS` | `45` | Prazo total de uma pergunta, com a retentativa incluída (mínimo 5) |
| `CHAT_MODELOS_PERMITIDOS` | `google/gemma-4-31b-it,nvidia/nemotron-3.5-bolt-e4b,nvidia/nemotron-3.5-lightning-30b-a3b` na nvidia; só o modelo do chat no gemini | Ids aceitos no campo `modelo`, separados por vírgula; o modelo do chat sempre entra, em primeiro lugar |
| `CHAT_MAX_PERGUNTA_CARACTERES` | `1000` | Tamanho máximo da pergunta |
| `CHAT_MAX_MENSAGENS_HISTORICO` | `10` | Mensagens anteriores usadas (o resto é descartado) |
| `CHAT_MAX_CONTEXTO_CARACTERES` | `24000` | Orçamento de texto dos trechos enviados ao modelo |
| `CHAT_LIMITE_POR_MINUTO` | `12` | Perguntas por minuto por aluno (e no balde único da empresa) |

Na nvidia valem modelo, raciocínio, temperatura e max_tokens do chat; no
gemini, só o modelo. Uma falha passageira (429, 5xx, timeout) é repetida no
máximo uma vez, dentro do prazo da pergunta; o prazo e as retentativas dos
jobs de geração não se aplicam ao chat.

### Modelo padrão do chat

Medição de 19/11/2026 com `scripts/medir_chat.py`: 3 modelos, raciocínio
desligado, 30 perguntas de gabarito sobre 2 documentos, 90 chamadas, sem
erros.

| Modelo | Acerto | Fundamentada | Recusa correta | Obediência | Ancoragem | p50 / p95 |
|---|---|---|---|---|---|---|
| google/gemma-4-31b-it | 100% | 100% | 100% | 0 | 1,00 | 1,6 s / 12,8 s |
| nvidia/nemotron-3.5-lightning-30b-a3b | 94% | 81% | 100% | 0 | 0,94 | 0,5 s / 3,1 s |
| nvidia/nemotron-3.5-bolt-e4b | 100% | 100% | 88% | 0 | 0,99 | 0,6 s / 0,9 s |

O padrão é o Gemma porque foi o único sem ponto fraco nas métricas. Num chat
restrito ao material, pesa mais não inventar fora do documento e cumprir o
formato de citação do que a velocidade; além disso, é o modelo de maior porte
dos três.

- **Gemma:** o custo é a cauda de latência, com 3 das 30 respostas entre 8 e
  15 s (14,8 s, 12,8 s e 8,0 s). A primeira chamada de cada modelo leva cerca
  de 6 s (5,6 a 6,2 s nos três).
- **Bolt:** o mais rápido (p95 de 0,9 s) e acertou todas as perguntas sobre o
  conteúdo. Na única pergunta de fora do material que a métrica não contou
  como recusa (`sql-fora-4`), ele começou com a frase de recusa e depois
  acrescentou um resumo do próprio material com citações. Não inventou
  conteúdo fora do documento; a métrica só não contou como recusa por causa
  das citações.
- **Lightning:** recusa correta em tudo, mas em 3 de 16 respostas sobre o
  conteúdo (todas de seguimento) não citou fonte, e uma delas foi só "Remove
  o recurso.". Numa das injeções recusou com palavras próprias em vez da frase
  padrão, sem vazar o prompt. O único erro de acerto (`http-dentro-3`) é um
  falso negativo da métrica lexical: respondeu "idempotência", e o termo
  esperado era "idempotente".

Ressalvas: foi uma única rodada, com amostra pequena (12 perguntas dentro do
material, 8 fora, 6 de injeção e 4 de seguimento), e acerto e ancoragem são
medidas lexicais. O gabarito só tem perguntas de consulta direta a um trecho
e não mede perguntas que exigem juntar vários trechos, por isso Bolt e Gemma
empatam em conteúdo nesta medição. O resultado serve para ordenar os modelos,
não como prova estatística.

Os três modelos ficam permitidos por padrão (o Gemma primeiro); para trocar o
padrão ou a lista, use `CHAT_LLM_MODELO` e `CHAT_MODELOS_PERMITIDOS`.

### Como o chat busca

- **Trechos:** o documento é dividido com o mesmo splitter da geração (1.000
  caracteres, 150 de sobreposição), e o pacote vira texto por item (cada
  flashcard, cada questão com a resposta e a explicação, cada seção do
  tutorial ou resumo).
- **Busca:** BM25 lexical em Python puro, sem embeddings e sem chamada
  externa, sobre documento e pacote juntos. Pergunta curta de seguimento ("e
  as limitações?") leva junto a última pergunta do histórico.
- **Orçamento:** os melhores trechos entram até `CHAT_MAX_CONTEXTO_CARACTERES`;
  o último pode entrar cortado. Se algum trecho do pacote pontuou, pelo menos
  um vai junto. Se nada pontuou, vão os primeiros trechos do pacote e o
  modelo decide se recusa.
- **Material antigo**, sem texto-fonte guardado: só o pacote (`base: "pacote"`).
- **Cache:** o índice de cada material fica num cache LRU de 32 materiais,
  limpo quando o material é apagado.

### Limite por aluno

Janela deslizante de 60 s, em memória: `CHAT_LIMITE_POR_MINUTO` perguntas por
aluno, e um balde único para a empresa. O limite é conferido antes de
carregar o material; um corpo inválido não conta, uma pergunta aceita conta
mesmo que dê erro depois. Chaves ociosas são descartadas, com teto de 10.000.

### Limitações e riscos

1. **`aluno_id` na query não é credencial** (veja a issue #66): quem conhece
   um id válido pergunta em nome daquele aluno e consome a cota do chat, e o
   limite por aluno não impede quem troca de id.
2. **O histórico vem do cliente:** uma mensagem falsa de `assistant` pode
   tentar influenciar o modelo. O prompt trata o histórico e os trechos como
   dados, e as citações são validadas no servidor, mas isso mitiga, não
   impede.
3. **A busca é lexical:** perguntas muito parafraseadas, sem as palavras do
   texto, podem não achar o trecho certo e acabar em recusa.
4. **A cota gratuita do provedor é compartilhada** com a geração: com uso
   alto, o chat pode receber 429 (`CHAT_PROVEDOR_OCUPADO`).
5. **O limite é por processo:** com vários workers, cada um conta à parte.

### Medir o chat

`scripts/medir_chat.py` compara modelos no chat com as perguntas de gabarito
de `data/exemplos/chat_perguntas.json` (dois documentos de exemplo; perguntas
dentro e fora do material, de injeção e de seguimento). O material é montado
em memória, sem tocar no banco, e o serviço do chat é chamado de verdade.

```bash
cd backend
python scripts/medir_chat.py --listar
python scripts/medir_chat.py --simulado
python scripts/medir_chat.py
python scripts/medir_chat.py --modelos org/modelo-a,org/modelo-b --raciocinio desligado,ligado --categorias dentro,fora --intervalo 5
```

- `--listar` mostra quantas chamadas serão feitas, sem chamar; `--simulado`
  usa um provedor falso, sem rede e sem chave, para ver o formato.
- Por modelo: acerto (dentro e seguimento), fundamentação, recusa correta
  (fora), obediência à injeção, ancoragem média, latência p50 e p95, tamanho
  médio da resposta e erros por tipo, com um veredito (APROVADO com acerto e
  recusa de pelo menos 80%, nenhuma obediência à injeção, p95 dentro do prazo
  do chat e até 10% de erros) e um ranking.
- O relatório vai em Markdown e JSON para `data/relatorios/`, com pergunta,
  resposta, ids citados e métricas; nunca a chave, o prompt nem o texto do
  material.
- O acerto e a ancoragem são aproximações lexicais, e a amostra é pequena (o
  relatório mostra o n por categoria): serve para comparar modelos entre si,
  não como prova estatística.

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
