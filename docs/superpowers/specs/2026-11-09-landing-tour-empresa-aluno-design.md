# NovaMente — Landing, tour, área da empresa e área do aluno

**Data:** 2026-11-09
**Status:** design aprovado na conversa; spec revisada por builder check em 2026-11-09; aguardando aprovação final
**Escopo:** frontend Next.js, backend FastAPI, persistência SQLite e contrato HTTP

Fontes de verdade:

- `docs/proposta.md` — visão do produto, problema, pilares pedagógicos, MVP e equipe.
- `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md` — contrato atual de dados, rotas e renderizadores.
- Este documento — resolve a separação empresa × aluno, o CRUD sem autenticação e o tour.

Quando este documento divergir da spec de 2026-10-21, **este documento vence** para os pontos que ele cobre. O restante da spec anterior continua valendo.

---

## 1. Objetivo

Transformar o NovaMente de uma aplicação de geração em um produto com três portas de entrada:

1. **Landing pública** que explica o problema, a proposta e os formatos, com CTAs claros.
2. **Área da empresa/educador** — a aplicação atual (gerar, acompanhar, abrir resultado, histórico) mais o CRUD de materiais e alunos.
3. **Área do aluno** — identificação leve e catálogo somente de leitura com os materiais que a empresa publicou e vinculou àquele aluno.

Além disso, um **tour guiado** percorre as telas reais para demonstrar o funcionamento de ponta a ponta.

Sucesso significa:

1. Um visitante entende o produto na landing e chega à área correta em um clique.
2. A empresa consegue criar, listar, editar, publicar, despublicar e excluir materiais.
3. A empresa consegue criar, listar, editar e excluir alunos e gerenciar os vínculos aluno ↔ material.
4. O aluno vê apenas materiais `publicado` vinculados a ele e estuda nos renderizadores existentes, sem gerar nem enviar nada.
5. O tour funciona nas telas reais, pode ser repetido e não bloqueia quem só quer usar o site.
6. Os fluxos atuais de geração, resultado, histórico, exportação e OCI continuam funcionando.

---

## 2. Decisões

| # | Decisão | Alternativa descartada | Motivo |
|---|---|---|---|
| D1 | Landing em `/`; empresa em `/empresa/*`; aluno em `/aluno/*` | Abas ou troca de papel no mesmo shell | Separação real de público, URL e permissão de tela |
| D2 | SQLite + SQLAlchemy como fonte durável | JSON em disco ou listar o OCI | Consultas, unicidade, integridade referencial e testes simples |
| D3 | OCI continua guardando os artefatos; SQLite guarda metadados e o JSON do pacote | OCI como único armazenamento | O listamento do bucket não é um catálogo consultável |
| D4 | Material nasce como `rascunho` na conclusão do job | Nascer `publicado` | O aluno só vê o que a empresa decidiu liberar |
| D5 | Conteúdo do material é imutável; edição altera só título de catálogo e visibilidade | Editar flashcards/quiz/markdown manualmente | Evita divergência entre conteúdo, ancoragem e exportação |
| D6 | Identificação do aluno por seleção de nome, sem senha | Login, magic link ou código por aluno | Autenticação está fora desta fase, por decisão do produto |
| D7 | Servidor filtra catálogo do aluno por `publicado` + vínculo + aluno `ativo` | Filtrar só no cliente | Não vaza material não liberado por URL direta |
| D8 | A tela de vínculos aplica diferenças com POST/DELETE; `PUT` atômico existe na API para uso em lote | Painel salvar o conjunto inteiro | A lista de materiais é paginada; salvar só o que está visível desvincularia o resto |
| D9 | Tour com `driver.js` sobre elementos reais marcados com `data-tour` | Tour em slides ou vídeo | Demonstra o produto de verdade e acompanha mudanças de layout |
| D10 | Tour automático só na primeira visita a `/empresa`; landing tem CTA manual | Auto-start na landing | Evita bloquear visitante novo e mantém o tour descobrível |
| D11 | Rotas antigas redirecionadas permanentemente | Quebrar links e testes existentes | Preserva URLs compartilhadas e histórico |
| D12 | `owner_id` nulo reservado em `alunos` e `materiais`; nenhuma autenticação implementada | Criar login agora | Prepara a evolução sem entregar meia autenticação |
| D13 | Sem exclusão de objeto OCI bloqueante | Falhar a exclusão se o OCI falhar | Metadados são a fonte; o OCI é best-effort e a UI informa |

---

## 3. Escopo

### Dentro

- Landing pública em `/`, com conteúdo da proposta do projeto.
- Reorganização de rotas: `/empresa/gerar`, `/empresa/historico`, `/empresa/resultado/[id]`, `/empresa/materiais`, `/empresa/alunos`, `/empresa/alunos/[id]`.
- Área do aluno: `/aluno` e `/aluno/materiais/[id]`.
- CRUD de alunos.
- CRUD de materiais (criação pelo pipeline, leitura, edição de metadados e visibilidade, exclusão).
- CRUD de vínculos aluno ↔ material.
- Persistência SQLite, com migração do repositório em memória.
- Tour guiado com `driver.js`.
- Mocks MSW, fixtures, testes unitários, de componente e E2E.
- Redirecionamentos das rotas antigas.

### Fora

- Autenticação, senha, sessão, JWT, OAuth, magic link, e-mail transacional.
- Multilocação real, papéis, permissões por empresa e cobrança.
- Aluno gerar, enviar, editar, publicar ou excluir material.
- Edição do conteúdo gerado (flashcards, quiz, markdown) ou regeneração parcial.
- Progresso do aluno, notas, tentativas de quiz persistidas, certificados.
- Notificações, comentários, chat ou fórum.
- Aplicativo mobile nativo.
- Internacionalização (continua pt-BR).
- Deploy, domínio, proxy reverso e configuração de produção.
- Administração do bucket OCI (criar, listar, apagar em lote).
- Importação de material legado de outro sistema.
- Tour como vídeo ou apresentação separada.

---

## 4. Arquitetura

### 4.1 Visão

```
Landing (/)
  ├── CTA empresa ──► /empresa/*  ──► API /api/v1/alunos, /materiais, /adaptacoes
  └── CTA aluno   ──► /aluno/*    ──► API /api/v1/aluno/*
                                         │
                              SQLite (metadados + pacote JSON)
                                         │
                              OCI (artefatos originais/gerados)
```

- O frontend continua sem `fetch` em componente: hooks → `NovaMenteApi` → `httpApiClient` → MSW em dev/teste.
- O backend mantém o envelope `ApiProblema` e o prefixo `/api/v1`.
- Jobs continuam em memória por 30 minutos; pacotes e catálogo passam a ser duráveis.
- `repositorio.py` vira fachada: jobs em memória; pacotes lidos/escritos na tabela `materiais`.

### 4.2 Rotas do frontend

| Rota | Público | Conteúdo |
|---|---|---|
| `/` | Todos | Landing |
| `/empresa` | Empresa | Redireciona para `/empresa/gerar` |
| `/empresa/gerar` | Empresa | Formulário + cenários + progresso (tela atual de `/`) |
| `/empresa/historico` | Empresa | Histórico atual |
| `/empresa/resultado/[id]` | Empresa | Resultado atual, com painel OCI e exportação |
| `/empresa/materiais` | Empresa | Catálogo administrativo, filtros e ações |
| `/empresa/alunos` | Empresa | Lista e CRUD de alunos |
| `/empresa/alunos/[id]` | Empresa | Dados do aluno e vínculos com materiais |
| `/aluno` | Aluno | Identificação (se necessário) + catálogo |
| `/aluno/materiais/[id]` | Aluno | Visualização do material |

Redirects permanentes em `next.config.ts`:

| De | Para |
|---|---|
| `/historico` | `/empresa/historico` |
| `/resultado/:id` | `/empresa/resultado/:id` |

`/` deixa de renderizar `GerarView`; nenhum redirect é aplicado à raiz.

### 4.3 Estrutura de pastas

```
frontend/src/
  app/
    (public)/page.tsx                      → /
    (empresa)/empresa/layout.tsx           → EmpresaShell
    (empresa)/empresa/page.tsx             → redirect /empresa/gerar
    (empresa)/empresa/gerar/page.tsx
    (empresa)/empresa/historico/page.tsx
    (empresa)/empresa/materiais/page.tsx
    (empresa)/empresa/alunos/page.tsx
    (empresa)/empresa/alunos/[id]/page.tsx
    (empresa)/empresa/resultado/[id]/page.tsx
    (aluno)/aluno/layout.tsx               → AlunoShell
    (aluno)/aluno/page.tsx
    (aluno)/aluno/materiais/[id]/page.tsx
  components/
    landing/                               Hero, Problema, ComoFunciona, Formatos,
                                           Publicos, Tecnologia, Pedagogia, Equipe, Footer
    layout/
      LandingHeader.tsx
      EmpresaShell.tsx                     (AppShell atual renomeado)
      EmpresaHeader.tsx                    (Header atual, nav ampliada)
      AlunoShell.tsx
      AlunoHeader.tsx
      TourLauncher.tsx
    materiais/
      MateriaisView.tsx
      MaterialCard.tsx
      MaterialEditDialog.tsx
      MaterialDeleteDialog.tsx
    alunos/
      AlunosView.tsx
      AlunoCard.tsx
      AlunoFormDialog.tsx
      AlunoDeleteDialog.tsx
      AlunoDetalheView.tsx
      VinculosPanel.tsx
    aluno/
      IdentificacaoAluno.tsx
      CatalogoAlunoView.tsx
      AlunoMaterialView.tsx
  features/
    alunos/useAlunos.ts
    alunos/useAluno.ts
    alunos/useAlunoMutations.ts
    alunos/useVinculos.ts
    materiais/useMateriais.ts
    materiais/useMaterialMutations.ts
    aluno/useIdentidadeAluno.ts
    aluno/useCatalogoAluno.ts
    aluno/useMaterialAluno.ts
    tour/useTour.ts
  services/api/                               (NovaMenteApi, endpoints e client ampliados)
  types/schemas.ts                            (schemas zod novos)
  mocks/handlers/                             (alunos.ts, materiais.ts, vinculos.ts, aluno.ts)
  mocks/fixtures/                             (alunos.json, materiais.json)
  lib/mensagens.ts                            (M.landing, M.tour, M.alunos, M.materiais, M.aluno)
```

### 4.4 Backend

```
backend/app/
  core/db.py                  engine, SessionLocal, Base, get_db
  models/db.py                AlunoDB, MaterialDB, VinculoDB (SQLAlchemy 2.0)
  models/__init__.py          schemas Pydantic novos (além dos existentes)
  api/v1/routers/alunos.py
  api/v1/routers/materiais.py
  api/v1/routers/aluno.py
  services/alunos.py          regras de aluno e vínculo
  services/materiais.py       regras de material e publicação
  services/repositorio.py     fachada: jobs em memória; pacotes em SQLite
```

`main.py` registra os três routers e cria as tabelas no `lifespan` com `Base.metadata.create_all(bind=engine)`.

Dependências novas (fixadas no lockfile na implementação):

- Backend: `sqlalchemy>=2.0,<3` e `email-validator` (usado por `EmailStr`).
- Frontend: `driver.js` (1.x).
- `backend/data/*.db`, `*.db-wal` e `*.db-shm` entram no `.gitignore`.

O `src/app/page.tsx` atual é removido; a rota `/` passa a vir de `src/app/(public)/page.tsx`.

### 4.5 Autenticação futura

- Nenhum token, cookie, sessão ou middleware de auth nesta fase.
- `alunos.owner_id` e `materiais.owner_id` existem como `TEXT NULL`, sempre nulos, fora do contrato público.
- Routers e serviços recebem dependências isoladas; quando a auth entrar, ela vira uma dependência de router e o filtro por `owner_id`, sem reescrever as regras.
- A identificação do aluno é **conveniência de UI**, não segurança: o servidor confia no `aluno_id` recebido. Isso é aceitável porque ainda não há dado real de aluno em produção.

---

## 5. Modelo de dados

### 5.1 SQLite

Arquivo padrão: `backend/data/novamente.db` (`DATABASE_URL=sqlite:///./data/novamente.db`).

Habilitar `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON` e `check_same_thread=False`.

```sql
CREATE TABLE alunos (
  aluno_id     TEXT PRIMARY KEY,
  nome         TEXT NOT NULL,
  email        TEXT NOT NULL COLLATE NOCASE UNIQUE,
  status       TEXT NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo','inativo')),
  owner_id     TEXT NULL,
  criado_em    TEXT NOT NULL,
  atualizado_em TEXT NOT NULL
);

CREATE TABLE materiais (
  material_id              TEXT PRIMARY KEY,
  adaptacao_id             TEXT NOT NULL UNIQUE,
  titulo                   TEXT NOT NULL,
  documento_titulo         TEXT NOT NULL,
  documento_origem         TEXT NOT NULL,
  documento_nome_arquivo   TEXT NULL,
  documento_tamanho_bytes  INTEGER NULL,
  perfil                   TEXT NOT NULL,
  formato                  TEXT NOT NULL,
  nivel                    TEXT NOT NULL,
  nicho                    TEXT NOT NULL,
  tempo_estimado_minutos   INTEGER NOT NULL,
  ancoragem_score          REAL NOT NULL,
  status_upload            TEXT NOT NULL
                           CHECK (status_upload IN ('concluido','falha')),
  conceitos_chave_json     TEXT NOT NULL,
  oci_objeto_id            TEXT NOT NULL,
  visibilidade             TEXT NOT NULL DEFAULT 'rascunho'
                           CHECK (visibilidade IN ('rascunho','publicado')),
  pacote_json              TEXT NOT NULL,
  owner_id                 TEXT NULL,
  criado_em                TEXT NOT NULL,
  atualizado_em            TEXT NOT NULL
);

CREATE TABLE vinculos (
  aluno_id    TEXT NOT NULL REFERENCES alunos(aluno_id) ON DELETE CASCADE,
  material_id TEXT NOT NULL REFERENCES materiais(material_id) ON DELETE CASCADE,
  criado_em   TEXT NOT NULL,
  PRIMARY KEY (aluno_id, material_id)
);

CREATE INDEX ix_alunos_status ON alunos(status);
CREATE INDEX ix_materiais_visibilidade ON materiais(visibilidade);
CREATE INDEX ix_materiais_formato ON materiais(formato);
CREATE INDEX ix_materiais_ancoragem ON materiais(ancoragem_score);
CREATE INDEX ix_vinculos_material ON vinculos(material_id);
```

Regras:

- IDs são ULID em texto.
- No MVP, `material_id` é **igual** a `adaptacao_id`: o material é o registro de catálogo do pacote. Os dois campos ficam no contrato para permitir versionamento futuro sem quebrar URLs.
- Datas são ISO 8601 UTC com sufixo `Z`.
- `email` é normalizado para minúsculas antes de gravar; a coluna `NOCASE` garante unicidade.
- `pacote_json` guarda o `AdaptacaoPacote` completo e imutável. Leitura valida com `AdaptacaoPacote.model_validate_json`; pacote corrompido produz `500 INTERNO` no detalhe, mas não impede a listagem.
- `titulo` do material é o nome de catálogo. Nasce de `pacote.conteudo_adaptado.titulo` truncado em 150 caracteres; editar não altera `pacote_json`.
- As colunas `documento_*`, `perfil`, `formato`, `nivel`, `nicho`, `tempo_estimado_minutos`, `ancoragem_score`, `status_upload`, `conceitos_chave_json` e `oci_objeto_id` são cópias desnormalizadas do pacote. **Nenhum endpoint de listagem desserializa `pacote_json`**: todos os campos de `MaterialResumo`, `AdaptacaoResumo` e do catálogo do aluno saem dessas colunas. `conceitos_chave_json` é um array JSON de strings; `oci_objeto_id` é usado pelo `DELETE` sem abrir o pacote.
- `visibilidade` nasce `rascunho` quando o pipeline conclui.
- `owner_id` reservado, sempre `NULL`, não exposto.

### 5.2 Migração do repositório

- `salvar_pacote(pacote)` passa a inserir/atualizar a linha em `materiais` (idempotente por `adaptacao_id`). Se a linha já existir, atualiza `pacote_json` e os campos desnormalizados, preservando `visibilidade` e `titulo` editados.
- O job só marca `succeeded` depois do commit da linha em `materiais`. Falha de banco leva o job a `failed` com `INTERNO`; um objeto OCI órfão é tolerado e registrado em log.
- `obter_pacote(id)` e `listar_pacotes()` leem `pacote_json` de `materiais`.
- Jobs continuam em memória, com o mesmo TTL.
- Não há backfill: pacotes antigos viviam só em memória e desaparecem no reinício, como já acontece hoje.
- `DELETE /materiais/{id}` remove a linha; consequentemente `/adaptacoes/{id}`, `/download` e `/exportacao` passam a responder 404.

---

## 6. Contrato HTTP

Base: `/api/v1`. Sem autenticação. JSON em `application/json; charset=utf-8`, exceto download/exportação. Erros no envelope `ApiProblema` existente.

### 6.1 Enums e schemas novos

```ts
export type StatusAluno = 'ativo' | 'inativo';
export type VisibilidadeMaterial = 'rascunho' | 'publicado';

export interface AlunoCriacao {
  nome: string;                  // 3..120 após trim
  email: string;                 // e-mail válido, até 254; normalizado para minúsculas
  status?: StatusAluno;          // default 'ativo'
}

export interface AlunoAtualizacao {
  nome?: string;
  email?: string;
  status?: StatusAluno;
}
// PATCH: ao menos um campo; corpo vazio ou campo desconhecido → 422 VALIDACAO

export interface AlunoResumo {
  aluno_id: string;
  nome: string;
  email: string;
  status: StatusAluno;
  total_materiais: number;
  criado_em: string;
  atualizado_em: string;
}

export interface PaginaAlunos {
  itens: AlunoResumo[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
}

export interface MaterialResumo {
  material_id: string;
  adaptacao_id: string;
  titulo: string;
  documento_titulo: string;
  perfil: PerfilDestinatario;
  formato: FormatoSaida;
  nivel: NivelDetalhe;
  nicho: NichoSetor;
  visibilidade: VisibilidadeMaterial;
  tempo_estimado_estudo_minutos: number;
  ancoragem_fonte_score: number;
  status_upload: 'concluido' | 'falha';
  criado_em: string;
  atualizado_em: string;
}

export interface MaterialDetalhe {
  material: MaterialResumo;
  pacote: AdaptacaoPacote;
}

export interface MaterialAtualizacao {
  titulo?: string;               // 3..150 após trim
  visibilidade?: VisibilidadeMaterial;
}

export interface PaginaMateriais {
  itens: MaterialResumo[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
}

export interface VinculoMaterial {
  material_id: string;
  titulo: string;
  formato: FormatoSaida;
  perfil: PerfilDestinatario;
  visibilidade: VisibilidadeMaterial;
  vinculado_em: string;
}

export interface VinculosAluno {
  aluno_id: string;
  itens: VinculoMaterial[];
}

export interface AtualizarVinculosInput {
  material_ids: string[];        // até 500; substitui o conjunto inteiro
}

export interface RemocaoMaterialResposta {
  material_id: string;
  removido: true;
  oci_removido: boolean;
  aviso?: string;
}

export interface IdentificacaoAlunoItem {
  aluno_id: string;
  nome: string;
}
```

`ItemCatalogoAluno` é `Pick<MaterialResumo, 'material_id' | 'titulo' | 'documento_titulo' | 'formato' | 'perfil' | 'nivel' | 'tempo_estimado_estudo_minutos' | 'criado_em'>` acrescido de `conceitos_chave: string[]` (até 6).

```ts
export interface PaginaCatalogoAluno {
  itens: ItemCatalogoAluno[];
  pagina: number;
  tamanho_pagina: number;
  total: number;
  total_paginas: number;
}
```

### 6.2 Alunos (empresa)

| # | Método | Rota | Sucesso |
|---|---|---|---|
| 1 | POST | `/alunos` | 201 `AlunoResumo` |
| 2 | GET | `/alunos` | 200 `PaginaAlunos` |
| 3 | GET | `/alunos/{aluno_id}` | 200 `AlunoResumo` |
| 4 | PATCH | `/alunos/{aluno_id}` | 200 `AlunoResumo` |
| 5 | DELETE | `/alunos/{aluno_id}` | 204, sem corpo |
| 6 | GET | `/alunos/{aluno_id}/materiais` | 200 `VinculosAluno` |
| 7 | PUT | `/alunos/{aluno_id}/materiais` | 200 `VinculosAluno` |
| 8 | POST | `/alunos/{aluno_id}/materiais/{material_id}` | 201 novo, 200 existente |
| 9 | DELETE | `/alunos/{aluno_id}/materiais/{material_id}` | 204 idempotente |

**GET `/alunos`** — query:

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `q` | string | — | 1..100; busca nome e e-mail |
| `status` | enum | — | `ativo` ou `inativo` |
| `ordenar` | enum | `nome:asc` | `nome:asc`, `nome:desc`, `criado_em:desc` |

Resposta vazia devolve `itens: []`, `total: 0`, `total_paginas: 0`. Parâmetro inválido → 422 `VALIDACAO` com `campos`.

**POST `/alunos`**:
- `email` duplicado (case-insensitive) → 409 `EMAIL_JA_CADASTRADO` com `campos.email = "E-mail já cadastrado."`.
- Campos inválidos → 422 `VALIDACAO` com `campos`.

**PATCH `/alunos/{aluno_id}`**:
- 404 `ALUNO_NAO_ENCONTRADO` se não existir.
- 409 `EMAIL_JA_CADASTRADO` se o novo e-mail pertencer a outro aluno.
- `atualizado_em` sempre renovado.

**DELETE `/alunos/{aluno_id}`**:
- 404 se não existir.
- Remove em cascata os vínculos. Materiais não são tocados.

**PUT `/alunos/{aluno_id}/materiais`**:
- Substituição atômica: valida todos os `material_ids`; se qualquer id não existir, 422 `VALIDACAO` com `campos.material_ids` e **nada** é alterado.
- Duplicatas no array são deduplicadas.
- Materiais `rascunho` podem ser vinculados; o aluno só os verá após publicação.
- Ids repetidos não geram erro.
- A UI **não usa** este endpoint: como `/materiais` é paginado e filtrável, o painel envia apenas as diferenças via POST/DELETE. O PUT fica disponível para operações em lote via API.

**GET `/alunos/{aluno_id}/materiais`**:
- Devolve **todos** os vínculos do aluno, sem paginação; o volume esperado no MVP é pequeno e o painel só precisa dos ids para marcar os checkboxes.
- Ordena por `vinculado_em:desc`.

**POST/DELETE de vínculo individual**:
- POST é idempotente e responde `201` na criação e `200` se já existia.
- DELETE responde `204` mesmo se o vínculo não existia.
- Material ou aluno inexistente → 404 com o código correspondente.

### 6.3 Materiais (empresa)

| # | Método | Rota | Sucesso |
|---|---|---|---|
| 10 | GET | `/materiais` | 200 `PaginaMateriais` |
| 11 | GET | `/materiais/{material_id}` | 200 `MaterialDetalhe` |
| 12 | PATCH | `/materiais/{material_id}` | 200 `MaterialResumo` |
| 13 | DELETE | `/materiais/{material_id}` | 200 `RemocaoMaterialResposta` |

**Criação (o "C" do CRUD)** — não existe `POST /materiais`. A criação continua sendo `POST /adaptacoes` ou `POST /adaptacoes/upload`; quando o job termina com sucesso, o pipeline grava o material com `visibilidade: "rascunho"`. Isso mantém uma única origem para conteúdo gerado, ancoragem e exportação.

**GET `/materiais`** — query:

| Query | Tipo | Default | Regra |
|---|---|---|---|
| `pagina` | inteiro | 1 | ≥ 1 |
| `tamanho_pagina` | inteiro | 12 | 1..50 |
| `q` | string | — | 1..100; busca título e título do documento |
| `formato` | enum | — | `FormatoSaida` |
| `perfil` | enum | — | `PerfilDestinatario` |
| `visibilidade` | enum | — | `rascunho` ou `publicado` |
| `ordenar` | enum | `criado_em:desc` | `criado_em:desc`, `criado_em:asc`, `ancoragem:desc`, `titulo:asc` |

**PATCH `/materiais/{material_id}`**:
- Aceita somente `titulo` e `visibilidade`; qualquer outro campo → 422.
- Corpo vazio → 422.
- 404 `MATERIAL_NAO_ENCONTRADO` se não existir.
- `atualizado_em` renovado.
- Publicar (`rascunho` → `publicado`) é idempotente.

**DELETE `/materiais/{material_id}`**:
- 404 se não existir.
- Remove a linha e os vínculos em cascata.
- Tenta remover o objeto OCI pelo `armazenamento_oci.objeto_id`.
- Responde `200` com `removido: true`, `oci_removido: boolean` e `aviso` quando a remoção no OCI falhar ou o OCI não estiver configurado.
- A falha no OCI não impede a remoção local.

### 6.4 Área do aluno

| # | Método | Rota | Sucesso |
|---|---|---|---|
| 14 | GET | `/aluno/identificacao` | 200 `{ itens: IdentificacaoAlunoItem[] }` |
| 15 | GET | `/aluno/materiais` | 200 `PaginaCatalogoAluno` |
| 16 | GET | `/aluno/materiais/{material_id}` | 200 `MaterialDetalhe` |

**GET `/aluno/identificacao`**:
- Lista somente alunos `ativo`, ordenados por nome.
- Devolve apenas `aluno_id` e `nome`; nunca e-mail.
- Lista vazia → `itens: []`, 200.

**GET `/aluno/materiais`** — query obrigatória `aluno_id`; opcionais `pagina`, `tamanho_pagina`, `q`, `formato`, `perfil`, `ordenar` (`criado_em:desc` padrão, `titulo:asc`).
- 404 `ALUNO_NAO_ENCONTRADO` se o aluno não existir.
- 403 `ALUNO_INATIVO` se o aluno estiver inativo.
- Inclui somente materiais `publicado` vinculados ao aluno.
- `total_materiais` do catálogo reflete o filtro aplicado.

**GET `/aluno/materiais/{material_id}?aluno_id=`**:
- 200 somente se o material estiver `publicado` **e** vinculado ao aluno.
- 404 `MATERIAL_NAO_DISPONIVEL` em qualquer outro caso (não existir, ser rascunho ou não estar vinculado). O mesmo código unifica os casos para não revelar existência de material não liberado.
- 403 `ALUNO_INATIVO` se o aluno estiver inativo.

### 6.5 Erros novos

| HTTP | `codigo` | Quando |
|---|---|---|
| 409 | `EMAIL_JA_CADASTRADO` | E-mail já usado por outro aluno |
| 404 | `ALUNO_NAO_ENCONTRADO` | Aluno inexistente |
| 403 | `ALUNO_INATIVO` | Aluno inativo em rota de aluno |
| 404 | `MATERIAL_NAO_ENCONTRADO` | Material inexistente em rota de empresa |
| 404 | `MATERIAL_NAO_DISPONIVEL` | Material não publicado, não vinculado ou inexistente em rota de aluno |
| 422 | `VALIDACAO` | Corpo/query inválidos, com `campos` |
| 500 | `INTERNO` | Pacote corrompido ou falha inesperada, com `request_id` |

Códigos existentes permanecem iguais.

### 6.6 Compatibilidade

- `GET /adaptacoes`, `GET /adaptacoes/{id}`, `/download` e `/exportacao` continuam com o mesmo contrato, agora lendo de `materiais`.
- O job continua devolvendo `202` e o `JobResposta` inalterado.
- `AdaptacaoPacote` não muda.
- O frontend existente continua compilando; apenas as rotas de página mudam.

---

## 7. Frontend

### 7.1 Landing (`/`)

Server Component sempre que possível; nenhum dado de API. Conteúdo baseado em `docs/proposta.md`.

Seções, nesta ordem:

1. **Header** — logo, âncoras (Como funciona, Formatos, Tecnologia, Equipe), `SkinSwitcher`, "Ver tour", "Sou aluno" e "Área da empresa".
2. **Hero** — título com a promessa central (transformar documentação técnica em material didático personalizado), subtítulo com RAG + Gemini + OCI, CTAs "Começar pela empresa" e "Acessar como aluno", selo "ONE G10 Brasil · No Country · Alura".
3. **Problema** — semanas de produção manual, jargão inacessível, mesmo manual para públicos diferentes; números apenas se verificáveis, nunca inventados.
4. **Como funciona** — quatro passos: envie PDF/MD/TXT → escolha perfil, formato e nível → a pipeline RAG ancora e gera → a empresa publica e o aluno estuda.
5. **Formatos** — Flashcards, Quiz, Tutorial e Resumo Executivo, cada um com uma frase do que entrega.
6. **Dois públicos** — painel "Para empresas e educadores" (gerar, publicar, acompanhar) e painel "Para alunos" (entrar e estudar), com CTAs.
7. **Tecnologia e confiança** — ancoragem estrita na fonte, score de ancoragem, ChromaDB, Gemini, persistência OCI. Não citar multi-agentes, deploy em OCI Compute, feedback em tempo real nem recursos fora do MVP.
8. **Fundamentação pedagógica** — scaffolding, carga cognitiva e microlearning em três blocos curtos.
9. **Equipe e realização** — os três integrantes com papéis, link do repositório e crédito ao programa ONE.
10. **Footer** — navegação, créditos e aviso de projeto de hackathon.

Regras:

- Copy em `M.landing`, pt-BR, sem promessas que o produto não cumpre.
- Nenhum depoimento, logo de cliente ou métrica fictícia.
- Todo CTA leva a uma rota existente; nada de botão morto.
- `metadata` específica da landing (title, description, Open Graph). Áreas `/empresa` e `/aluno` recebem `robots: { index: false }`.
- Movimento com Framer Motion respeita `prefers-reduced-motion`.
- A landing não importa `driver.js` nem os renderizadores no bundle inicial.

### 7.2 Tour

Implementação: `driver.js` carregado por `import()` dinâmico dentro do handler; nunca no bundle inicial.

**Elementos estáveis** marcados com `data-tour`:

| Seletor | Onde |
|---|---|
| `landing-hero` | Hero da landing |
| `landing-publicos` | Bloco dos dois públicos |
| `empresa-nav` | Navegação do header da empresa |
| `empresa-gerar-form` | Formulário de geração |
| `empresa-historico-lista` | Lista/grade do histórico |
| `empresa-materiais-lista` | Lista de materiais |
| `empresa-alunos-lista` | Lista de alunos |
| `aluno-identificacao` | Cartão de identificação |
| `aluno-catalogo` | Grade do catálogo do aluno |

**Passos** (8):

1. Boas-vindas + o que é o NovaMente — `landing-hero`.
2. Empresa ou aluno — `landing-publicos`.
3. Área da empresa e navegação — `/empresa/gerar` + `empresa-nav`.
4. Gerar material — `empresa-gerar-form`.
5. Histórico — `/empresa/historico` + `empresa-historico-lista`.
6. Catálogo e publicação — `/empresa/materiais` + `empresa-materiais-lista`.
7. Alunos e vínculos — `/empresa/alunos` + `empresa-alunos-lista`.
8. Área do aluno — `/aluno` + `aluno-identificacao` (ou `aluno-catalogo`, se já identificado).

**Comportamento por ponto de entrada**:

| Origem | Passos | Navegação |
|---|---|---|
| "Ver tour" em `/` | 1–8 | Começa na landing e segue o roteiro completo |
| "Ver tour" em `/empresa/*` | 3–8 | Começa na área da empresa; não volta à landing |
| "Ver tour" em `/aluno*` | 8 | Tour curto só da experiência do aluno; nunca entra em `/empresa` |
| Auto-start em `/empresa/gerar` | 3–8 | Uma vez por navegador, após 600 ms, se `novamente.tour` não existir |
| `?tour=1` em qualquer rota | 1–8 | Força o roteiro completo, inclusive a partir da área do aluno |

- Deep links de `/empresa/*` que não sejam `/empresa/gerar` não iniciam o tour automaticamente.
- "Ver tour" sempre ignora o flag de conclusão e reinicia o subconjunto correspondente.
- Auto-start nunca ocorre em `/`, `/empresa/historico`, `/empresa/materiais`, `/empresa/alunos` ou `/aluno*`.
- Persistência: `novamente.tour` = `{ "versao": 1, "concluido_em": "<ISO>" }`. Incrementar `versao` reexibe o tour.
- Cada passo navega com `router.push` e aguarda o seletor por até 2.500 ms (MutationObserver + timeout). Se o alvo não aparecer, o passo é pulado e o tour continua.
- Elementos ausentes por estado vazio (ex.: lista sem itens) continuam válidos: o alvo é o container, não o item.
- "Pular tour" e `Esc` encerram e gravam conclusão. Concluir também grava.
- Sem dependência do backend: funciona com listas vazias e sem jobs.
- Não inicia automaticamente em `/aluno`.
- Acessibilidade: foco preso ao popover do driver, navegação por teclado, `aria-live="polite"` anunciando o título do passo, botões ≥ 44 px, `prefers-reduced-motion` remove animações, contraste AA nas duas skins.
- Textos em `M.tour`.

### 7.3 Área da empresa

`EmpresaShell` reaproveita o `AppShell` atual. Header:

- Logo → `/`.
- Nav: Gerar (`/empresa/gerar`), Histórico (`/empresa/historico`), Materiais (`/empresa/materiais`), Alunos (`/empresa/alunos`).
- Ações: "Ver tour", `SkinSwitcher` e link "Área do aluno" → `/aluno`.
- Mobile: menu acessível por botão, com os mesmos itens.

`/empresa` redireciona para `/empresa/gerar` (sem dashboard nesta fase).

**Materiais** (`/empresa/materiais`):

- Grade de cards (desktop 3 colunas, mobile 1) com título, documento, badges de formato/perfil/nível, visibilidade, data e ações.
- Filtros: busca com debounce de 300 ms, formato, perfil, visibilidade e ordenação; refletidos na URL.
- Ações por card: Abrir (→ `/empresa/resultado/[id]`), Editar, Publicar/Despublicar e Excluir.
- Editar abre `MaterialEditDialog` com título (3..150) e visibilidade; erros 422 voltam ao campo.
- Excluir abre confirmação com o título do material. Sucesso mostra toast; `aviso` de OCI aparece como aviso secundário.
- Estados: skeleton em grade, vazio com CTA "Gerar material", erro com retry, paginação numerada.
- Publicar/despublicar é otimista com rollback em erro.

**Resultado** (`/empresa/resultado/[id]`):

- Usa `GET /materiais/{id}` (não `GET /adaptacoes/{id}`) para obter `material` + `pacote`.
- Cabeçalho mostra o `titulo` do catálogo, badges de perfil/formato/nicho/nível, visibilidade e tempo estimado, além de "Editar" e "Publicar/Despublicar".
- Corpo mantém o `ContentRenderer` e o `OCIPanel`; exportação e "Baixar JSON" continuam iguais.
- `id` da rota é `material_id`, que é igual a `adaptacao_id` nesta fase.
- 404 `MATERIAL_NAO_ENCONTRADO` mostra o estado de material não encontrado com link para `/empresa/materiais`.

**Alunos** (`/empresa/alunos`):

- Lista em tabela no desktop e cards no mobile: nome, e-mail, status, total de materiais, data e ações.
- Filtros: busca, status e ordenação, refletidos na URL.
- Ações: Editar, Excluir e "Materiais" (→ detalhe).
- `AlunoFormDialog` cria e edita com nome, e-mail e status; validação zod no `onBlur` e no submit; `409 EMAIL_JA_CADASTRADO` mapeia para o campo e-mail.
- Excluir confirma e avisa que os vínculos serão removidos.
- Estados de carregando, vazio, erro e paginação.

**Detalhe do aluno** (`/empresa/alunos/[id]`):

- Cabeçalho com nome, e-mail, status, total de materiais e ações Editar/Excluir.
- `VinculosPanel` lista os materiais de forma paginada (12 por página) com checkbox, badge de formato e badge de visibilidade (`rascunho`/`publicado`).
- O estado inicial dos checkboxes vem de `GET /alunos/{id}/materiais` (lista completa de vínculos); a página visível vem de `GET /materiais`.
- Busca por título e filtro de formato dentro do painel. Material vinculado que não aparece no filtro **continua vinculado**: a UI só marca/desmarca o que o usuário alterou.
- Alterações são locais até "Salvar vínculos". Ao salvar, o painel calcula a diferença e envia apenas `adicionarVinculo` (POST) e `removerVinculo` (DELETE); **não envia o conjunto inteiro**, para não desvincular material fora da página/filtro.
- Falha em uma operação da diferença: refetch de vínculos e da página, aviso com os títulos que falharam, seleção restante preservada.
- Indicador de "alterações não salvas" e confirmação ao sair com mudanças pendentes.
- Estado vazio de materiais: "Nenhum material cadastrado" + link para gerar.
- Voltar preserva a página/filtros da lista via query na URL.

### 7.4 Área do aluno

`AlunoShell`: header enxuto com logo → `/`, nome do aluno, "Trocar aluno", "Ver tour", `SkinSwitcher` e link "Área da empresa". Sem nav de geração.

**Identificação** (`/aluno`):

- Se `localStorage['novamente.aluno']` contém `{ aluno_id, nome }` válido, pula a identificação.
- Sem identificação: cartão com título "Quem está estudando?", busca por nome, lista de alunos ativos e botão "Entrar".
- Sem alunos ativos: mensagem "Nenhum aluno cadastrado. Peça à empresa para cadastrar." e link para `/empresa/alunos`.
- Ao entrar, grava `novamente.aluno` e recarrega o catálogo.
- Se o backend responder 404 `ALUNO_NAO_ENCONTRADO` ou 403 `ALUNO_INATIVO`, limpa o localStorage e volta à identificação com aviso.
- A tela não expõe e-mail.
- Aviso visível e discreto: "Identificação sem senha nesta versão." Não é authentication; não usar dado real.

**Catálogo** (`/aluno` após identificação):

- Saudação com o nome do aluno.
- Grade de cards com título, documento, badge de formato/perfil, tempo estimado, até 6 conceitos-chave e CTA "Estudar".
- Busca com debounce, filtro de formato e paginação; URL sincronizada.
- Estados: skeleton, vazio ("Nenhum material disponível ainda."), erro com retry.
- Não mostra rascunhos, não mostra materiais de outros alunos e não oferece geração.

**Visualização** (`/aluno/materiais/[id]`):

- Cabeçalho: voltar ao catálogo, título, badges de formato/perfil/nível, tempo estimado.
- Corpo: `ContentRenderer` reutilizado (`FlashcardDeck`, `InteractiveQuiz`, `MarkdownView`).
- Sem `OCIPanel`, sem exportação, sem download e sem CTA de geração.
- Quiz e flashcards mantêm o comportamento atual; progresso de quiz não é persistido.
- 404 `MATERIAL_NAO_DISPONIVEL` mostra "Este material não está disponível." com link para o catálogo.
- Se o material for despublicado enquanto a página está aberta, um novo carregamento leva ao estado 404.

### 7.5 Estado e dados no cliente

| Estado | Ferramenta | Chaves |
|---|---|---|
| Lista de alunos | TanStack Query | `['alunos', filtros]` |
| Aluno | TanStack Query | `['aluno', alunoId]` |
| Vínculos | TanStack Query | `['vinculos', alunoId]` |
| Materiais (empresa) | TanStack Query | `['materiais', filtros]` |
| Material (empresa) | TanStack Query | `['material', materialId]` |
| Identificação/catálogo do aluno | TanStack Query | `['aluno-identificacao']`, `['aluno-catalogo', alunoId, filtros]` |
| Material do aluno | TanStack Query | `['aluno-material', alunoId, materialId]` |
| Identidade do aluno | `localStorage` | `novamente.aluno` |
| Tour | `localStorage` | `novamente.tour` |
| Formulários | react-hook-form + zod | — |

Invalidações:

- Mutação de aluno invalida `['alunos']` e `['aluno', id]`.
- Mutação de vínculo invalida `['vinculos', alunoId]`, `['aluno', alunoId]` e `['alunos']`.
- Publicar/despublicar invalida `['materiais']`, `['material', id]` e `['aluno-catalogo']`.
- Excluir material invalida `['materiais']`, `['material', id]` e `['vinculos']` do aluno afetado.

### 7.6 Serviço

`NovaMenteApi` ganha:

```ts
listarAlunos(params?: ListarAlunosParams): Promise<PaginaAlunos>;
criarAluno(input: AlunoCriacao): Promise<AlunoResumo>;
obterAluno(alunoId: string): Promise<AlunoResumo>;
atualizarAluno(alunoId: string, input: AlunoAtualizacao): Promise<AlunoResumo>;
excluirAluno(alunoId: string): Promise<void>;
listarVinculos(alunoId: string): Promise<VinculosAluno>;
substituirVinculos(alunoId: string, input: AtualizarVinculosInput): Promise<VinculosAluno>; // lote; o painel não usa
adicionarVinculo(alunoId: string, materialId: string): Promise<void>;
removerVinculo(alunoId: string, materialId: string): Promise<void>;

listarMateriais(params?: ListarMateriaisParams): Promise<PaginaMateriais>;
obterMaterial(materialId: string): Promise<MaterialDetalhe>;
atualizarMaterial(materialId: string, input: MaterialAtualizacao): Promise<MaterialResumo>;
excluirMaterial(materialId: string): Promise<RemocaoMaterialResposta>;

listarIdentificacaoAluno(): Promise<IdentificacaoAlunoItem[]>;
listarCatalogoAluno(alunoId: string, params?: ListarCatalogoParams): Promise<PaginaCatalogoAluno>;
obterMaterialAluno(alunoId: string, materialId: string): Promise<MaterialDetalhe>;
```

Novas URLs em `endpoints.ts`:

```ts
alunos, aluno(id), alunoMateriais(id), alunoMaterial(id, materialId),
materiais, material(id), materialAlunos? (não usado nesta fase),
alunoIdentificacao, alunoCatalogo, alunoMaterialDetalhe(materialId)
```

---

## 8. Acessibilidade e performance

### Acessibilidade

- axe sem violação crítica em `/`, `/empresa/materiais`, `/empresa/alunos`, `/aluno` e `/aluno/materiais/[id]`.
- Formulários com `<label>` associado, `aria-invalid`, `aria-describedby` e resumo de erros.
- Diálogos com foco preso, `Esc` para fechar e retorno de foco ao gatilho.
- Checkboxes de vínculo com rótulo acessível e estado "não salvo" anunciado.
- Toasts com `role="status"`; erros com `role="alert"`.
- Tour com foco preso, teclado, `Esc` e anúncio de passo.
- Alvos de toque ≥ 44×44 px; contraste AA nas duas skins.
- `prefers-reduced-motion` remove transições do tour, do flip e das animações da landing.

### Performance

| Meta | Alvo |
|---|---|
| LCP da landing (local) | < 2,5 s |
| CLS | 0 |
| JS inicial da landing (gzip) | < 180 kB, sem driver.js e sem renderizadores |
| JS inicial de `/empresa` e `/aluno` | < 250 kB, mantendo a meta da spec anterior |
| Tour | carregado sob demanda |

Regras:

- `driver.js` por `import()` dinâmico.
- `FlashcardDeck`, `InteractiveQuiz` e `MarkdownView` continuam via `next/dynamic`.
- Landing sem TanStack Query para dados; o provider global pode permanecer.
- Sem imagens pesadas; usar CSS e ícones `lucide-react`.

---

## 9. Testes

### Backend (pytest)

Arquivos novos:

- `tests/test_alunos.py` — create/list/get/patch/delete, validação de nome/e-mail, normalização, 409 case-insensitive, 404, paginação, filtros, ordenação.
- `tests/test_materiais.py` — material criado pelo job como rascunho, listagem, filtros, PATCH de título/visibilidade, campos imutáveis rejeitados, DELETE com e sem OCI configurado, cascata de vínculos, 404, pacote corrompido → 500 no detalhe. A listagem e o catálogo do aluno **continuam funcionando** com `pacote_json` corrompido, porque não o desserializam.
- `tests/test_vinculos.py` — GET/PUT/POST/DELETE, substituição atômica do PUT, idempotência, ids inválidos sem alteração parcial, cascata nos dois lados, e garantia de que POST/DELETE parciais não afetam vínculos fora da página/filtro.
- `tests/test_aluno_catalogo.py` — identificação só ativos e sem e-mail; catálogo só publicado + vinculado; 403 inativo; 404 `MATERIAL_NAO_DISPONIVEL` para rascunho/não vinculado/inexistente; filtros e paginação.
- `tests/test_repositorio_sqlite.py` — `salvar_pacote` idempotente, `obter/listar` após "reinício" (nova sessão), compatibilidade de `/adaptacoes`.
- Fixture de banco isolado por teste (`sqlite://` em arquivo temporário ou memória com `StaticPool`), `create_all`/`drop_all` e `DATABASE_URL` sobrescrito.

Os testes existentes de contrato continuam passando.

### Frontend (Vitest + MSW)

Handlers novos replicam todas as rotas e erros (`404`, `403`, `409`, `422`).

Fixtures:

- `alunos.json` — 6 alunos, um inativo.
- `materiais.json` — 6 materiais, misturando rascunho e publicado, todos os formatos.
- Vínculos derivados em memória pelos handlers.

Testes:

- `MateriaisView` — carregando, vazio, erro, filtros, editar, publicar/despublicar, excluir com aviso de OCI.
- `AlunosView` — carregando, vazio, criar, editar, excluir, 409 no e-mail.
- `AlunoDetalheView`/`VinculosPanel` — seleção, estado "não salvo", salvar por diferença, filtro que esconde um vínculo sem desvinculá-lo, falha parcial com refetch, vazio.
- `IdentificacaoAluno` — lista, entrada, persistência, troca, 403/404 limpam sessão.
- `CatalogoAlunoView` — só itens retornados pelo servidor, filtros, vazio, erro.
- `AlunoMaterialView` — renderiza os quatro formatos e nega OCI/exportação.
- `useTour` — auto-start uma vez em `/empresa/gerar`, subconjunto correto por origem (landing 1–8, empresa 3–8, aluno 8), `?tour=1` completo, persistência, passo pulado quando o alvo não existe, `Esc`.
- Landing — seções obrigatórias, CTAs com href correto, metadata, ausência de promessas fora do MVP.

### E2E (Playwright + axe)

1. Landing → "Área da empresa" → gerar (mock) → resultado → exportar.
2. Empresa → materiais → publicar rascunho → alunos → criar aluno → vincular material → `/aluno` → identificar → abrir material → responder quiz.
3. Aluno não vê material não vinculado nem rascunho, mesmo digitando a URL.
4. Tour completo a partir do header e auto-start uma única vez.
5. axe em `/`, `/empresa/materiais`, `/empresa/alunos`, `/aluno`, `/aluno/materiais/[id]`.

---

## 10. Fases de entrega

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 0 | Landing, route groups, `EmpresaShell`/`AlunoShell`, redirects, nav nova | `/` renderiza a landing; rotas antigas redirecionam; fluxo atual de geração funciona em `/empresa/gerar` |
| 1 | SQLite, `core/db.py`, modelos DB, `repositorio` durável, material automático como rascunho | Reiniciar o backend preserva materiais; `/adaptacoes` continua igual; testes de repositório verdes |
| 2 | CRUD de materiais (API + tela `/empresa/materiais`), resultado lendo `GET /materiais/{id}`, publicar/despublicar/excluir | CRUD completo em tela e API; "C" via geração documentado e testado; resultado mostra título/visibilidade do catálogo |
| 3 | CRUD de alunos, detalhe e vínculos (API + telas) | Criar/editar/excluir aluno e substituir vínculos de forma atômica |
| 4 | Área do aluno: identificação, catálogo, visualização | Aluno vê só publicado + vinculado; renderizadores funcionam; 403/404 tratados |
| 5 | Tour, acessibilidade, performance, mocks/fixtures completos | Tour repetível e auto-start único; axe limpo; metas de performance |
| 6 | E2E, README, revisão final | `npm run verificar` e pytest verdes; documentação atualizada |

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Identificação sem senha permitir escolher qualquer aluno | Alto para dados reais; baixo para demo | Aviso explícito, sem e-mail na lista, nenhum dado real até a auth entrar |
| SQLite em produção com múltiplos workers | Médio | WAL, uma instância/UM worker nesta fase; documentar limite |
| Concorrência entre job e CRUD | Médio | Inserção idempotente por `adaptacao_id`, transações curtas |
| Exclusão no OCI falhar | Baixo | Resposta informa `oci_removido` e `aviso`; metadados continuam fonte |
| Pacote JSON corrompido impedir a tela | Médio | Listagem não desserializa; detalhe retorna 500 com `request_id` |
| Tour quebrar com mudança de layout | Médio | Seletores `data-tour` estáveis, passo pulado se o alvo não existir, teste de fumaça |
| Redirect permanente atrapalhar rollback | Baixo | Redirects em `next.config.ts`, reversíveis em um commit |
| Landing prometer recurso fora do MVP | Médio | Copy revisada contra a seção 3 e a spec anterior |
| Duplicidade de título de material confundir aluno | Baixo | Título + documento + badges no card; sem unicidade obrigatória |

---

## 12. Critérios de sucesso e definição de pronto

- Landing em `/` com todas as seções, CTAs funcionais e conteúdo fiel à proposta.
- `/empresa/*` contém o fluxo atual completo e as telas de Materiais e Alunos.
- CRUD de alunos completo: criar, listar, ler, editar, excluir.
- CRUD de materiais completo: criar pela geração, listar, ler, editar metadados/visibilidade, excluir.
- CRUD de vínculos completo: listar, adicionar, remover e substituir o conjunto.
- Aluno acessa somente materiais `publicado` vinculados a ele; rascunho e material de outro aluno retornam 404 mesmo por URL direta.
- Tour executa nas telas reais, pode ser repetido, pula alvos ausentes e não inicia sozinho na área do aluno.
- Rotas antigas redirecionam sem quebrar links.
- `pytest`, `npm run typecheck`, `npm run lint`, `npm run test:coverage`, `npm run build` e `npm run e2e` verdes.
- axe sem violação crítica nas rotas novas.
- Nenhuma tela em branco nos estados carregando, vazio, erro, degradado e sem permissão.
- README do backend e do frontend atualizados com banco, rotas novas, tour e fluxo empresa × aluno.
- Nenhum código de autenticação, token ou sessão nesta entrega.

---

## 13. Divergências em relação às fontes

| Ponto | Spec de 2026-10-21 / proposta | Esta spec | Motivo |
|---|---|---|---|
| `/` | Tela de geração | Landing pública; geração em `/empresa/gerar` | Pedido de landing + separação empresa × aluno |
| Auth | Fora do MVP | Continua fora; identificação leve e `owner_id` reservado | Decisão do produto nesta fase |
| Persistência | Memória; pacotes somem no reinício | SQLite durável; OCI para artefatos | CRUD e catálogo do aluno exigem fonte durável |
| Conteúdo do pacote | Imutável | Mantido imutável; só título/visibilidade editáveis | Preserva ancoragem e exportação |
| Perfis de acesso | Sem usuários | Dois públicos na UI, sem autenticação | Separação de experiência sem login |
| Tour | Não previsto | `driver.js` nas telas reais | Pedido do produto |
| Exportação do aluno | Exportação para todos | Somente empresa exporta | Área do aluno é de estudo |
| Rotas antigas | `/historico`, `/resultado/[id]` | Redirecionam para `/empresa/*` | Preservar links |
