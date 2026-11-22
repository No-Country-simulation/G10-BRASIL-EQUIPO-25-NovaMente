<div align="center">

<!-- Badges centralizadas e limpas -->
<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" height="28">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" height="28">
  <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js" height="28">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" height="28">
  <img src="https://img.shields.io/badge/Tailwind%20CSS-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind CSS" height="28">
  <img src="https://img.shields.io/badge/Google%20Gemini-8E75B2?style=flat-square&logo=google&logoColor=white" alt="Google Gemini" height="28">
  <img src="https://img.shields.io/badge/OCI-F80000?style=flat-square&logo=oracle&logoColor=white" alt="OCI Object Storage" height="28">
</p>

# NovaMente


> **NovaMente** é um sistema inteligente de adaptação e geração de conteúdo educacional desenvolvido para o hackathon da ONE (Oracle Next education) em parceria com a No Country e Alura. O projeto tem como propósito automatizar e personalizar a criação de materiais didáticos a partir de documentos técnicos, aplicando técnicas de RAG (*Retrieval-Augmented Generation*) e inteligência artificial para atender a diferentes perfis de aprendizado e necessidades setoriais.

</div>

---

## Visão do Produto

- **Para** EdTechs, instituições de ensino, empresas de tecnologia e equipes de engenharia que precisam capacitar públicos diversos desde iniciantes em transição de carreira até lideranças técnicas e arquitetos.
- **Que enfrentam** processos morosos de semanas para a criação e adaptação manual de materiais didáticos densos e em constante evolução.
- **O NovaMente** é um sistema inteligente de adaptação e geração de conteúdo educacional baseado em IA Generativa, Arquitetura RAG e Orquestração de Agentes.
- **Que** ingere documentações técnicas, manuais de software e bases de conhecimento para transformá-los automaticamente em conteúdos educacionais personalizados e estruturados de acordo com o perfil do destinatário, a indústria de aplicação e o formato pedagógico.
- **Diferente de** processos manuais fragmentados com consultores especializados e geradores de texto genéricos sem ancoragem técnica.
- **Nosso produto** oferece automação completa via RAG (Retrieval-Augmented Generation) com fidelidade às fontes originais, permitindo parametrizar perfis (iniciante, pleno, arquiteto), formatos de saída (flashcards, quizzes, tutoriais) e persistência obrigatória em nuvem na Oracle Cloud (OCI Object Storage).

---

## Principais Funcionalidades
### Funcionalidades Planejadas / Previstas para o MVP:
- Formulário de ingestão multiorigem (upload de arquivos `.pdf`, `.md`, `.txt` ou inserção de texto copiado).
- Landing pública com apresentação do produto, formatos e tour guiado pelas telas reais.
- Separação entre **área da empresa** (`/empresa/*`) e **área do aluno** (`/aluno/*`).
- Catálogo durável de materiais em SQLite, com rascunho, publicação, edição e exclusão.
- CRUD de alunos e vínculos aluno ↔ material, com identificação leve do aluno (sem senha).
- Parametrização por perfil de destinatário, formato de saída, nicho/setor e nível de detalhe.
- Execução assíncrona com monitoramento de etapas e progresso via polling de jobs.
- Renderizadores visuais dedicados para Flashcards, Quiz Interativo e Documentos Markdown.
- Painel de metadados do OCI e indicadores de qualidade (score de ancoragem e clareza).
- Histórico global de adaptações com paginação e filtros por parâmetros.
- Exportação e download de pacotes em formatos JSON, Markdown, PDF e CSV.
- Health check da API e status do bucket Object Storage.
- Temas alternáveis persistidos via Zustand e sistema de skins.
- Massa de demonstração contendo *fixtures* e cenários de atalho pré-configurados.

---

## Processo de Desenvolvimento
O desenvolvimento do projeto segue uma metodologia ágil adaptada para entregas de alto impacto em hackathons:
- **Organização do Trabalho:** Sprints estruturadas (S0 a S5) com foco em entregas incrementais.
- **Fluxo de Versionamento e Git Strategy:** Utilização de branches descritivas (`feat/...`, `fix/...`, `docs/...`), abertura de *Pull Requests* direcionadas à branch `develop`, revisão e aprovação por pares antes da integração final na branch `main`.
* **Quadro de Tarefas (Kanban):** [NovaMente](https://github.com/orgs/No-Country-simulation/projects/568)
* **Documentação Completa da Proposta:** [docs/](docs/) ou [Wiki](https://github.com/No-Country-simulation/G10-BRASIL-EQUIPO-25-NovaMente/wiki)
- **Boas Práticas:** Commits atômicos, testes locais com dados simulados/reais, atualização contínua da documentação técnica e acompanhamento das tarefas através do quadro Kanban.

---

## Equipe 25 Hackathon ONE G10 Brasil
| Nome do Integrante | Papel no Projeto / Scrum |
| :--- | :--- |
| **Alex Grellet** | Vibe Coder / Developer |
| **Luan Carvalho** | Vibe Coder / Developer |
| **Renato Campos** | Tech Lead / Vibe Coder |

---

## Stack Tecnológica
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn, SQLAlchemy 2 + SQLite (catálogo de materiais, alunos e vínculos), LangChain, ChromaDB (Vector Store), Google Gemini API (LLM).
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Hook Form + Zod, Framer Motion, React Markdown.
- **Armazenamento e Nuvem:** OCI Object Storage (Oracle Cloud Infrastructure - camada *Always Free*).
- **Testes e Qualidade:** Pytest, Vitest, Testing Library, Playwright e MSW (*Mock Service Worker*) para contratos de rede.

---

## Estrutura do Projeto
O repositório está organizado como um monorepo contendo os módulos de backend e frontend, além de diretórios de documentação:

```text
.
└── no-country-simulation-g10-brasil-equipo-25-novamente/
    ├── README.md                                  # Visão geral, arquitetura, setup e uso do projeto
    ├── backend/                                   # Serviço API FastAPI, pipeline RAG e workers
    │   ├── README.md                              # Documentação específica do backend
    │   ├── requirements-rag.txt                   # Dependências específicas do pipeline RAG
    │   ├── requirements.txt                       # Dependências principais do backend Python
    │   ├── .env.example                           # Modelo de variáveis de ambiente do backend
    │   ├── app/                                   # Código-fonte da aplicação backend
    │   │   ├── __init__.py                        # Inicializador do pacote app
    │   │   ├── main.py                            # Entrada da API FastAPI e configuração de rotas/middlewares
    │   │   ├── api/                               # Camada HTTP / endpoints da API
    │   │   │   ├── __init__.py                    # Inicializador do pacote api
    │   │   │   └── v1/                            # Versão 1 da API REST
    │   │   │       ├── __init__.py                # Inicializador do pacote v1
    │   │   │       └── routers/                   # Agrupamento de rotas por domínio
    │   │   │           ├── __init__.py            # Inicializador do pacote routers
    │   │   │           ├── adaptacoes.py          # Endpoints de geração, consulta e exportação de adaptações
    │   │   │           ├── health.py              # Endpoint de health check da API
    │   │   │           ├── jobs.py                # Endpoints de acompanhamento de jobs assíncronos
    │   │   │           └── oci.py                 # Endpoints de status/integração com OCI Object Storage
    │   │   ├── core/                              # Configurações centrais e tratamento de exceções
    │   │   │   ├── config.py                      # Leitura e validação de configurações/variáveis de ambiente
    │   │   │   └── erros.py                       # Exceções de domínio e respostas padronizadas de erro
    │   │   ├── models/                            # Schemas e modelos de dados da aplicação
    │   │   │   └── __init__.py                    # Definições/exports de modelos de dados
    │   │   ├── rag/                               # Pipeline de recuperação aumentada por geração (RAG)
    │   │   │   ├── README.md                      # Documentação técnica do módulo RAG
    │   │   │   ├── __init__.py                    # Inicializador do módulo rag
    │   │   │   ├── armazenamento.py               # Persistência/gerenciamento de índices e artefatos RAG
    │   │   │   ├── chunking.py                    # Divisão e preparo de textos/documentos em chunks
    │   │   │   ├── config.py                      # Parâmetros específicos de configuração do RAG
    │   │   │   ├── embeddings.py                  # Geração de embeddings vetoriais
    │   │   │   ├── modelos.py                     # Estruturas de dados e configurações de modelos LLM/RAG
    │   │   │   └── servico.py                     # Orquestração principal da consulta e geração via RAG
    │   │   ├── services/                          # Regras de negócio e integrações externas
    │   │   │   ├── __init__.py                    # Inicializador do pacote services
    │   │   │   ├── extracao.py                    # Extração de texto de arquivos e fontes de entrada
    │   │   │   ├── oci.py                         # Integração com OCI Object Storage
    │   │   │   ├── pipeline.py                    # Fluxo completo de processamento e adaptação de conteúdo
    │   │   │   └── repositorio.py                 # Acesso a dados e persistência de registros
    │   │   └── workers/                           # Processamento em segundo plano / assíncrono
    │   │       ├── __init__.py                    # Inicializador do pacote workers
    │   │       └── job_worker.py                  # Worker responsável por executar jobs de geração
    │   ├── data/                                  # Dados de apoio e exemplos
    │   │   └── exemplos/                          # Materiais base de demonstração
    │   │       ├── git_versionamento.md           # Exemplo de conteúdo técnico sobre Git
    │   │       ├── http_apis_rest.md              # Exemplo de conteúdo técnico sobre APIs REST
    │   │       └── sql_consultas.md               # Exemplo de conteúdo técnico sobre SQL
    │   ├── scripts/                               # Scripts utilitários de apoio e validação
    │   │   ├── demo_rag.py                      # Script para testar/demonstrar o pipeline RAG
    │   │   └── verificar_ambiente.py              # Verificação de dependências e ambiente do backend
    │   └── tests/                                 # Suíte de testes automatizados do backend (pytest)
    │       ├── conftest.py                        # Fixtures e configurações globais de testes
    │       ├── api/                               # Testes de endpoints e contratos da API
    │       │   ├── __init__.py                    # Inicializador dos testes de API
    │       │   └── test_rotas.py                  # Testes das rotas REST da aplicação
    │       └── rag/                               # Testes unitários e de integração do módulo RAG
    │           ├── conftest.py                    # Fixtures específicas para testes de RAG
    │           ├── falsos.py                      # Dublês/mocks de componentes para testes isolados
    │           ├── test_armazenamento.py          # Testes de armazenamento/índice RAG
    │           ├── test_chunking.py               # Testes da divisão de documentos em chunks
    │           ├── test_embeddings.py             # Testes da camada de embeddings
    │           ├── test_exemplos.py               # Testes usando os documentos de exemplo
    │           └── test_servico.py                # Testes do serviço de geração RAG
    ├── docs/                                      # Documentação técnica, specs e proposta do projeto
    │   ├── Especificação do backend fastapi.md    # Especificação funcional/técnica da API FastAPI
    │   ├── Especificações frontend-design.md      # Diretrizes e especificações de design do frontend
    │   ├── master_prompt_superpowers_novamente_frontend.md # Prompt mestre de referência do frontend
    │   ├── proposta.md                            # Documento de proposta do projeto
    │   └── superpowers/                           # Especificações detalhadas de design e arquitetura
    │       └── specs/                             # Documentos de especificação versionados
    │           └── 2026-10-21-novamente-frontend-design.md # Especificação de design do frontend (21/10/2026)
    ├── frontend/                                  # Aplicação web Next.js, testes e Storybook
    │   ├── README.md                              # Documentação específica do frontend
    │   ├── AGENTS.md                              # Instruções/convenções para agentes de código no frontend
    │   ├── components.json                        # Configuração de componentes UI (ex.: shadcn/ui)
    │   ├── eslint.config.mjs                      # Configuração do ESLint (linting e qualidade de código)
    │   ├── next.config.ts                         # Configuração do Next.js
    │   ├── package.json                           # Dependências e scripts NPM do frontend
    │   ├── playwright.config.ts                   # Configuração dos testes end-to-end com Playwright
    │   ├── tsconfig.json                          # Configuração do TypeScript
    │   ├── vitest.config.mts                      # Configuração do Vitest (testes unitários/componentes)
    │   ├── vitest.shims.d.ts                      # Tipagens auxiliares para o ambiente de testes Vitest
    │   ├── .env.example                           # Modelo de variáveis de ambiente do frontend
    │   ├── .npmrc                                 # Configurações do NPM
    │   ├── e2e/                                   # Testes end-to-end automatizados (Playwright)
    │   │   ├── 1-gerar-flashcards.spec.ts         # Fluxo E2E de geração de flashcards
    │   │   ├── 2-upload-quiz.spec.ts              # Fluxo E2E de upload e geração de quiz
    │   │   ├── 3-historico-exportacao.spec.ts     # Fluxo E2E de histórico e exportação de materiais
    │   │   └── 4-acessibilidade.spec.ts           # Verificações automatizadas de acessibilidade
    │   ├── public/                                # Arquivos estáticos públicos
    │   │   └── mockServiceWorker.js               # Service worker do MSW para interceptar requisições em mock
    │   ├── src/                                   # Código-fonte da aplicação frontend
    │   │   ├── app/                               # Rotas e páginas do Next.js (App Router)
    │   │   │   ├── globals.css                    # Estilos globais da aplicação
    │   │   │   ├── layout.tsx                     # Layout raiz compartilhado entre as páginas
    │   │   │   ├── page.tsx                       # Página inicial / geração de conteúdo
    │   │   │   ├── providers.tsx                  # Providers globais (QueryClient, tema, mocks, etc.)
    │   │   │   ├── historico/                     # Rota de histórico de adaptações
    │   │   │   │   └── page.tsx                   # Tela de listagem e filtros do histórico
    │   │   │   └── resultado/                     # Rota dinâmica de visualização do material gerado
    │   │   │       └── [id]/                      # Parâmetro dinâmico pelo ID da adaptação
    │   │   │           └── page.tsx               # Tela de detalhe, visualização, OCI e exportação
    │   │   ├── components/                        # Componentes visuais reutilizáveis e de telas
    │   │   │   ├── forms/                         # Formulários de ingestão e parametrização
    │   │   │   │   ├── Cenarios.test.tsx            # Testes do componente de cenários prontos
    │   │   │   │   ├── Cenarios.tsx               # Atalhos/cenários pré-configurados de demonstração
    │   │   │   │   ├── IngestionForm.test.tsx     # Testes do formulário principal de ingestão
    │   │   │   │   ├── IngestionForm.tsx          # Formulário de envio de documento e parâmetros
    │   │   │   │   └── campos/                    # Subcampos especializados do formulário
    │   │   │   │       ├── FonteDocumento.tsx     # Campo de seleção de arquivo ou texto de origem
    │   │   │   │       └── ParametrosFields.tsx   # Campos de perfil, formato, nicho e nível de detalhe
    │   │   │   ├── layout/                        # Estrutura de layout, navegação e status
    │   │   │   │   ├── AppShell.tsx               # Estrutura base de layout das páginas
    │   │   │   │   ├── Header.tsx                 # Cabeçalho e navegação superior
    │   │   │   │   ├── HealthBanner.test.tsx      # Testes do banner de status da API
    │   │   │   │   ├── HealthBanner.tsx           # Indicador visual de saúde/disponibilidade da API
    │   │   │   │   ├── SkinSwitcher.test.tsx      # Testes do seletor de tema/skin
    │   │   │   │   └── SkinSwitcher.tsx           # Controle para alternar tema/skin visual
    │   │   │   ├── ui/                            # Componentes base de interface (design system)
    │   │   │   │   ├── badge.tsx                  # Componente visual de badge/etiqueta
    │   │   │   │   ├── button.test.tsx            # Testes do componente de botão
    │   │   │   │   ├── button.tsx                 # Componente de botão reutilizável
    │   │   │   │   ├── card.tsx                   # Componente de cartão/container visual
    │   │   │   │   ├── dropdown-menu.tsx          # Menu suspenso acessível
    │   │   │   │   ├── Dropzone.test.tsx          # Testes da área de arrastar e soltar arquivos
    │   │   │   │   ├── Dropzone.tsx               # Componente de upload via drag-and-drop
    │   │   │   │   ├── progress.tsx               # Barra de progresso visual
    │   │   │   │   ├── select.tsx                 # Campo de seleção suspensa (select)
    │   │   │   │   ├── separator.tsx              # Divisor visual horizontal/vertical
    │   │   │   │   ├── skeleton.tsx               # Placeholder de carregamento (skeleton loading)
    │   │   │   │   ├── tabs.tsx                   # Componente de abas (tabs)
    │   │   │   │   └── tooltip.tsx                # Dica flutuante ao passar/focar (tooltip)
    │   │   │   └── views/                         # Visualizações completas e renderizadores de conteúdo
    │   │   │       ├── ContentRenderer.test.tsx   # Testes do seletor/renderizador de formatos
    │   │   │       ├── ContentRenderer.tsx        # Renderiza o conteúdo conforme o formato escolhido
    │   │   │       ├── ExportMenu.tsx             # Menu de exportação (PDF, Markdown, JSON, CSV etc.)
    │   │   │       ├── FlashcardCard.tsx          # Cartão individual de flashcard (frente/verso)
    │   │   │       ├── FlashcardDeck.reduzido.test.tsx # Teste de deck de flashcards em cenário reduzido
    │   │   │       ├── FlashcardDeck.stories.tsx  # Stories do Storybook para FlashcardDeck
    │   │   │       ├── FlashcardDeck.test.tsx     # Testes unitários de FlashcardDeck
    │   │   │       ├── FlashcardDeck.tsx          # Deck interativo de flashcards
    │   │   │       ├── GerarView.test.tsx         # Testes da view de geração de material
    │   │   │       ├── GerarView.tsx            # View principal de criação e execução de jobs
    │   │   │       ├── HistoricoView.test.tsx     # Testes da view de histórico
    │   │   │       ├── HistoricoView.tsx        # View de histórico de adaptações geradas
    │   │   │       ├── InteractiveQuiz.stories.tsx # Stories do Storybook para InteractiveQuiz
    │   │   │       ├── InteractiveQuiz.test.tsx   # Testes unitários de InteractiveQuiz
    │   │   │       ├── InteractiveQuiz.tsx        # Quiz interativo com correção/feedback
    │   │   │       ├── JobProgress.test.tsx       # Testes do componente de progresso de job
    │   │   │       ├── JobProgress.tsx          # Exibe etapas e progresso do processamento assíncrono
    │   │   │       ├── MarkdownView.stories.tsx   # Stories do Storybook para MarkdownView
    │   │   │       ├── MarkdownView.tsx           # Renderizador formatado de documentos Markdown
    │   │   │       ├── OCIPanel.stories.tsx       # Stories do Storybook para OCIPanel
    │   │   │       ├── OCIPanel.test.tsx        # Testes unitários de OCIPanel
    │   │   │       ├── OCIPanel.tsx             # Painel com metadados e status do OCI Object Storage
    │   │   │       ├── ResultadoHeader.tsx        # Cabeçalho da tela de resultado com metadados/ações
    │   │   │       ├── ResultadoView.test.tsx     # Testes da view de resultado
    │   │   │       ├── ResultadoView.tsx        # View completa do material gerado e exportações
    │   │   │       └── ScoreGauge.tsx           # Indicador visual de métricas/qualidade (ex.: ancoragem)
    │   │   ├── features/                          # Hooks e lógica de domínio encapsulada por feature
    │   │   │   ├── adaptations/                   # Feature de adaptações de conteúdo
    │   │   │   │   ├── useAdaptation.ts           # Hook para buscar/gerenciar uma adaptação específica
    │   │   │   │   ├── useAdaptationForm.ts       # Hook para estado e validação do formulário
    │   │   │   │   ├── useAdaptationHistory.ts    # Hook para consulta e filtros do histórico
    │   │   │   │   ├── useCreateAdaptation.ts     # Hook de mutação para criar/iniciar adaptação
    │   │   │   │   ├── useExport.test.tsx         # Testes do hook de exportação
    │   │   │   │   └── useExport.ts               # Hook para disparar e baixar exportações
    │   │   │   ├── health/                        # Feature de monitoramento de saúde da API
    │   │   │   │   └── useHealth.ts               # Hook de consulta ao status da API
    │   │   │   ├── jobs/                          # Feature de jobs assíncronos
    │   │   │   │   ├── useAdaptationJob.test.tsx  # Testes do hook de acompanhamento de job
    │   │   │   │   └── useAdaptationJob.ts        # Hook de polling de status e progresso de job
    │   │   │   ├── oci/                           # Feature de integração/status OCI
    │   │   │   │   ├── useOciStatus.test.tsx      # Testes do hook de status do OCI
    │   │   │   │   └── useOciStatus.ts            # Hook para consultar status/metadados do bucket OCI
    │   │   │   └── theme/                         # Feature de temas e skins visuais
    │   │   │       ├── SkinProvider.tsx           # Contexto/provider de persistência e aplicação de skin
    │   │   │       └── useSkin.ts                 # Hook para ler e alterar o tema/skin ativo
    │   │   ├── lib/                               # Utilitários, constantes, formatações e mensagens
    │   │   │   ├── cn.test.ts                   # Testes do utilitário de classes CSS (`cn`)
    │   │   │   ├── cn.ts                        # Helper para combinar classes Tailwind/clsx
    │   │   │   ├── constants.ts                   # Constantes da aplicação (formatos, perfis, limites)
    │   │   │   ├── formatadores.test.ts           # Testes das funções de formatação
    │   │   │   ├── formatadores.ts                # Formatadores de datas, textos e valores
    │   │   │   ├── mensagens.ts                   # Mensagens padronizadas de interface/erro/feedback
    │   │   │   └── utils.ts                       # Funções utilitárias genéricas
    │   │   ├── mocks/                           # Simulação de API e dados fictícios (MSW / fixtures)
    │   │   │   ├── browser.ts                     # Configuração do MSW para ambiente de navegador
    │   │   │   ├── estadoJobs.ts                  # Simulação de estados de progresso de jobs
    │   │   │   ├── fixtures.test.ts               # Testes de validação das fixtures JSON
    │   │   │   ├── handlers.test.ts               # Testes dos handlers HTTP de mock
    │   │   │   ├── MockGate.tsx                   # Controle condicional para ativar/exibir modo mock
    │   │   │   ├── MockProvider.tsx               # Provider que inicializa o ambiente de mocks
    │   │   │   ├── server.ts                      # Configuração do MSW para testes (Node/Vitest)
    │   │   │   ├── fixtures/                      # Exemplos de payloads adaptados em JSON
    │   │   │   │   ├── flashcards-vcn-iniciante.json # Fixture de flashcards sobre VCN (nível iniciante)
    │   │   │   │   ├── quiz-vcn-desenvolvedor.json # Fixture de quiz sobre VCN (nível desenvolvedor)
    │   │   │   │   ├── resumo-vcn-gestor.json     # Fixture de resumo sobre VCN (nível gestor)
    │   │   │   │   └── tutorial-vcn-lider.json    # Fixture de tutorial sobre VCN (nível líder)
    │   │   │   └── handlers/                      # Handlers mockados por endpoint da API
    │   │   │       ├── adaptacoes.ts              # Mock das rotas de adaptações
    │   │   │       ├── health.ts                  # Mock da rota de health check
    │   │   │       ├── index.ts                   # Agrega e exporta todos os handlers MSW
    │   │   │       ├── jobs.ts                    # Mock das rotas de jobs assíncronos
    │   │   │       └── oci.ts                     # Mock das rotas relacionadas ao OCI
    │   │   ├── services/                          # Camada de comunicação externa e cliente HTTP
    │   │   │   └── api/                           # Cliente da API backend
    │   │   │       ├── ApiProvider.tsx            # Provider de contexto para injeção/acesso à API
    │   │   │       ├── download.test.ts           # Testes do utilitário de download de arquivos
    │   │   │       ├── download.ts                # Dis

```

## Áreas da aplicação

```text
/                     landing pública + tour
/empresa/gerar        geração de material
/empresa/historico    histórico de pacotes gerados
/empresa/resultado/:id  detalhe, OCI e exportação
/empresa/materiais    catálogo: rascunho, publicado, editar e excluir
/empresa/alunos       CRUD de alunos
/empresa/alunos/:id   detalhe do aluno + vínculos com materiais
/aluno                identificação por nome + catálogo liberado
/aluno/materiais/:id  leitura do material pelo aluno
```

Fluxo empresa × aluno:

1. A empresa gera o material em `/empresa/gerar`; ele nasce como **rascunho**.
2. Em `/empresa/materiais`, a empresa revisa, publica e pode excluir.
3. Em `/empresa/alunos/:id`, vincula materiais publicados (ou ainda em rascunho) ao aluno.
4. O aluno se identifica sem senha em `/aluno` e vê somente materiais **publicados e vinculados** ao seu `aluno_id`.
5. Acesso direto a material não liberado responde `404 MATERIAL_NAO_DISPONIVEL`, sem revelar sua existência.




## Pré-requisitos

#### Para executar o projeto localmente, certifique-se de possuir as seguintes ferramentas instaladas:

- Python 3.11 ou superior (recomendado o uso de ambiente virtual).

- Node.js (versão 20 ou superior) e gerenciador de pacotes (npm, pnpm ou yarn).

- Git para controle de versão.

- GNU Make (opcional, recomendado para os atalhos `make`; no Windows: `choco install make` ou `winget install ezwinports.make`).

- Chaves de API configuradas para acesso ao modelo de IA (Google Gemini) e opcionais credenciais da OCI Object Storage (caso deseje testar a persistência em nuvem).

## Como Executar

### Clonar o Repositório

```bash
git clone https://github.com/No-Country-simulation/G10-BRASIL-EQUIPO-25-NovaMente.git
cd G10-BRASIL-EQUIPO-25-NovaMente
```

### Atalhos com Make (recomendado)

Com o [GNU Make](https://www.gnu.org/software/make/) instalado, os comandos abaixo funcionam em Linux/macOS e Windows (PowerShell, CMD ou Git Bash), sempre a partir da raiz do repositório:

| Comando | O que faz |
|---|---|
| `make venv` | Cria `backend/.venv` e instala `backend/requirements.txt` |
| `make install-backend-dev` | Cria o venv e instala também `requirements-dev.txt` (pytest) |
| `make install` | Cria o venv com deps de dev e instala as dependências do frontend |
| `make dev-backend` | Sobe a API FastAPI em `http://localhost:8000` |
| `make dev-frontend` | Sobe o Next.js em `http://localhost:3000` |
| `make test` | Roda `pytest` e `vitest` |
| `make test-backend` | Roda somente `pytest` |
| `make test-frontend` | Roda somente `vitest` |
| `make typecheck` | Roda `tsc --noEmit` |
| `make lint` | Roda o ESLint |
| `make build` | Build de produção do Next.js |
| `make e2e` | Roda o Playwright |
| `make audit` | Roda `npm audit` no `frontend/` |
| `make verificar` | DoD completo: pytest + `npm run verificar` |
| `make help` | Lista todos os comandos disponíveis |

```bash
make install        # primeira execução (deps de dev + frontend)
make dev-backend    # terminal 1
make dev-frontend   # terminal 2
```

> **Windows:** instale o Make com `choco install make` ou `winget install ezwinports.make`. Não é necessário ativar o venv manualmente — os comandos usam o interpretador de `backend/.venv` diretamente.

As seções abaixo descrevem a execução manual, sem o Make.

### Configuração e Execução do Backend

##### Navegue até a pasta do backend:

```bash
cd backend
```

##### Crie e ative um ambiente virtual Python (utilizando Python 3.11+):

```bash
python3 -m venv .venv
```
```bash
source .venv/bin/activate          # Linux/macOS
.venv\Scripts\Activate.ps1         # Windows (PowerShell)
```

##### Instale as dependências do projeto:
Para desenvolvimento e testes (inclui as de produção):
```bash
pip install -r requirements-dev.txt
```
Em produção, apenas:
```bash
pip install -r requirements.txt
```

##### Configure as variáveis de ambiente:
```bash
cp .env.example .env
```
Edite o `.env` e preencha:
- `GOOGLE_API_KEY`: chave da API Google Gemini (obrigatória; nunca a envie para o repositório).
- `MODELO_LLM`: modelo Gemini usado na geração (padrão: `gemini-3.5-flash-lite`).
- `CHROMA_DIR`: pasta do ChromaDB, relativa a `backend/` (ex.: `./data/chroma`).
- `DATABASE_URL`: banco do catálogo (padrão: `sqlite:///./data/novamente.db`, relativo a `backend/`). O schema é criado no start da API; não há migrations nesta fase.

##### (Opcional) Liste os modelos disponíveis para a sua chave:
```bash
curl -s -H "x-goog-api-key: $GOOGLE_API_KEY" "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200"
```

##### Inicie o servidor de desenvolvimento do FastAPI:
```bash
uvicorn app.main:app --reload
```

### Configuração e Execução do Frontend
```bash
cd frontend
npm ci
```
##### Inicie o servidor de desenvolvimento do Next.js:
```bash
npm run dev
```

### Como Testar

##### No Backend (Testes de Contrato e Integração):

Certifique-se de estar com o ambiente virtual ativado na pasta backend/, com `requirements-dev.txt` instalado, e execute:
```bash
PYTHONPATH=. pytest tests/ -v
```

##### No Frontend (Testes e Linting):
```bash
npm run lint
npm test
```


### Licença

Este projeto foi desenvolvido para fins educacionais e de avaliação no âmbito do Hackathon ONE G10 (Oracle Next Education & Alura) sob a licença MIT.