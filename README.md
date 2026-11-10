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
| **Mario Lucio Breder Junior** | Product Manager / Developer  |
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
├── Makefile                # Atalhos de desenvolvimento (venv, backend, frontend)
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Rotas e endpoints REST da API
│   │   ├── core/           # Configurações globais, erros e engine SQLite
│   │   ├── models/         # Schemas Pydantic v2 e modelos ORM
│   │   ├── rag/            # Lógica de pipeline RAG, embeddings e ChromaDB
│   │   ├── services/       # OCI, extração, jobs, repositório, catálogo e alunos
│   │   └── main.py         # Ponto de entrada da aplicação FastAPI
│   ├── data/exemplos/      # Fixtures e textos de demonstração
│   │   └── novamente.db    # Banco SQLite local (gitignored, criado em runtime)
│   ├── tests/              # Testes unitários e de integração (pytest)
│   └── requirements.txt    # Dependências Python do backend
├── frontend/
│   ├── src/
│   │   ├── app/            # Rotas: landing, /empresa/* e /aluno/*
│   │   ├── components/     # UI, landing, empresa, aluno e visualizadores
│   │   ├── features/       # Hooks e regras de negócio encapsuladas
│   │   ├── services/       # Cliente de API e adaptadores de transporte
│   │   ├── types/          # Schemas Zod e tipos globais
│   │   └── mocks/          # Handlers e fixtures do MSW
│   ├── e2e/                # Playwright: fluxos, tour, responsivo e axe
│   └── package.json        # Dependências Node.js do frontend
└── docs/                   # Documentação técnica e especificações do projeto

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
| `make dev-backend` | Sobe a API FastAPI em `http://localhost:8000` |
| `make dev-frontend` | Sobe o Next.js em `http://localhost:3000` |
| `make install` | Cria o venv e instala as dependências do frontend |
| `make help` | Lista todos os comandos disponíveis |

```bash
make venv           # primeira execução
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





