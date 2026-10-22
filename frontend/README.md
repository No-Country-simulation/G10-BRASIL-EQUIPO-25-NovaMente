# NovaMente — Frontend

Interface Next.js do NovaMente: transforma documentação técnica em flashcards, quizzes, tutoriais e resumos executivos ancorados na fonte, com persistência no OCI Object Storage.

## Como rodar com mocks

```bash
npm install
$env:NEXT_PUBLIC_API_MOCK=1   # PowerShell
npm run dev
```

Abra http://localhost:3000. O MSW intercepta `/api/v1/*` e simula todo o pipeline, incluindo erros.

O worker do MSW é servido de `public/mockServiceWorker.js`; se ele for apagado, `npm install`
o recria (configuração `msw.workerDirectory` no `package.json`). A variável é lida em tempo de
build (`process.env.NEXT_PUBLIC_API_MOCK`), então **trocar de mock para backend real exige
rebuildar** (`npm run build`) — em `npm run dev` o valor entra na próxima compilação.

## Como apontar para o backend real

Sem `NEXT_PUBLIC_API_MOCK`, o Next faz rewrite de `/api/v1/*` para `API_BASE_URL` (padrão `http://localhost:8000`):

```bash
$env:API_BASE_URL='http://localhost:8000'
npm run dev
```

O rewrite acontece no servidor do Next; o browser sempre chama caminho relativo. O contrato
consumido está em `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md` (seções 5 e 6).
O backend deve implementá-lo à risca: os handlers do MSW são o contrato executável.

## Scripts

| Comando | Função |
|---|---|
| `npm run dev` | Servidor de desenvolvimento |
| `npm run build` | Build de produção |
| `npm run start` | Servidor do build de produção |
| `npm run typecheck` | TypeScript sem emitir |
| `npm run lint` | ESLint |
| `npm test` | Vitest |
| `npm run test:coverage` | Vitest com cobertura |
| `npm run storybook` | Catálogo de componentes |
| `npm run e2e` | Playwright |
| `npm run verificar` | Pipeline completo do DoD |

`npm run verificar` roda, em sequência e sem intervenção: `typecheck` → `lint` →
`test:coverage` → `build` → `e2e`. Ele exige a porta 3000 livre (o Playwright não reaproveita
servidor) e o Chromium do Playwright instalado uma vez com `npx playwright install chromium`.

## Estrutura

- `src/app` — rotas do App Router (`/`, `/historico`, `/resultado/[id]`), layout, providers
- `src/components/ui` — átomos e primitivos (shadcn)
- `src/components/layout` — shell, header, banner de saúde, troca de skin
- `src/components/views` — visualizadores e páginas client
- `src/components/forms` — formulário de ingestão e cenários
- `src/features` — hooks de fluxo (formulário, job, histórico, exportação, OCI, saúde)
- `src/services/api` — `NovaMenteApi`, cliente HTTP e normalização de erros
- `src/mocks` — handlers MSW e fixtures validadas por zod
- `src/types` — schemas zod e tipos do contrato
- `src/themes` — tokens e skins `violeta` e `ciano`
- `e2e` — os três cenários do edital e a checagem de acessibilidade com axe

## Decisões que valem saber

- Base HTTP é sempre relativa (`/api/v1`). Não existe `NEXT_PUBLIC_API_URL`.
- O mock é de rede (MSW), não de serviço: o mesmo `httpApiClient` roda em dev, teste, Storybook e produção.
- Toda resposta de pacote passa por `AdaptacaoPacoteSchema.parse`; contrato divergente vira `ErrorState`, nunca tela branca.
- Jobs são assíncronos com polling de 1,5 s (3 s após 60 s) e timeout de 5 min.
- FlashcardDeck, InteractiveQuiz e MarkdownView entram por `next/dynamic` no `ContentRenderer`,
  então react-markdown/remark/rehype e framer-motion ficam fora da primeira carga de `/`.
- O formulário usa react-hook-form + zod; `src/types/schemas.ts` é a fonte única do contrato e
  também valida as fixtures usadas pelo mock.

## Performance (medido em 22/10/2026)

Medição local, build de produção (`npm run build` + `npm run start`), Chromium headless via
Playwright, sem Lighthouse (não é dependência do projeto).

| Rota | CLS | LCP |
|---|---|---|
| `/` | 0 | 500 ms |
| `/historico` | 0 | 532 ms |
| `/resultado/01JAVCNFLCARD00000000001` | 0 | 884 ms |

- O LCP das três rotas foi medido no build com `NEXT_PUBLIC_API_MOCK=1` (o mock é embutido no
  build), com o worker do MSW no caminho crítico; sem mock o valor tende a ser menor.
- CLS 0 foi obtido reservando no esqueleto de `/resultado` as mesmas tags, classes e alturas do
  conteúdo final: trocar esqueleto por pacote não desloca nenhum elemento.
- **First Load JS de `/`: 230,8 kB (gzip, 13 chunks de primeira carga; 749,9 kB sem compressão).**
  A meta do design era < 180 kB. Desse total, 128,3 kB são a base do framework (react-dom e
  runtime do Next 16/Turbopack) e o restante são dependências exigidas pela spec — zod 34 kB,
  TanStack Query 12 kB, react-hook-form 11 kB, tailwind-merge 8 kB — mais o código do app.
  Para caber em 180 kB seria preciso abrir mão de ~50 kB de dependências obrigatórias; o número
  fica registrado como desvio consciente.

Cobertura de `src/features/**` + `src/services/**`: 90,4% statements, 82,1% branches,
95,1% functions, 94,2% lines (limiares do `vitest.config.ts`: 80/70/80/80).

## Testes E2E (Playwright)

Os testes cobrem os três cenários do edital e a acessibilidade (axe) das rotas principais,
rodando com o mock de API no browser (NEXT_PUBLIC_API_MOCK=1).

```bash
npx playwright install chromium   # uma vez por máquina
npm run e2e                       # sobe o next dev e roda os 6 testes
npm run e2e -- 3-historico        # filtra por arquivo
```

- `playwright.config.ts` usa `workers: 1` e nunca reaproveita um servidor já no ar
  (`reuseExistingServer: false`), para não rodar contra o FastAPI real por acidente.
  Pare qualquer `next dev` na porta 3000 antes de rodar.
- Cada teste abre um contexto de browser novo; o estado do mock (jobs e pacotes) vive na
  memória da página, então recarregar a página reseta o histórico para a fixture semeada.
- Reporter `list` no terminal e relatório HTML em `playwright-report/` (`open: 'never'`, não abre
  sozinho); traces de retry ficam em `test-results/`. Ambos são ignorados pelo git.

## Notas de manutenção

- `vitest.config.ts` exclui `e2e/**`: os specs do Playwright casam com o include padrão do
  Vitest e usam outro runner.
- `storybook-static/`, `.next/`, `coverage/`, `playwright-report/` e `test-results/` são
  artefatos de build e ficam fora do git.
