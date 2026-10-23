# NovaMente — Spec do Backend FastAPI (MVP)

**Data:** 2026-10-21  
**Status:** Aprovado e integrado à spec do frontend  
**Escopo:** API REST em FastAPI, Pipeline de RAG (ChromaDB + Gemini) e Integração com OCI Object Storage  

---

## 1. Visão Geral e Objetivos

O backend do **NovaMente** é construído em **Python com FastAPI**, servindo como o motor de inteligência artificial, processamento de documentos e persistência de dados. Ele expõe a versão `v1` da API REST sob o prefixo `/api/v1` e consome diretamente os artefatos gerados pelo pipeline de Recuperação Aumentada por Geração (RAG).

### Objetivos Principais:
1. **Ingestão Flexível:** Processar entradas via JSON (texto colado) ou `multipart/form-data` (upload de arquivos `.pdf`, `.md`, `.txt`).
2. **Processamento Assíncrono (Jobs):** Executar tarefas longas de IA em background com acompanhamento de progresso em tempo real e suporte a cancelamento.
3. **Fidelidade de Contrato (Pydantic):** Garantir tipagem estrita de entrada e saída, espelhando exatamente os contratos definidos no frontend.
4. **Ancoragem RAG & LLM:** Integrar segmentação de texto, geração de *embeddings* e consultas parametrizadas ao Google Gemini.
5. **Persistência em Nuvem (OCI):** Armazenar os pacotes de conteúdo gerados em Buckets da Oracle Cloud Infrastructure (camada *Always Free*), com tratamento gracioso de falhas (*graceful degradation*).

---

## 2. Arquitetura e Estrutura de Diretórios

O diretório `backend/` é organizado seguindo os princípios de Separação de Preocupações (SoC) e Injeção de Dependências:

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── adaptacoes.py      # Endpoints de criação, listagem e exportação
│   │       ├── jobs.py            # Endpoints de consulta e cancelamento de jobs
│   │       ├── oci.py             # Status do bucket e saúde do armazenamento
│   │       └── health.py          # Liveness e verificação de dependências
│   ├── core/
│   │   ├── config.py              # Configurações de ambiente (Pydantic BaseSettings)
│   │   └── erros.py               # Exceções customizadas e normalização para ApiProblema
│   ├── models/
│   │   └── schemas.py             # Schemas Pydantic (1:1 com os tipos do frontend)
│   ├── rag/
│   │   └── servico.py             # Módulo de chunking, embeddings e ChromaDB
│   ├── services/
│   │   ├── extracao.py            # Parsing de PDF, Markdown e texto bruto
│   │   ├── pipeline.py            # Orquestração do prompt, LLM Gemini e cálculo de score
│   │   ├── repositorio.py         # Armazenamento em memória com TTL thread-safe
│   │   └── oci.py                 # Conexão e upload para o OCI Object Storage
│   ├── workers/
│   │   └── job_worker.py          # Execução assíncrona de jobs em threads separadas
│   └── main.py                    # Aplicação principal FastAPI, middlewares e exception handlers
├── data/
│   └── exemplos/                  # Fixtures e dados de demonstração
├── tests/
│   ├── api/                       # Testes de contrato com TestClient e Pytest
│   └── rag/                       # Testes unitários do pipeline de IA
├── requirements.txt               # Dependências unificadas do backend
└── .env.example                   # Exemplo de variáveis de ambiente
```

---

## 3. Contrato de Dados (Pydantic)

Todos os modelos de dados da API são validados rigorosamente por schemas Pydantic localizados em `backend/app/models/schemas.py`.

### 3.1 Enums de Domínio
```python
from enum import Enum

class PerfilDestinatario(str, Enum):
    INICIANTE = "Iniciante"
    DESENVOLVEDOR = "Desenvolvedor"
    LIDER_TECNICO = "LiderTecnico"
    GESTOR = "Gestor"

class FormatoSaida(str, Enum):
    FLASHCARDS = "Flashcards"
    QUIZ = "Quiz"
    TUTORIAL = "Tutorial"
    RESUMO_EXECUTIVO = "ResumoExecutivo"

class NichoSetor(str, Enum):
    FINTECH = "Fintech"
    SAUDE = "Saude"
    ECOMMERCE = "Ecommerce"
    GERAL = "Geral"

class NivelDetalhe(str, Enum):
    DIDATICO = "Didatico"
    TECNICO = "Tecnico"
    EXECUTIVO = "Executivo"

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EtapaJob(str, Enum):
    EXTRAINDO = "extraindo"
    CHUNKING = "chunking"
    EMBEDDINGS = "embeddings"
    GERANDO = "gerando"
    REVISANDO = "revisando"
    ARMAZENANDO = "armazenando"
```

### 3.2 Estrutura do Pacote Gerado (`AdaptacaoPacote`)
O resultado final entregue ao cliente contém a estrutura pedagógica adaptada, métricas de qualidade de ancoragem e metadados de persistência OCI.

---

## 4. Endpoints HTTP (`/api/v1`)

| # | Método | Rota | Descrição | Resposta de Sucesso |
|---|---|---|---|---|
| 1 | `POST` | `/adaptacoes` | Cria job a partir de texto (JSON) | `202 Accepted` |
| 2 | `POST` | `/adaptacoes/upload` | Cria job a partir de arquivo (`multipart`) | `202 Accepted` |
| 3 | `GET` | `/jobs/{job_id}` | Retorna o estado atual do job | `200 OK` |
| 4 | `DELETE` | `/jobs/{job_id}` | Cancela a execução de um job ativo | `200 OK` |
| 5 | `GET` | `/adaptacoes` | Lista histórico paginado com filtros | `200 OK` |
| 6 | `GET` | `/adaptacoes/{id}` | Retorna o pacote completo adaptado | `200 OK` |
| 7 | `GET` | `/adaptacoes/{id}/download` | Baixa o JSON bruto do pacote | `200 OK` (Attachment) |
| 8 | `GET` | `/adaptacoes/{id}/exportacao` | Exporta para Markdown, PDF ou CSV | `200 OK` (File) |
| 9 | `GET` | `/oci/status` | Retorna a saúde e status do Bucket OCI | `200 OK` |
| 10| `GET` | `/health` | Liveness check da API e dependências | `200 OK` |

---

## 5. Tratamento de Erros e Envelope `ApiProblema`

O backend padroniza todas as falhas utilizando um formato consistente de resposta de erro (`ApiProblema`):

```json
{
  "erro": {
    "codigo": "VALIDACAO",
    "mensagem": "O campo documento_titulo é obrigatório.",
    "campos": {
      "documento_titulo": "Preenchimento obrigatório"
    },
    "request_id": "req_9f8c7b6a"
  }
}
```

### Códigos de Erro Mapeados:
* `VALIDACAO`: Falha em regras de schema Pydantic.
* `ARQUIVO_INVALIDO`: Extensão ou MIME type não suportado.
* `DOCUMENTO_ILEGIVEL`: Impossível extrair texto do documento fornecido.
* `LIMITE_EXCEDIDO`: Arquivo > 10 MiB ou texto > 50.000 caracteres.
* `ADAPTACAO_NAO_ENCONTRADA` / `JOB_NAO_ENCONTRADO`: ID inexistente ou expirado (404).
* `JOB_FINALIZADO`: Tentativa de cancelar job já concluído (409).
* `FORMATO_INCOMPATIVEL`: Tentativa de exportar CSV de um pacote que não seja Flashcards (409).
* `OCI_INDISPONIVEL`: Falha de conexão persistente com o Object Storage (503).
* `INTERNO`: Erro genérico de servidor com rastreio de `request_id` (500).

---

## 6. Pipeline de RAG e Execução Assíncrona

1. **Ingestão e Parsing (`extracao.py`):** Extração de texto bruto a partir de arquivos PDF, Markdown ou texto enviado diretamente.
2. **Segmentação e Vetorização (`rag/servico.py`):** Divisão do texto em pedaços (*chunks*) e indexação vetorial utilizando ChromaDB / FAISS e embeddings otimizados.
3. **Orquestração com LLM (`pipeline.py`):** Construção de prompts contextuais injetados no Google Gemini para gerar saídas estruturadas adaptadas ao perfil do usuário.
4. **Persistência OCI (`oci.py`):** Upload assíncrono do arquivo gerado para o bucket do Oracle Cloud Infrastructure (com tratamento gracioso caso as credenciais não estejam configuradas localmente).

---

## 7. Validação e Testes

A suíte de testes automatizados é executada via `pytest` e cobre contratos de API, cenários de erro e componentes do RAG:

```bash
# Executar suíte completa de testes no backend
PYTHONPATH=backend pytest backend/tests/ -v