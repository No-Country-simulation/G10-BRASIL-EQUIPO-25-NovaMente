# NovaMente — Spec do Frontend (MVP)

**Data:** 2026-10-21
**Status:** aprovada em design; aguardando revisão da spec escrita
**Escopo:** frontend Next.js + contrato HTTP consumido (backend FastAPI a implementar)

Fontes de verdade:

- `NovaMente–Sistema_Inteligente_de_Adaptacao_e_Geracao_de_Conteudo_Educacional.pdf` — escopo e requisitos do hackathon ONE G10.
- `master_prompt_superpowers_novamente_frontend.md` — stack, princípios SOLID e fases de execução.
- Este documento — resolve as divergências entre os dois e fixa o contrato.

Quando este documento e o briefing divergirem, **este documento vence**. A seção 14 registra cada divergência e o motivo.

---

## 1. Objetivo

Entregar a interface do NovaMente capaz de receber um documento técnico (PDF, Markdown ou texto colado), parametrizar o material didático e apresentar o pacote gerado pelo pipeline RAG + LLM, com rastreabilidade da ancoragem na fonte e do armazenamento no OCI Object Storage.

Sucesso significa:

1. Um visitante consegue gerar um material didático em menos de três minutos, sem ler instruções.
2. Os quatro formatos de saída são renderizados com visualização própria.
3. O pacote é reaberto depois por URL própria, baixado em JSON e exportado em Markdown, PDF ou CSV-Anki.
4. O estado da geração (etapas, progresso, falha, cancelamento) é visível e recuperável.
5. O frontend funciona por completo contra mocks antes de o backend existir, sem alterar uma linha de serviço quando o backend entrar.

O público do MVP é a banca do hackathon e o time do projeto. Não há usuários autenticados, cobrança ou multilocação.

---

## 2. Escopo

### Dentro

- Formulário de ingestão com duas origens: texto colado e upload de arquivo.
- Parâmetros: título, perfil, formato, nicho e nível de detalhe.
- Geração assíncrona com job, etapas e polling.
- Visualizadores: Flashcards (flip 3D), Quiz interativo, Tutorial e Resumo Executivo (markdown).
- Painel OCI com score de ancoragem, clareza pedagógica e status do upload.
- Histórico paginado e filtrável, reabertura por id.
- Download do JSON do pacote e exportação em MD, PDF e CSV-Anki.
- Status do bucket OCI e health check da API.
- Duas skins dark trocáveis e persistidas.
- Massa de demonstração com quatro fixtures e três atalhos de cenário.

### Fora

- Autenticação, usuários, permissões.
- Roteiro de Aula / Vídeo (quinto formato citado no PDF).
- Reenvio de upload ao OCI após falha.
- Streaming SSE das etapas.
- Internacionalização (apenas pt-BR).
- Renderização de dados em Server Component.
- Configuração de deploy, proxy reverso e hospedagem.
- Multimodal (interpretação de diagramas).
- Persistência de tentativas do quiz.
- Edição ou regeneração parcial do conteúdo gerado.
- Administração do bucket (criar, apagar, listar objetos).
- Versionamento de pacote gerado: pacote é imutável.

---

## 3. Decisões

| # | Decisão | Alternativa descartada | Motivo |
|---|---|---|---|
| D1 | Contrato definido nesta spec, do zero | Alinhar a backend existente | Backend ainda não existe |
| D2 | Quatro formatos de saída | Incluir Roteiro de Aula | Briefing define quatro; roteiro exigiria renderizador próprio |
| D3 | `nivel_detalhe` incluído | Ignorar campo do PDF | O PDF o usa no exemplo de requisição |
| D4 | Duas rotas de criação (JSON e multipart) | Um endpoint híbrido | Evita `arquivo` e `documento_conteudo` mutuamente exclusivos no mesmo tipo |
| D5 | Job assíncrono com polling | Requisição síncrona | Pipeline RAG+LLM excede timeout de proxy; permite etapas reais |
| D6 | Histórico global, sem auth | Login de usuários | Edital não exige; demo sem atrito |
| D7 | Exportação gerada no backend | Montar MD/CSV no cliente | Uma única fonte do formato; arquivo exportado bate com o pacote salvo |
| D8 | Stack completa (shadcn, TanStack Query, Zustand, RHF/zod, MSW, Storybook, Playwright) | Conjunto mínimo | Mocks de rede e testes de componente são requisito de qualidade |
| D9 | Monorepo `frontend/` + `backend/` | Next na raiz | O backend FastAPI viverá no mesmo repositório |
| D10 | Apenas local, rewrites `/api` | Vercel + CORS | Sem hospedagem definida nesta fase |
| D11 | Dark com duas skins trocáveis | Tema claro | Direção visual escolhida; tokens permitem expansão |
| D12 | Quatro fixtures + três atalhos | Só Flashcards e Quiz | Edital exige três cenários e mais de um formato |
| D13 | Discriminante `tipo` no conteúdo | União estreitada por `metadados` | Permite união discriminada validada por zod |
| D14 | `status: 'sucesso'` literal | `'sucesso' \| 'erro'` | Erro é transporte HTTP, não pacote |
| D15 | Limites: 10 MB / 50.000 caracteres | 5 MB ou 25 MB | Equilíbrio entre manuais reais e custo de embeddings |
| D16 | Rotas em português | Rotas em inglês | Coerência com os campos JSON do edital |
| D17 | `/api/v1` versionado | `/api` | Permite quebrar contrato sem derrubar cliente |
| D18 | Cancelamento de job incluído | Sem cancelamento | Evita custo de LLM/embeddings em job abandonado |
| D19 | Navegar para `/resultado/[id]` no sucesso | Renderizar inline | URL recarregável e compartilhável |
| D20 | Atalhos de demo sempre visíveis | Só em modo mock | Simplifica a apresentação do hackathon |
| D21 | Cobertura ≥ 80% em `features/` e `services/` | Sem meta numérica | Regressão silenciosa em hook de job é caro |
| D22 | axe automatizado nas rotas + revisão manual | Só revisão manual | Falha crítica de a11y bloqueia conclusão |

---

## 4. Arquitetura

### 4.1 Princípios aplicados

- **SRP** — componente só renderiza; regra de negócio mora em hook; transporte mora em serviço.
- **OCP** — formato novo é uma entrada no registry de renderizadores, sem tocar em página.
- **ISP** — cada visualizador recebe apenas o recorte de dados que usa.
- **DIP** — hooks dependem de `NovaMenteApi`; a implementação HTTP é injetada uma vez no provider.

### 4.2 Camadas

```
UI (components/)
  └── hooks (features/)          regra de fluxo, estado derivado
        └── serviço (services/)   NovaMenteApi
              └── transporte     fetch('/api/v1/...')  ← MSW intercepta em dev/test
```

Nenhum componente importa `fetch`, `apiClient` ou schema diretamente. Nenhum serviço conhece React. Nenhum hook conhece Tailwind.

### 4.3 Estrutura de pastas

```
frontend/
  src/
    app/
      layout.tsx                 AppShell, fontes, script anti-flash de skin
      page.tsx                   / (gerar)
      resultado/[id]/page.tsx    /resultado/[id]
      historico/page.tsx         /historico
      providers.tsx              QueryClientProvider, ThemeProvider
    components/
      ui/                        Button, Card, Badge, Skeleton, Tabs, Select,
                                 SegmentedControl, Dropzone, Tooltip, ProgressBar,
                                 EmptyState, ErrorState, ScoreGauge
      forms/
        IngestionForm.tsx
        campos/                  PerfilField, FormatoField, NichoField, NivelField,
                                 TextoField, ArquivoField
      views/
        ContentRenderer.tsx
        FlashcardDeck.tsx
        FlashcardCard.tsx
        InteractiveQuiz.tsx
        MarkdownView.tsx
        OCIPanel.tsx
        JobProgress.tsx
        ResultadoHeader.tsx
        ExportMenu.tsx
      layout/
        AppShell.tsx
        Header.tsx
        SkinSwitcher.tsx
        HealthBanner.tsx
    features/
      adaptations/useAdaptationForm.ts
      adaptations/useCreateAdaptation.ts
      adaptations/useAdaptation.ts
      adaptations/useAdaptationHistory.ts
      adaptations/useExport.ts
      jobs/useAdaptationJob.ts
      oci/useOciStatus.ts
      health/useHealth.ts
      theme/useSkin.ts
    services/
      api/NovaMenteApi.ts        interface (contrato de serviço)
      api/httpApiClient.ts       implementação fetch
      api/endpoints.ts           construção de URLs e query strings
      api/erros.ts               normalização de erro HTTP → ApiProblema
      api/ApiProvider.tsx        contexto que injeta a implementação
    types/
      schemas.ts                 zod — fonte única de verdade
      novamente.ts               reexporta tipos inferidos com os nomes do briefing
      api.ts                     envelopes de job, página, erro, OCI, health
    mocks/
      browser.ts                 setupWorker
      server.ts                  setupServer (testes)
      handlers/                  adaptacoes, jobs, oci, health
      fixtures/                  4 pacotes JSON
      estadoJobs.ts              simulação em memória do ciclo do job
    themes/
      tokens.css                 CSS vars por skin
      registry.ts                skins: violeta, ciano
    styles/
      globals.css
    lib/
      cn.ts
      constants.ts               rótulos pt-BR, faixas de score, limites
      mensagens.ts               todos os textos de UI
      formatadores.ts            data relativa, bytes, percentual, slug
```

### 4.4 Registry de renderizadores (OCP)

```ts
// components/views/ContentRenderer.tsx
type RendererProps = { conteudo: ConteudoAdaptado };

const RENDERIZADORES: Record<ConteudoAdaptado['tipo'], ComponentType<RendererProps>> = {
  flashcards: FlashcardDeck,
  quiz: InteractiveQuiz,
  markdown: MarkdownView,
};

export function ContentRenderer({ conteudo }: { conteudo: ConteudoAdaptado }) {
  const Renderer = RENDERIZADORES[conteudo.tipo];
  return <Renderer conteudo={conteudo} />;
}
```

`FlashcardDeck` recebe `conteudo.itens` e ignora o resto; `InteractiveQuiz` idem; `MarkdownView` recebe `titulo`, `introducao_contextualizada` e `itens`. `ContentRenderer` é o único que conhece o tipo união.

### 4.5 Interfaces de serviço (DIP)

```ts
export interface NovaMenteApi {
  criarPorTexto(input: AdaptacaoInput): Promise<JobResposta>;
  criarPorArquivo(input: AdaptacaoUploadInput): Promise<JobResposta>;
  obterJob(jobId: string): Promise<JobResposta>;
  cancelarJob(jobId: string): Promise<JobResposta>;
  listar(params: ListarAdaptacoesParams): Promise<PaginaAdaptacoes>;
  obter(adaptacaoId: string): Promise<AdaptacaoPacote>;
  baixarJson(adaptacaoId: string): Promise<Blob>;
  exportar(adaptacaoId: string, formato: FormatoExportacao): Promise<Blob>;
  statusOci(): Promise<OciStatus>;
  health(): Promise<HealthResposta>;
}
```

`httpApiClient` é a única implementação. Não existe `mockApiClient`: o mock é de rede (MSW), então o mesmo cliente serve dev, teste, Storybook e produção.

### 4.6 Estado

| Tipo de estado | Ferramenta | Chaves |
|---|---|---|
| Servidor | TanStack Query | `['health']`, `['oci-status']`, `['job', jobId]`, `['adaptacao', id]`, `['adaptacoes', filtros]` |
| Formulário | react-hook-form + zodResolver | — |
| UI persistida | Zustand + `persist` | `novamente.skin` |
| UI efêmera | `useState` local | aba ativa, índice do card, resposta do quiz |

Parâmetros de query:

- `['job', jobId]`: `refetchInterval` de 1.500 ms, 3.000 ms após 60 s de job; `refetchIntervalInBackground: false`; para em status terminal.
- `['adaptacoes', filtros]`: `staleTime` 30 s.
- `['adaptacao', id]`: `staleTime` infinito (pacote imutável).
- `['oci-status']`: `staleTime` 30 s.
- `['health']`: `refetchInterval` 60 s.
- Nenhum retry automático em `4xx`; até 2 retries em erro de rede.

---

## 5. Contrato de dados

### 5.1 Enums

```ts
export type PerfilDestinatario = 'Iniciante' | 'Desenvolvedor' | 'LiderTecnico' | 'Gestor';
export type FormatoSaida = 'Flashcards' | 'Quiz' | 'Tutorial' | 'ResumoExecutivo';
export type NichoSetor = 'Fintech' | 'Saude' | 'Ecommerce' | 'Geral';
export type NivelDetalhe = 'Didatico' | 'Tecnico' | 'Executivo';
export type OrigemDocumento = 'upload' | 'texto';
export type FormatoExportacao = 'md' | 'pdf' | 'csv';
```

Rótulos de exibição (não fazem parte do contrato; vivem em `lib/constants.ts`):

| Enum | Rótulo |
|---|---|
| `Iniciante` | Iniciante / Transição de Carreira |
| `Desenvolvedor` | Desenvolvedor Júnior / Pleno |
| `LiderTecnico` | Líder Técnico / Arquiteto |
| `Gestor` | Gestor / Executivo (Não Técnico) |
| `Saude` | Saúde |
| `Ecommerce` | E-commerce |
| `ResumoExecutivo` | Resumo Executivo (TL;DR) |
| `Didatico` | Didático |
| `Tecnico` | Técnico |
| `Executivo` | Executivo |

### 5.2 Entrada

```ts
export interface AdaptacaoInput {
  documento_titulo: string;          // 3..150 caracteres
  documento_conteudo: string;        // 200..50000 caracteres
  perfil_destinatario: PerfilDestinatario;
  formato_saida: FormatoSaida;
  nicho_setor: NichoSetor;
  nivel_detalhe: NivelDetalhe;
}

export interface AdaptacaoUploadInput {
  arquivo: File;                     // .pdf, .md, .txt; até 10 MiB
  documento_titulo: string;
  perfil_destinatario: PerfilDestinatario;
  formato_saida: FormatoSaida;
  nicho_setor: NichoSetor;
  nivel_detalhe: NivelDetalhe;
}
```

`documento_conteudo` **não existe** em `AdaptacaoUploadInput`: a origem do texto é o arquivo. O formulário garante isso por tipo.

Limites, validados no cliente e revalidados no servidor (servidor é a autoridade):

| Item | Regra |
|---|---|
| Título | 3 a 150 caracteres após `trim` |
| Texto colado | 200 a 50.000 caracteres após `trim` |
| Arquivo | ≤ 10 MiB (10.485.760 bytes) |
| Extensões | `.pdf`, `.md`, `.txt` |
| MIME aceitos | `application/pdf`, `text/markdown`, `text/x-markdown`, `text/plain` |

### 5.3 Pacote gerado

```ts
export interface DocumentoRef {
  titulo: string;
  origem: OrigemDocumento;
  nome_arquivo?: string;
  tamanho_bytes?: number;
}

export interface MetadadosAdaptacao {
  perfil_aplicado: PerfilDestinatario;
  formato_gerado: FormatoSaida;
  nivel_detalhe_aplicado: NivelDetalhe;
  nicho_setor_aplicado: NichoSetor;
  tempo_estimado_estudo_minutos: number;   // inteiro >= 1
  conceitos_chave: string[];               // 1..12 itens
}

export interface FlashcardItem {
  frente: string;
  verso: string;
  dica_didatica?: string;
}

export interface QuizItem {
  pergunta: string;
  opcoes: string[];                        // 2..6
  resposta_correta: number;                // índice válido em opcoes
  explicacao: string;
}

export type ConteudoAdaptado =
  | { tipo: 'flashcards'; titulo: string; introducao_contextualizada: string; itens: FlashcardItem[] }
  | { tipo: 'quiz';       titulo: string; introducao_contextualizada: string; itens: QuizItem[] }
  | { tipo: 'markdown';   titulo: string; introducao_contextualizada: string; itens: string };

export interface AvaliacaoQualidade {
  ancoragem_fonte_score: number;           // 0..1
  clareza_pedagogica: 'Alta' | 'Media' | 'Baixa';
  observacoes?: string;
}

export interface ArmazenamentoOci {
  bucket: string;
  objeto_id: string;
  status_upload: 'concluido' | 'falha';
}

export interface AdaptacaoPacote {
  adaptacao_id: string;                    // ULID
  status: 'sucesso';
  criado_em: string;                       // ISO 8601 UTC
  documento: DocumentoRef;
  metadados: MetadadosAdaptacao;
  conteudo_adaptado: ConteudoAdaptado;
  avaliacao_qualidade: AvaliacaoQualidade;
  armazenamento_oci: ArmazenamentoOci;
}
```

Regras de consistência, validadas por `superRefine`:

- `conteudo_adaptado.tipo` deve corresponder a `metadados.formato_gerado`: `Flashcards→flashcards`, `Quiz→quiz`, `Tutorial|ResumoExecutivo→markdown`.
- Em `quiz`, `resposta_correta` deve estar dentro de `0..opcoes.length-1`.
- Em `flashcards`, `itens` tem 3 a 30 cartões.
- `itens` markdown tem no mínimo 40 caracteres.
- `status_upload: 'falha'` nunca invalida o pacote: o conteúdo continua renderizável e o download do JSON continua disponível (o pacote é servido pelo backend, não lido do bucket pelo cliente). A UI apenas avisa que a persistência no OCI falhou.

### 5.4 Job

```ts
export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export type EtapaJob =
  | 'extraindo' | 'chunking' | 'embeddings'
  | 'gerando' | 'revisando' | 'armazenando';

export interface JobResposta {
  job_id: string;
  status: JobStatus;
  etapa_atual: EtapaJob | null;
  etapas_concluidas: EtapaJob[];
  progresso_percentual: number;            // 0..100, monotônico
  mensagem?: string;
  iniciado_em: string;
  atualizado_em: string;
  adaptacao_id?: string;                   // presente em succeeded
  resultado?: AdaptacaoPacote;             // presente em succeeded
  erro?: ApiProblema['erro'];              // presente em failed
}
```

Faixas de progresso acordadas entre backend e UI (o backend não é obrigado a atingir cada valor, apenas a respeitar a ordem):

| Etapa | Rótulo | Faixa |
|---|---|---|
| `extraindo` | Extraindo texto | 0–20 |
| `chunking` | Segmentando conteúdo | 20–35 |
| `embeddings` | Gerando embeddings | 35–55 |
| `gerando` | Redigindo material | 55–80 |
| `revisando` | Revisando fidelidade | 80–90 |
| `armazenando` | Salvando no OCI | 90–100 |

Jobs vivem em memória por 30 minutos. Após reinício do backend, `GET /jobs/{id}` responde `404 JOB_NAO_ENCONTRADO` e a UI oferece "Tentar novamente".

### 5.5 Envelopes

```ts
export interface ApiProblema {
  erro: {
    codigo:
      | 'VALIDACAO' | 'ARQUIVO_INVALIDO' | 'DOCUMENTO_ILEGIVEL' | 'LIMITE_EXCEDIDO'
      | 'ADAPTACAO_NAO_ENCONTRADA' | 'JOB_NAO_ENCONTRADO' | 'JOB_FINALIZADO'
      | 'FORMATO_INCOMPATIVEL' | 'FORMATO_DESCONHECIDO' | 'OCI_INDISPONIVEL'
      | 'INTERNO';
    mensagem: string;                      // exibível ao usuário
    campos?: Record<string, string>;       // erro por campo do formulário
    request_id?: string;
  };
}

export interface AdaptacaoResumo {
  adaptacao_id: string;
  criado_em: string;
  documento: DocumentoRef;
  perfil_aplicado: PerfilDestinatario;
  formato_gerado: FormatoSaida;
  nivel_detalhe_aplicado: NivelDetalhe;
  tempo_estimado_estudo_minutos: number;
  ancoragem_fonte_score: number;
  status_upload: 'concluido' | 'falha';
  conceitos_chave: string[];               // até 6
}

export interface PaginaAdaptacoes {
  itens: AdaptacaoResumo[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
}

export interface OciStatus {
  configurado: boolean;
  bucket?: string;
  regiao?: string;
  total_objetos?: number;
  bytes_armazenados?: number;
  ultimo_upload_em?: string;
  mensagem?: string;
  verificado_em: string;
}

export interface HealthResposta {
  status: 'ok' | 'degraded';
  versao: string;
  oci: 'ok' | 'indisponivel';
  llm: 'ok' | 'indisponivel';
  verificado_em: string;
}
```

### 5.6 Zod como fonte única

`src/types/schemas.ts` contém todos os schemas acima (com `.strict()` nos objetos de entrada). `src/types/novamente.ts` reexporta `z.infer` com os nomes públicos:

```ts
export type AdaptacaoPacote = z.infer<typeof AdaptacaoPacoteSchema>;
```

Assim existe um lugar só para mudar o contrato, e os fixtures são validados pelo mesmo schema que valida a resposta da API.

---

## 6. Contrato HTTP

Base: `/api/v1`. Sem autenticação. Sem `PUT`/`PATCH`. Todas as respostas em `application/json; charset=utf-8`, salvo download/exportação.

Em desenvolvimento, `next.config.ts` aplica:

```ts
async rewrites() {
  return [{
    source: '/api/v1/:path*',
    destination: `${process.env.API_BASE_URL ?? 'http://localhost:8000'}/api/v1/:path*`,
  }];
}
```

O cliente sempre usa caminho relativo — não há `NEXT_PUBLIC_API_URL`.

### 6.1 Resumo

| # | Método | Rota | Função | Sucesso |
|---|---|---|---|---|
| 1 | POST | `/adaptacoes` | Job a partir de texto (JSON) | 202 |
| 2 | POST | `/adaptacoes/upload` | Job a partir de arquivo (multipart) | 202 |
| 3 | GET | `/jobs/{job_id}` | Estado do job | 200 |
| 4 | DELETE | `/jobs/{job_id}` | Cancela job | 200 |
| 5 | GET | `/adaptacoes` | Histórico paginado | 200 |
| 6 | GET | `/adaptacoes/{id}` | Pacote completo | 200 |
| 7 | GET | `/adaptacoes/{id}/download` | JSON do pacote | 200 |
| 8 | GET | `/adaptacoes/{id}/exportacao` | MD / PDF / CSV | 200 |
| 9 | GET | `/oci/status` | Saúde do bucket | 200 |
| 10 | GET | `/health` | Liveness e dependências | 200 |

### 6.2 `POST /adaptacoes`

Requisição `application/json` com `AdaptacaoInput`.

```json
{
  "documento_titulo": "Introdução à Arquitetura de Redes VCN na OCI",
  "documento_conteudo": "A Virtual Cloud Network (VCN) é uma rede privada e personalizável configurada na Oracle Cloud Infrastructure...",
  "perfil_destinatario": "Iniciante",
  "formato_saida": "Flashcards",
  "nicho_setor": "Geral",
  "nivel_detalhe": "Didatico"
}
```

Resposta `202 Accepted`:

- header `Location: /api/v1/jobs/{job_id}`
- corpo `JobResposta` com `status: "queued"`, `etapa_atual: null`, `etapas_concluidas: []`, `progresso_percentual: 0`.

O job é criado antes de qualquer chamada ao LLM; a requisição não bloqueia no pipeline.

Erros: `422 VALIDACAO` (com `campos`), `413 LIMITE_EXCEDIDO`, `400 DOCUMENTO_ILEGIVEL`.

### 6.3 `POST /adaptacoes/upload`

`multipart/form-data` com `arquivo` e os cinco campos de parametrização. Enviar `documento_conteudo` é erro `422 VALIDACAO` com `campos.documento_conteudo = "não permitido quando há arquivo"`.

Resposta `202` igual à anterior. Erros adicionais: `415 ARQUIVO_INVALIDO`, `413 LIMITE_EXCEDIDO`, `400 DOCUMENTO_ILEGIVEL` (PDF sem camada de texto).

### 6.4 `GET /jobs/{job_id}`

```json
{
  "job_id": "01J9Q3ZK8V4T2R6M0C5B7N1XPD",
  "status": "running",
  "etapa_atual": "embeddings",
  "etapas_concluidas": ["extraindo", "chunking"],
  "progresso_percentual": 45,
  "mensagem": "Gerando 128 embeddings do documento",
  "iniciado_em": "2026-10-21T14:02:11Z",
  "atualizado_em": "2026-10-21T14:02:38Z"
}
```

Em `succeeded`, inclui `adaptacao_id` e `resultado` completo. Em `failed`, inclui `erro` no formato de `ApiProblema['erro']`. Em `cancelled`, não inclui nem resultado nem erro.

Erro: `404 JOB_NAO_ENCONTRADO`.

### 6.5 `DELETE /jobs/{job_id}`

Cancela e devolve `200` com o `JobResposta` em `cancelled`. `409 JOB_FINALIZADO` se o job já estiver em `succeeded`, `failed` ou `cancelled`. `404 JOB_NAO_ENCONTRADO` se o id não existir.

### 6.6 `GET /adaptacoes`

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `formato` | enum | — | `FormatoSaida` |
| `perfil` | enum | — | `PerfilDestinatario` |
| `q` | string | — | 1..100 caracteres; busca em título e conceitos-chave |
| `ordenar` | enum | `criado_em:desc` | `criado_em:desc`, `criado_em:asc`, `ancoragem:desc` |

Resposta `200 PaginaAdaptacoes`. Filtro sem resultado devolve `itens: []`, `total: 0`, `total_paginas: 0` — nunca `404`. Parâmetro fora da faixa (página negativa, `tamanho_pagina` > 50, `ordenar` desconhecido) devolve `422 VALIDACAO` com `campos`.

### 6.7 `GET /adaptacoes/{id}`

`200 AdaptacaoPacote`. `404 ADAPTACAO_NAO_ENCONTRADA`.

### 6.8 `GET /adaptacoes/{id}/download`

`200` com `Content-Type: application/json; charset=utf-8` e `Content-Disposition: attachment; filename="<nome>.json"`. Corpo é o `AdaptacaoPacote` serializado.

### 6.9 `GET /adaptacoes/{id}/exportacao`

Query obrigatória `formato` = `md` | `pdf` | `csv`.

| `formato` | Content-Type | Compatível com |
|---|---|---|
| `md` | `text/markdown; charset=utf-8` | Todos os formatos |
| `pdf` | `application/pdf` | Todos os formatos |
| `csv` | `text/csv; charset=utf-8` | Somente `Flashcards` |

CSV no formato Anki: separador `;`, aspas duplas como escape, quebras de linha preservadas dentro de campos citados. A linha de cabeçalho `frente;verso;dica` é sempre incluída.

Erros: `400 FORMATO_DESCONHECIDO`, `409 FORMATO_INCOMPATIVEL` (CSV para pacote que não é Flashcards), `404 ADAPTACAO_NAO_ENCONTRADA`.

Nome do arquivo em todas as saídas: `novamente-<slug-titulo>-<perfil>-<formato>-<8 primeiros do id>.<ext>`, com slug em minúsculas, sem acento, hífen simples. O mesmo padrão é usado em `armazenamento_oci.objeto_id`, para que a UI mostre exatamente o objeto que está no bucket.

### 6.10 `GET /oci/status`

Resposta `200 OciStatus`. O backend consulta o Object Storage e faz cache de 30 segundos. `configurado: false` **não** é erro HTTP: significa que faltam credenciais e a UI mostra estado neutro. `503 OCI_INDISPONIVEL` apenas quando há credenciais mas a API da OCI falha de forma persistente.

### 6.11 `GET /health`

Resposta sempre `200`, com `status: "ok" | "degraded"`. O frontend não trata `503` de health; trata o campo `status`. Único endpoint chamado sem ação do usuário (a cada 60 s).

### 6.12 Erros

| HTTP | `codigo` | Quando |
|---|---|---|
| 400 | `DOCUMENTO_ILEGIVEL` | Sem conteúdo extraível |
| 400 | `FORMATO_DESCONHECIDO` | `formato` de exportação inválido |
| 404 | `ADAPTACAO_NAO_ENCONTRADA` | Id inexistente |
| 404 | `JOB_NAO_ENCONTRADO` | Id inválido, expirado ou backend reiniciado |
| 409 | `FORMATO_INCOMPATIVEL` | CSV para pacote que não é Flashcards |
| 409 | `JOB_FINALIZADO` | Cancelar job já terminado |
| 413 | `LIMITE_EXCEDIDO` | > 10 MiB ou > 50.000 caracteres |
| 415 | `ARQUIVO_INVALIDO` | Extensão/MIME fora da lista |
| 422 | `VALIDACAO` | Schema inválido, com `campos` |
| 500 | `INTERNO` | Com `request_id` |
| 503 | `OCI_INDISPONIVEL` | Credenciais presentes, OCI falhando (somente em `/oci/status`) |

`lib/formatadores.ts` nunca exibe `codigo`; exibe `erro.mensagem`. `codigo` controla apenas comportamento (ex.: `campos` volta para o formulário).

---

## 7. Telas e fluxos

Dados sempre client-side via TanStack Query. Shells são Server Components; nada de `fetch` de dados em Server Component.

### 7.1 `/` — Gerar

Duas colunas em desktop: formulário fixo de 380 px à esquerda, área de trabalho à direita. Abaixo de `lg`, empilha e o formulário vira painel colapsável com resumo das escolhas.

**`IngestionForm`**

- Tabs "Colar texto" / "Enviar arquivo". Trocar de aba preserva título, perfil, formato, nicho e nível; descarta o conteúdo da aba anterior.
- Contador do textarea no formato `12.480 / 50.000`, mudando de cor nos últimos 10%.
- Dropzone de 160 px, estados `idle`, `dragging`, `selecionado` (nome, tamanho formatado, remover) e `invalido` (motivo). `input[type=file]` real dentro de `<label>`, operável por teclado.
- Perfil e formato como cards de rádio; nicho como select nativo estilizado; nível como segmented control.
- Validação: zod no `onBlur` e no submit. `aria-invalid`, `aria-describedby` e mensagem por campo. Erros `422` com `campos` são mapeados de volta para os campos correspondentes.
- Botão primário "Gerar material"; durante o job vira "Cancelar geração" (chama `DELETE`).
- Erro `413`/`415` posicionado no campo de arquivo, com o motivo do servidor.

**`JobProgress`**

- Seis etapas com estado pendente, atual, concluída e falha; rótulos da tabela de faixas.
- Barra derivada de `progresso_percentual`, sempre monotônica no cliente (`Math.max(anterior, novo)`).
- `aria-live="polite"` anunciando apenas troca de etapa, não cada poll.
- Skeleton do resultado com altura reservada desde o primeiro frame.
- Falha: `erro.mensagem` + `request_id` em texto secundário + "Tentar novamente" reenviando o mesmo payload.
- Timeout local de 5 minutos produz a mesma UI de falha, com mensagem própria.
- `404 JOB_NAO_ENCONTRADO` durante o polling é tratado como falha recuperável ("geração perdida, tente novamente").

**Cenários de demonstração** — faixa de três chips sempre visível, acima do formulário, que preenche e envia: `Iniciante + Flashcards`, `Desenvolvedor + Quiz`, `Gestor + Resumo Executivo`. Todos usam o documento-base de VCN/OCI.

Ao receber `succeeded`, o app navega para `/resultado/{adaptacao_id}`.

### 7.2 `/resultado/[id]`

Cabeçalho: título adaptado, badges (perfil, formato, nicho, nível), tempo estimado, e ações "Exportar" (menu MD/PDF/CSV; CSV desabilitado com tooltip quando não é Flashcards), "Baixar JSON" e "Nova geração".

Corpo: conteúdo principal à esquerda, `OCIPanel` à direita; empilhado abaixo de `lg`.

Estados: carregando (skeleton com o layout final), `404` (mensagem + link para o histórico), erro de rede (`ErrorState` com retry), pacote com `status_upload: "falha"` (aviso âmbar persistente). O download do JSON permanece habilitado nesse caso; a exportação também, pois ambas as rotas leem o pacote do backend.

**`FlashcardDeck`**

- Um cartão por vez, contador `3 / 8`, setas ←/→, botão "Virar" e `Enter`/`Espaço` no cartão focado.
- Flip 3D de 180° com `preserve-3d` e `backface-visibility: hidden` (Framer Motion).
- `prefers-reduced-motion`: troca instantânea de face, sem animação.
- Frente e verso com área reservada; cartão não muda de altura ao virar.
- Dica didática aparece abaixo do cartão quando existir, sem exigir o verso.

**`InteractiveQuiz`**

- Uma pergunta por vez, opções em `radiogroup` com `<fieldset>`/`<legend>`.
- "Confirmar" habilitado apenas com seleção; feedback imediato correto/incorreto com a explicação; depois "Próxima".
- Última pergunta leva ao placar `7 / 10` e bloco "Revisar erradas" com pergunta, resposta dada e resposta correta.
- Sem persistência de tentativas.

**`MarkdownView`**

- `react-markdown` + `remark-gfm` + `rehype-sanitize`, importado com `next/dynamic`.
- Estilos via `@tailwindcss/typography`, com código inline e blocos em fonte mono.
- Skeleton de altura reservada durante o carregamento do chunk.

**`OCIPanel`**

- Gauge de ancoragem: `0,98` → `98%`. Faixas: ≥ 0,90 verde; 0,70–0,89 âmbar; < 0,70 vermelho.
- Clareza pedagógica como badge, observações como texto secundário.
- Bucket, `objeto_id` (truncado com `title`) e badge de `status_upload`.
- `status_upload: "falha"`: aviso âmbar "Material exibido, mas não persistido no OCI". Sem botão de reenvio (fora de escopo).
- OCI não configurado (`configurado: false`): estado neutro, não erro.

### 7.3 `/historico`

Grade de cards, 12 por página: título do documento, badges, data relativa, score e status do upload.

- Busca com debounce de 300 ms, filtros de formato e perfil.
- Filtros refletidos na URL (`?formato=Quiz&perfil=Gestor&pagina=2`), recarregáveis e compartilháveis.
- Paginação numerada com primeira/última.
- Estados: skeleton em grade, vazio com CTA "Gerar o primeiro material", erro com retry.

### 7.4 Transversal

- `AppShell`: header fixo com logo, nav (Gerar, Histórico), `SkinSwitcher`; `skip-link` para o conteúdo; container de 1280 px.
- `HealthBanner`: faixa discreta quando `/health` responde `degraded`.
- Toda view define carregando, vazio, erro e degradado. Nenhuma tela em branco.
- Textos de UI exclusivamente em `lib/mensagens.ts`, pt-BR.
- Mobile-first; alvos de toque ≥ 44 px; foco visível em ambas as skins.

---

## 8. Temas e skins

Duas skins dark, trocadas por atributo `data-skin` no `<html>`:

| Skin | Acento | Caráter |
|---|---|---|
| `violeta` (default) | `#8b5cf6` | IA/cloud, superfícies grafite-azuladas |
| `ciano` | `#22d3ee` | Terminal/cloud, contraste mais frio |

Tokens em `themes/tokens.css` (nomes fixos, valores por skin):

```
--bg, --surface, --surface-elevated, --border, --border-strong,
--fg, --fg-muted, --accent, --accent-fg, --accent-muted,
--success, --warning, --danger, --ring
```

Regras:

- `registry.ts` exporta `SKINS: Record<SkinId, { nome: string; classe: string }>`; adicionar skin é adicionar tokens + entrada, sem tocar em componente (OCP).
- Persistência em `localStorage` (`novamente.skin`) via Zustand `persist`.
- Script inline no `<head>` aplica `data-skin` antes do primeiro paint — sem flash de skin errada.
- Ambas as skins obrigam contraste AA (4,5:1 para texto normal) e foco visível com `--ring`.
- Não há skin clara nesta versão. A camada de tokens está pronta para recebê-la.

---

## 9. Performance

| Meta | Alvo | Como verificar |
|---|---|---|
| CLS | 0 | Lighthouse local ou PerformanceObserver em Chromium |
| LCP local | < 2,5 s | Lighthouse local |
| JS inicial por rota (gzip) | < 250 kB | Medição no browser; Next 16 não reporta First Load JS |

A meta original de 180 kB foi revista depois da medição: `/` ficou em 230,8 kB, dos quais 128,3 kB são a base do framework (Next 16 + React 19) e ~65 kB são dependências exigidas ou escolhidas na stack (zod, TanStack Query, react-hook-form, tailwind-merge). Como a base do framework sozinha já consome 128 kB, 180 kB não é atingível sem trocar a stack aprovada. O número medido e a decomposição ficam registrados no `frontend/README.md`.
| Framer Motion e markdown | fora do bundle inicial | Análise do relatório de build |

Regras:

- `FlashcardDeck`, `InteractiveQuiz` e `MarkdownView` via `next/dynamic`, com skeleton de altura equivalente.
- Fontes com `next/font` (Inter + JetBrains Mono), `display: swap`.
- Polling do job com `refetchIntervalInBackground: false`.
- `React.memo` em `FlashcardCard`; `useMemo` apenas em cálculos de score, faixa e etapas; `useCallback` apenas em handlers passados a filhos memoizados. Nenhuma memoização sem justificativa medida.
- Pacote imutável nunca é revalidado (`staleTime: Infinity`).

---

## 10. Acessibilidade

- axe-core executado nas três rotas (E2E) + revisão manual. Violação de impacto crítico bloqueia a conclusão.
- Teclado: formulário completo, deck (setas/Enter/Espaço), quiz (`radiogroup` + botões), menu de exportação, paginação, troca de skin.
- `aria-live="polite"` apenas em mudança de etapa do job e em erro de submissão; nunca em cada poll.
- `prefers-reduced-motion` remove o flip e reduz transições.
- Contraste AA nas duas skins; foco visível com `--ring` de 2 px e offset.
- Campos sempre com `<label>` associado; erros anunciados via `aria-describedby` e resumo de erros no topo do formulário.
- Áreas clicáveis ≥ 44×44 px; nenhum controle só por hover.

---

## 11. Testes e mocks

### 11.1 MSW como contrato executável

- Handlers replicam todas as dez rotas, incluindo os erros `400`, `404`, `409`, `413`, `415`, `422` e `500`.
- Fixtures obrigatoriamente validadas por `AdaptacaoPacoteSchema.parse()` em `fixtures.test.ts`. Fixture desalinhada falha o build.
- Simulação de job em memória: handler de criação registra o job, que avança as seis etapas ao longo de ~6 s; `GET /jobs/{id}` devolve o estado corrente; `DELETE` marca cancelado.
- Cenários de erro são injetados com `server.use()` nos testes e stories. Nenhum código de produção verifica ambiente para forçar falha.
- `NEXT_PUBLIC_API_MOCK=1` inicia o worker no browser; ausente, o app chama o FastAPI.

### 11.2 Fixtures

| Arquivo | Formato | Perfil | Nível | Conteúdo |
|---|---|---|---|---|
| `flashcards-vcn-iniciante.json` | Flashcards | Iniciante | Didatico | 8 cartões de VCN |
| `quiz-vcn-desenvolvedor.json` | Quiz | Desenvolvedor | Tecnico | 6 questões de VCN |
| `tutorial-vcn-lider.json` | Tutorial | LiderTecnico | Tecnico | Markdown com seções e exemplos |
| `resumo-vcn-gestor.json` | ResumoExecutivo | Gestor | Executivo | Markdown TL;DR com conceitos-chave |

Todos com `armazenamento_oci.status_upload: "concluido"`, `bucket: "novamente-conteudos-educativos"` e scores entre 0,94 e 0,99. O estado de upload falho é coberto por uma variação derivada da fixture de Flashcards dentro dos testes, sem virar uma quinta fixture de demonstração.

### 11.3 Camadas de teste

| Camada | Ferramenta | Cobertura mínima |
|---|---|---|
| Schemas e formatadores | Vitest | Casos de borda de limites, enums e união discriminada |
| Hooks e serviços | Vitest + MSW (`setupServer`) | ≥ 80% de linhas em `features/**` e `services/**` |
| Componentes | RTL + MSW | Formulário, deck, quiz, OCI, histórico |
| Ponto a ponta | Playwright + axe | 3 cenários do edital + 3 rotas no axe |
| Catálogo visual | Storybook + addon MSW | Sucesso, carregando, vazio e erro por visualizador |

E2E obrigatórios:

1. Texto colado → Flashcards → resultado → exportar Markdown.
2. Upload de PDF → Quiz → responder tudo → placar correto.
3. Histórico → reabrir pacote → baixar JSON → CSV desabilitado para não-Flashcards.

---

## 12. Ordem de entrega

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 0 | Scaffold Next, Tailwind, shadcn, fontes, tokens, duas skins, `AppShell`, MSW no ar | App sobe, troca de skin persiste, `/health` mockado responde |
| 1 | `schemas.ts`, `novamente.ts`, `NovaMenteApi`, `httpApiClient`, handlers, fixtures | `fixtures.test.ts` e testes de schema verdes |
| 2 | `FlashcardCard`, `FlashcardDeck`, `InteractiveQuiz`, `MarkdownView`, `OCIPanel`, `ContentRenderer` | Stories dos 4 formatos navegáveis e testadas |
| 3 | `IngestionForm`, hooks de criação, `useAdaptationJob`, `JobProgress`, cancelamento | Geração completa contra mock, com etapas reais |
| 4 | `/`, `/resultado/[id]`, `/historico`, exportação, download, `oci/status` | 3 cenários clicáveis ponta a ponta |
| 5 | E2E, axe, revisão de performance, README do frontend | DoD abaixo |

---

## 13. Definição de pronto

- `npm run build`, `npm run lint` e `tsc --noEmit` sem erro.
- Vitest verde, com o limite de cobertura de 11.3 aplicado no CI.
- 3 E2E verdes; axe sem violação crítica nas 3 rotas.
- As duas skins operáveis por teclado, com contraste AA.
- Nenhuma tela em branco em estado de carregando, vazio, erro, degradado ou OCI não configurado.
- Handlers do MSW, fixtures e seções 5 e 6 desta spec descrevendo exatamente o mesmo contrato.
- README do frontend com como rodar em modo mock e como apontar para o backend real.

---

## 14. Divergências em relação às fontes

| Ponto | Briefing / PDF | Esta spec | Motivo |
|---|---|---|---|
| Formatos | Briefing: 4. PDF: 5 (inclui Roteiro de Aula) | 4 | Roteiro exigiria renderizador e contrato próprios; fora do MVP |
| `nivel_detalhe` | PDF inclui; briefing omite | Incluído com 3 valores | Requisito do edital presente no exemplo |
| `arquivo` + `documento_conteudo` no mesmo request | Briefing | Rotas separadas | Ambiguidade de precedência; duas origens, dois contratos |
| `itens: FlashcardItem[] \| QuizItem[] \| string` | Briefing | `ConteudoAdaptado` discriminado por `tipo` | Segurança de tipo e validação zod |
| `apiClient.ts` e `api.ts` (mock) | Briefing, FASE 1 | `NovaMenteApi` + `httpApiClient` + MSW | Um caminho de código; mock é de rede |
| `status: 'sucesso' \| 'erro'` | Briefing | `status: 'sucesso'` literal | Erro é HTTP + `ApiProblema` |
| Interface Streamlit/Gradio | PDF | Next.js (briefing) | O briefing escolhe a stack; PDF aceita API REST |
| Perfis | PDF com rótulos duais | Enum curto + rótulo em `constants` | Contrato estável, texto fiel ao PDF |
| Deploy em OCI Compute | PDF, diferencial | Fora de escopo | Sem hospedagem definida nesta fase |
| Exportação MD/PDF/CSV | PDF, diferencial | Dentro | Escolhido no design |
| Auth | Não citado | Ausente | Escopo demo |

---

## 15. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Backend divergir do contrato | Alto | MSW é o contrato executável; fixtures validadas por zod; backend implementa esta spec |
| Job longo estourar tempo na camada free | Médio | Cancelamento, timeout de 5 min, limites de entrada |
| Custo de embeddings acima do previsto | Médio | 10 MB / 50.000 caracteres por job |
| PDF didático e CSV-Anki no backend | Médio | Uma rota com `formato` e regra de compatibilidade explícita |
| Flip 3D inacessível | Baixo | Fallback de troca instantânea com motion reduzido, testado |
| Fixtures envelhecerem | Médio | Falha de build no teste de contrato |
| Gauge de score comunicar só por cor | Baixo | Percentual textual sempre visível ao lado |
