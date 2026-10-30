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
| **Mario Lucio Breder Junior** | Product Manager / Developer  |
| **Renato Campos** | Tech Lead / Vibe Coder |

---

## Stack Tecnológica
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn, LangChain, ChromaDB (Vector Store), Google Gemini API (LLM).
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Hook Form + Zod, Framer Motion, React Markdown.
- **Armazenamento e Nuvem:** OCI Object Storage (Oracle Cloud Infrastructure - camada *Always Free*).
- **Testes e Qualidade:** Pytest, Vitest, Testing Library, Playwright e MSW (*Mock Service Worker*) para contratos de rede.

---

## Estrutura do Projeto
O repositório está organizado como um monorepo contendo os módulos de backend e frontend, além de diretórios de documentação:

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Rotas e endpoints REST da API
│   │   ├── core/           # Configurações globais e tratamento de erros
│   │   ├── models/         # Schemas Pydantic v2
│   │   ├── rag/            # Lógica de pipeline RAG, embeddings e ChromaDB
│   │   ├── services/       # Serviços de OCI, extração, jobs e repositório
│   │   └── main.py         # Ponto de entrada da aplicação FastAPI
│   ├── data/exemplos/      # Fixtures e textos de demonstração
│   ├── tests/              # Testes unitários e de integração (pytest)
│   └── requirements.txt    # Dependências Python do backend
├── frontend/
│   ├── src/
│   │   ├── app/            # Rotas do Next.js (Gerar, Resultado, Histórico)
│   │   ├── components/     # Componentes de UI, formulários e visualizadores
│   │   ├── features/       # Hooks e regras de negócio encapsuladas
│   │   ├── services/       # Cliente de API e adaptadores de transporte
│   │   ├── types/          # Schemas Zod e tipos globais
│   │   └── mocks/          # Handlers e fixtures do MSW
│   └── package.json        # Dependências Node.js do frontend
└── docs/                   # Documentação técnica e especificações do projeto

```




## Pré-requisitos

#### Para executar o projeto localmente, certifique-se de possuir as seguintes ferramentas instaladas:

- Python 3.11 ou superior (recomendado o uso de ambiente virtual).

- Node.js (versão 20 ou superior) e gerenciador de pacotes (npm, pnpm ou yarn).

- Git para controle de versão.

- Chaves de API configuradas para acesso ao modelo de IA (Google Gemini) e opcionais credenciais da OCI Object Storage (caso deseje testar a persistência em nuvem).

## Como Executar

### Clonar o Repositório

```bash
git clone https://github.com/No-Country-simulation/G10-BRASIL-EQUIPO-25-NovaMente.git
cd G10-BRASIL-EQUIPO-25-NovaMente
```

### Configuração e Execução do Backend

##### Navegue até a pasta do backend:

```bash
cd backend
```

##### Crie e ative um ambiente virtual Python (utilizando Python 3.11):

```bash
python3.11 -m venv venv
```
```bash
source venv/bin/activate
```

##### Instale as dependências do projeto:
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

Certifique-se de estar com o ambiente virtual ativado na pasta backend/ e execute:
```bash
PYTHONPATH=. pytest tests/ -v
```

##### No Frontend (Testes e Linting):
```bash
npm run lint
npm test
```





