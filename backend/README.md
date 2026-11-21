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

### Backup e restauração

Tudo o que importa fica num único arquivo SQLite (`DB_PATH`): jobs, histórico,
materiais, alunos e vínculos. O **ChromaDB é descartável**: é só o índice de
trabalho da geração, a subida o limpa sozinha e ele **não entra no backup**
nem precisa ser restaurado.

| Variável | Padrão | Descrição |
|---|---|---|
| `BACKUP_DIR` | `./data/backups` | Pasta dos backups, relativa à pasta de execução (`backend/`). Criada se não existir. Já ignorada pelo git. |
| `BACKUP_RETENCAO` | `7` | Quantos backups manter (mínimo 1). Valor menor que 1 ou não numérico impede a subida e o script. |

**Gerar um backup** (com o backend rodando ou parado):

```bash
cd backend
python -m app.scripts.backup
# no Docker Compose:
docker compose exec backend python -m app.scripts.backup
```

- Usa a API de backup do `sqlite3`: a cópia é consistente mesmo com o backend
  gravando. A origem é aberta só para leitura.
- O arquivo se chama `novamente-AAAAMMDD-HHMMSS.db` (hora UTC), é gravado
  primeiro como temporário na mesma pasta e só ganha o nome final depois de
  passar no `PRAGMA integrity_check` e de ter ao menos uma tabela. Fica com
  permissão `600`, pois contém dados de alunos.
- A retenção roda depois de um backup bem-sucedido e apaga os mais antigos
  (pela data do nome), mantendo os `BACKUP_RETENCAO` mais recentes. Só mexe em
  arquivos que casam exatamente com `novamente-AAAAMMDD-HHMMSS.db`; qualquer
  outro arquivo da pasta é ignorado.
- Códigos de saída: `0` sucesso; `1` falha (banco não encontrado, pasta de
  backup inválida, verificação reprovada, configuração inválida); `2` backup
  gerado, mas a retenção não conseguiu apagar algum arquivo antigo.
- O script copia o arquivo de `DB_PATH`. Se `DATABASE_URL` apontar para
  **outro** arquivo SQLite (fora do padrão), o catálogo não entra no backup e o
  script avisa em stderr. Mantenha os dois no mesmo arquivo.
- `BACKUP_DIR` no mesmo volume do banco não protege contra a perda do volume.
  Em produção, aponte para outro volume e copie os arquivos para fora do
  servidor. A agenda do backup e o envio ao OCI Object Storage ficam fora do
  backend (Compose).

**Restaurar um backup** (o backend precisa estar parado):

```bash
# 1. Pare o backend
docker compose stop backend

# 2. Guarde o banco atual (se existir) e traga o backup escolhido
cd backend/data
mv novamente.db novamente.db.antes-da-restauracao 2>/dev/null
cp backups/novamente-AAAAMMDD-HHMMSS.db novamente.db

# 3. Remova as sobras do banco antigo (arquivos do modo WAL)
rm -f novamente.db-wal novamente.db-shm

# 4. Suba o backend e confira
cd ../..
docker compose start backend
curl -s http://localhost:8000/api/v1/health   # "banco": "ok"
```

Sem Docker, pare o `uvicorn`, faça os passos 2 e 3 na pasta de `DB_PATH` e suba
de novo. Não troque o arquivo com o backend rodando: ele mantém conexões
abertas no arquivo antigo. Os jobs que estavam em andamento no backup voltam
como `failed`, como em qualquer reinício. Se o arquivo restaurado estiver
inutilizável, o procedimento é reversível: volte o `.antes-da-restauracao`.

**Subida segura:** antes de criar o esquema, o backend confere `DB_PATH` e o
arquivo de `DATABASE_URL` (`sqlite:///relativo.db` ou `sqlite:////absoluto.db`).
Com o volume vazio ou sem o arquivo, cria a pasta e o arquivo, e o esquema nasce
na sequência. Se o caminho não for gravável, a pasta não puder ser criada, o
caminho for uma pasta ou o arquivo não for um banco SQLite, a subida falha com
uma mensagem em português que diz o que conferir. Dados existentes não são
alterados nessa checagem.

**Estado no `GET /api/v1/health`:** o campo `banco` vale `ok` ou
`indisponivel`. É uma consulta curta (timeout de 1 s) nos arquivos SQLite
configurados, sem criar nada; a resposta não traz o caminho nem a mensagem do
erro. Como os demais campos, `indisponivel` marca `status: degraded` e o
endpoint continua respondendo `200`.

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

## Segurança do backend

Proteções de linha de base para expor o backend (por exemplo, na OCI). Todas
valem para um único processo; o contador de requisições e o teto de jobs ficam
em memória.

| Variável | Padrão | Descrição |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Origens permitidas no CORS, separadas por vírgula (`https://app.exemplo.com,https://painel.exemplo.com`). Espaços e entradas vazias são ignorados |
| `ARQUIVO_MAX_BYTES` | `10485760` (10 MiB) | Tamanho máximo do arquivo enviado em `POST /adaptacoes/upload` |
| `GERACAO_LIMITE_POR_MINUTO` | `6` | Gerações por minuto, por IP, em `POST /adaptacoes` e `POST /adaptacoes/upload` (inteiro, mínimo `1`) |
| `GERACAO_MAX_JOBS_SIMULTANEOS` | `4` | Jobs de geração em andamento ao mesmo tempo (inteiro, mínimo `1`) |
| `CONFIAR_X_FORWARDED_FOR` | `false` | Usa o `X-Forwarded-For` como IP do cliente no limite por IP. Só ligue atrás de um proxy confiável |

Valores inválidos (limite menor que 1, `CORS_ORIGINS` malformada) impedem a
subida, com a mensagem do campo.

### CORS

- As origens vêm de `CORS_ORIGINS`, cada uma no formato `esquema://host[:porta]`,
  sem barra final nem caminho. Origem fora da lista não recebe os cabeçalhos
  `Access-Control-*`, e o navegador bloqueia a leitura da resposta.
- `*` **impede a subida**: o CORS usa credenciais (`allow_credentials=True`), e
  liberar qualquer origem com credenciais é inseguro.
- Métodos: `GET`, `POST`, `PUT`, `PATCH`, `DELETE` e `OPTIONS`. Cabeçalhos:
  `Content-Type`, `Authorization`, `X-API-Key` e `Accept`. `Retry-After` fica
  visível ao navegador.
- O CORS é o middleware mais externo: as respostas 413 e 429 dos limites
  abaixo também levam os cabeçalhos de CORS.
- O frontend chama o backend por um *rewrite* do Next.js (`/api/v1/*`), então o
  navegador não faz requisição entre origens. O CORS importa para quem chama a
  API de outra origem (outro painel, ferramentas no navegador).

### Upload

O Starlette recebe o corpo multipart inteiro (e o grava em arquivo temporário)
antes de chamar a rota. Por isso a recusa acontece antes, em um middleware:

1. `Content-Length` acima de `ARQUIVO_MAX_BYTES` mais **64 KiB** de folga (campos
   do formulário e delimitadores do multipart): `413`, sem ler o corpo.
2. Envio sem `Content-Length` (em blocos): os bytes são contados e a leitura
   para ao passar do limite do corpo, também com `413`.
3. Na rota, o arquivo é lido em blocos de 64 KiB e a leitura para quando passa de
   `ARQUIVO_MAX_BYTES`. O tamanho já conhecido do arquivo é conferido antes de
   qualquer leitura.

A resposta é a mesma de antes: `413` com `{"erro": {"codigo": "LIMITE_EXCEDIDO", ...}}`.
Arquivo dentro do limite, extensão (`415`), tipo (`415`) e documento ilegível
(`400`) se comportam como antes. A mensagem do 413 deixou de informar quantos
bytes foram recebidos (a leitura para antes de saber).

### Limite de gerações por IP

`POST /api/v1/adaptacoes` e `POST /api/v1/adaptacoes/upload` dividem o mesmo
limite por IP, numa janela deslizante de 1 minuto. Acima de
`GERACAO_LIMITE_POR_MINUTO`:

```json
HTTP 429  Retry-After: 37
{"erro": {"codigo": "LIMITE_EXCEDIDO", "mensagem": "Muitas gerações em pouco tempo. Tente novamente em 37 segundos."}}
```

- `Retry-After` é inteiro, arredondado para cima, em segundos.
- **Só a requisição que cria um job (`202`) consome o limite.** A vaga é
  reservada antes da rota e devolvida se a resposta não for `202` (validação
  `422`, `413`, `415`, `400`, `503`). Erro de preenchimento não esgota o limite de
  quem está usando o sistema. Em troca, o limite não freia quem só envia
  requisições inválidas (que não chamam o LLM).
- **IP do cliente:** por padrão, o IP da conexão. Com
  `CONFIAR_X_FORWARDED_FOR=true`, a **última** entrada do `X-Forwarded-For` (a que
  o proxy confiável acrescentou). As anteriores vêm do cliente e podem ser
  forjadas. Se o cabeçalho não tiver um IP válido, vale o IP da conexão.

> **Atenção: atrás do proxy do frontend o limite vira global.** O Next.js faz as
> chamadas ao backend a partir do servidor, então todas as requisições chegam
> com o IP do contêiner do frontend, e o limite por IP passa a valer para todos
> os usuários juntos. Para limitar por usuário, o proxy do frontend deve repassar
> o IP real em `X-Forwarded-For` e o backend deve subir com
> `CONFIAR_X_FORWARDED_FOR=true`. **Risco:** com a variável ligada e o backend
> alcançável sem passar pelo proxy, qualquer cliente envia um
> `X-Forwarded-For` falso e burla o limite. Ligue somente se a porta do backend
> estiver acessível apenas pelo proxy.

### Teto de jobs simultâneos

Cada geração abre uma thread. Em `criar_job`, antes de abrir a thread, o backend
conta os jobs `queued` ou `running` que ainda não expiraram. Com
`GERACAO_MAX_JOBS_SIMULTANEOS` jobs em andamento, a requisição é recusada, sem
gravar job nem abrir thread:

```json
HTTP 503  Retry-After: 30
{"erro": {"codigo": "GERACAO_OCUPADA", "mensagem": "O sistema está gerando outros materiais no momento. Tente novamente em instantes."}}
```

É `503` (e não `429`) porque a recusa é por capacidade do servidor, não por
excesso de requisições daquele cliente; assim o frontend distingue as duas
situações. A contagem e o registro do job usam a mesma trava, então duas
requisições simultâneas não passam juntas pelo último lugar. Um job que termina
(`succeeded`, `failed` ou `cancelled`) libera a vaga.

### Chaves e credenciais

- O código nunca grava `GOOGLE_API_KEY` nem credenciais do OCI em log ou em
  resposta. Os adaptadores do LLM registram só o tipo e o código da exceção.
- Como defesa extra, `app/core/redacao_logs.py` troca por `***`, em todos os logs
  (mensagem, argumentos e traceback com as causas encadeadas), o valor de
  `GOOGLE_API_KEY` e de toda variável de ambiente cujo nome termine em `API_KEY`,
  `SECRET`, `TOKEN`, `PASSWORD`, `PRIVATE_KEY` ou `ACCESS_KEY` (valores com menos
  de 8 caracteres são ignorados).
- `tests/test_segredos_logs.py` força falhas do provedor e dos embeddings com a
  chave dentro do texto da exceção e confere que ela não aparece nos logs, no
  job gravado nem nas respostas (inclusive `/health`, `/oci/status` e
  `/openapi.json`). Outro teste revisa por AST que nenhuma chamada de log recebe
  `settings`, a chave ou o ambiente.
- Limite conhecido: `GET /api/v1/oci/status` devolve o texto da exceção do OCI
  em `mensagem` quando a consulta falha. Ele não carrega credenciais, mas pode
  trazer detalhes de infraestrutura; prefira expô-lo apenas à área da empresa.

### CI de segurança

- `.github/workflows/seguranca.yml` (em `pull_request` e `push` para `develop` e
  `main`, com `contents: read`):
  - **gitleaks:** varre o histórico completo (`fetch-depth: 0`) com o binário
    oficial em contêiner, com a versão fixa na imagem, e `--redact` para não
    imprimir o segredo. Achado reprova o job. (Não usamos a `gitleaks-action`,
    que exige licença em repositórios de organização.) O `.gitleaks.toml` da raiz
    mantém as regras padrão e libera só valores fictícios de exemplos e testes
    (`chave-ficticia...` e `fake_key_for_ci_testing`). Outro falso positivo
    conhecido entra nesse arquivo, em `regexes`, ou em um `.gitleaksignore` com
    a impressão digital do achado.
  - **pip-audit** (backend) e **npm audit** (frontend): informativos
    (`continue-on-error`). O resultado aparece no log e, no backend, no resumo
    da execução; vulnerabilidades não reprovam o pipeline.
- `.github/dependabot.yml`: atualização semanal de `pip` (`/backend`), `npm`
  (`/frontend`) e `github-actions` (`/`), com no máximo 3 PRs abertos por
  ecossistema, apontando para `develop`.

### Limites conhecidos

- O contador por IP e o teto de jobs são **por processo**: com vários workers do
  uvicorn (ou várias réplicas), cada um conta à parte e o limite efetivo é
  multiplicado. Para mais de um processo, mova o contador para um armazenamento
  compartilhado.
- O contador é perdido quando o processo reinicia.
- IP atrás de proxy: veja o aviso acima.
- O limite do corpo vale só para o upload. Os corpos JSON das demais rotas não
  têm teto de bytes (o texto colado é limitado em caracteres só depois de lido).
- Um job que ficar `running` sem terminar (por exemplo, o processo morreu e o
  registro não foi atualizado) ocupa uma vaga até o TTL do job (`JOB_TTL_SEGUNDOS`,
  30 minutos por padrão); na subida, os jobs deixados em andamento são marcados
  como `failed`.
- O frontend precisa reconhecer o código `GERACAO_OCUPADA` (e tratar `429` e
  `503` com `Retry-After`) para mostrar uma mensagem amigável.
- Autenticação e proteção das rotas da empresa, migrations e WAF/HTTPS/rede da
  OCI estão fora deste escopo.

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

### Política de esquema (migrações)

No MVP não há migrações. A decisão (opção B da issue #67, a confirmar com o
Renato) é recriar o banco quando o esquema do catálogo mudar e impedir que o
backend suba com um arquivo de outra versão.

- **Escopo:** alunos, materiais e vínculos (modelos em `app/models/db.py`).
  O `create_all` só cria tabelas que não existem e nunca altera as existentes,
  por isso uma coluna, constraint ou índice novo não chegaria a um banco antigo.
  Jobs e a tabela `pacotes` seguem com o `PRAGMA user_version` próprio e não
  entram nesta verificação.
- **O que o banco guarda:** a tabela `esquema_catalogo`, com a versão do
  esquema e uma impressão digital (hash) das tabelas, colunas, índices e
  constraints dos modelos.
- **Duas proteções:**
  - `ESQUEMA_VERSAO` (em `app/core/esquema.py`) é um número que quem mudar um
    modelo incrementa na mesma alteração. Ele aparece na mensagem de erro.
  - A impressão digital é calculada sozinha a partir dos modelos. Se alguém
    mudar um modelo e esquecer de incrementar a versão, o hash diverge e a
    subida falha do mesmo jeito.
- **Na subida** (`repositorio.iniciar()`, logo depois do `create_all`):
  1. Banco novo ou sem `esquema_catalogo` (criado antes desta política): o
     backend compara as colunas, índices e constraints reais (`PRAGMA`) com os
     modelos. Se baterem, grava versão e impressão digital e segue; se não,
     falha.
  2. Banco com `esquema_catalogo`: se a versão ou a impressão digital forem
     diferentes das do código, falha.
  3. Banco na versão atual: sobe normalmente, sem gravar nada (subir duas
     vezes não muda o arquivo).
- **A falha** é um `EsquemaDefasadoError` (um `RuntimeError`) com mensagem em
  português dizendo o que divergiu e como recriar o banco. A verificação só lê
  o catálogo e só escreve em `esquema_catalogo`; nenhum job, pacote ou
  material é alterado ou apagado, nem quando ela falha.

**Ao mudar um modelo do catálogo**, antes da release:

1. Incremente `ESQUEMA_VERSAO` em `app/core/esquema.py`.
2. Registre a mudança no PR: quem tiver um banco local precisa recriá-lo.

**Como recriar o banco:**

- **Dev:** pare o backend, mova (ou apague) `backend/data/novamente.db` e os
  arquivos `novamente.db-wal` e `novamente.db-shm`, e suba de novo. As tabelas
  são criadas do zero.
- **OCI:** pare o container, mova ou apague o arquivo do banco no volume
  persistente (o caminho de `DATABASE_URL`, com `-wal` e `-shm`) e suba de novo.
  Sem dados reais antes da release, isso é aceitável.
- **Atenção:** com `DB_PATH` e `DATABASE_URL` no mesmo arquivo (o padrão),
  recriar o banco também apaga jobs e histórico de pacotes. Mova o arquivo em
  vez de apagá-lo se precisar de uma cópia.

**Depois da primeira release** (dados reais no volume da OCI), recriar deixa de
ser aceitável. Nesse momento a política deve migrar para a opção A: Alembic
com migrações versionadas, aplicadas na subida. O `ESQUEMA_VERSAO` e a tabela
`esquema_catalogo` podem ser substituídos pela tabela `alembic_version`.

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

## Proteção das rotas da empresa

O backend não tem sistema de usuários. As rotas da empresa, que expõem dados de
alunos (nome e e-mail) e permitem alterar o catálogo, podem ser protegidas por
uma chave compartilhada, enviada no cabeçalho `X-API-Key`.

| Variável | Obrigatória | Descrição |
|---|---|---|
| `API_KEY_EMPRESA` | — | Chave das rotas da empresa. Vazia ou só espaços = não configurada (rotas abertas) |

- **Com a variável definida**, `X-API-Key` ausente ou diferente responde `401` com
  o envelope `{"erro": {"codigo": "NAO_AUTORIZADO", "mensagem": "..."}}`. A resposta é a
  mesma nos dois casos e nunca traz a chave. A comparação é em tempo constante
  (`hmac.compare_digest`).
- **Sem a variável** (dev local e testes), tudo responde como antes e o backend
  registra um aviso no log, uma única vez, na primeira requisição a uma rota protegida.
- A chave é lida do ambiente (ou do `.env`, que está fora do git), nunca é logada
  e não deve ser commitada. O `.env.example` traz a variável sem valor.
- Em deploy público, defina a chave **antes** de expor o backend.

Rotas que exigem a chave:

| Grupo | Rotas |
|---|---|
| Alunos e vínculos | todas de `/alunos` e `/alunos/{id}/materiais` (inclusive os `GET`) |
| Materiais | todas de `/materiais` (inclusive os `GET`) |
| Adaptações | `POST /adaptacoes` e `POST /adaptacoes/upload` |
| Jobs | `DELETE /jobs/{id}` |

Continuam sem chave: `/aluno/*` (área do aluno), `/health`, `/oci/status`,
`GET /adaptacoes`, `GET /adaptacoes/{id}` (e `/download` e `/exportacao`),
`GET /jobs/{id}` e a documentação (`/docs`, `/redoc`, `/openapi.json`). As requisições
`OPTIONS` do CORS não são bloqueadas.

Exemplo (chave fictícia):

```bash
API_KEY_EMPRESA=chave-ficticia-de-exemplo uvicorn app.main:app --port 8000

curl -i http://localhost:8000/api/v1/alunos                                   # 401
curl -i -H "X-API-Key: chave-ficticia-de-exemplo" http://localhost:8000/api/v1/alunos   # 200
```

No Swagger UI (`/docs`), use o botão **Authorize** para informar a chave.

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
