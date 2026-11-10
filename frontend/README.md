# NovaMente — Frontend

Interface Next.js do NovaMente: transforma documentação técnica em flashcards, quizzes, tutoriais e resumos executivos ancorados na fonte, com persistência no OCI Object Storage.

## Como rodar com mocks

```bash
npm install
$env:NEXT_PUBLIC_API_MOCK=1   # PowerShell
npm run dev
```

> Na raiz do monorepo, `make dev-frontend` sobe o servidor (equivalente a `npm run dev`).
> Também há `make test-frontend`, `make typecheck`, `make lint`, `make build` e `make e2e`.
> Veja o [README principal](../README.md#atalhos-com-make-recomendado) para os demais atalhos.

Abra http://localhost:3000. O MSW intercepta `/api/v1/*` e simula todo o pipeline, incluindo erros.

O worker do MSW é servido de `public/mockServiceWorker.js`; se ele for apagado, `npm install`
o recria (configuração `msw.workerDirectory` no `package.json`). A variável é inlinada no bundle
de desenvolvimento (`process.env.NEXT_PUBLIC_API_MOCK`), então **trocar de mock para backend real
exige reiniciar o `next dev`** — e, em produção, refazer o `npm run build`.

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

- `src/app` — rotas do App Router:
  - `/` — landing pública;
  - `/empresa/gerar`, `/empresa/historico`, `/empresa/resultado/[id]` — geração e histórico;
  - `/empresa/materiais` — catálogo administrativo;
  - `/empresa/alunos`, `/empresa/alunos/[id]` — alunos e vínculos;
  - `/aluno`, `/aluno/materiais/[id]` — identificação, catálogo e leitura do aluno.
- `src/components/ui` — átomos e primitivos (shadcn)
- `src/components/landing` — seções da landing pública
- `src/components/layout` — shells, headers, banner de saúde, troca de skin e `TourLauncher`
- `src/components/views` — visualizadores e páginas client
- `src/components/forms` — formulário de ingestão e cenários
- `src/components/materiais` — catálogo, edição e exclusão de materiais
- `src/components/alunos` — lista, formulário, detalhe e painel de vínculos
- `src/components/aluno` — identificação, catálogo e material do aluno
- `src/features` — hooks de fluxo (formulário, job, histórico, materiais, alunos, aluno, exportação, OCI, saúde e tour)
- `src/services/api` — `NovaMenteApi`, cliente HTTP e normalização de erros
- `src/mocks` — handlers MSW, estado em memória e fixtures validadas por zod
- `src/types` — schemas zod e tipos do contrato
- `src/themes` — tokens e skins `violeta` e `ciano`
- `e2e` — cenários de geração, histórico, landing/empresa, aluno, tour, responsividade e acessibilidade com axe

## Tour guiado

- `driver.js` é carregado por import dinâmico em `src/features/tour/driver.ts`; a lib e o CSS não entram no bundle inicial.
- São 8 passos sobre as telas reais. O subconjunto depende da origem: landing (1–8), empresa (3–8), aluno (8) e `?tour=1` (1–8).
- O tour auto-inicia **uma vez** em `/empresa/gerar`, após 600 ms, se `localStorage['novamente.tour']` não existir ou tiver versão antiga.
- "Ver tour" sempre reinicia; `Esc`/fechar gravam a conclusão em `novamente.tour = { versao: 1, concluido_em }`.
- Passos sem alvo no DOM são pulados após 2.500 ms.

## Decisões que valem saber

- Base HTTP é sempre relativa (`/api/v1`). Não existe `NEXT_PUBLIC_API_URL`.
- O mock é de rede (MSW), não de serviço: o mesmo `httpApiClient` roda em dev, teste, Storybook e produção.
- Toda resposta de pacote passa por `AdaptacaoPacoteSchema.parse`; contrato divergente vira um
  estado de erro com `role="alert"` (mensagem legível, botão de tentar de novo), nunca tela branca.
- Jobs são assíncronos com polling de 1,5 s (3 s após 60 s) e timeout de 5 min.
- FlashcardDeck, InteractiveQuiz e MarkdownView entram por `next/dynamic` no `ContentRenderer`,
  então react-markdown/remark/rehype e framer-motion ficam fora da primeira carga de `/`.
- O formulário usa react-hook-form + zod; `src/types/schemas.ts` é a fonte única do contrato e
  também valida as fixtures usadas pelo mock.

## Performance (medido em 22/10/2026)

Medição local, build de produção (`npm run build` + `npm run start`), Chromium headless via
Playwright, sem Lighthouse (não é dependência do projeto).

| Rota | CLS 1280×720 | CLS 390×844 | LCP 1280×720 |
|---|---|---|---|
| `/` | 0 | 0 | 500 ms |
| `/historico` | 0 | 0 | 532 ms |
| `/resultado/01JAVCNFLCARD00000000001` | 0 | 0 | 892 ms |

- O LCP das três rotas foi medido no build com `NEXT_PUBLIC_API_MOCK=1` (o mock é embutido no
  build), com o worker do MSW no caminho crítico; sem mock o valor tende a ser menor. Também
  medimos com rede limitada a 150 kB/s (o esqueleto fica visível por ~4 s): CLS continuou 0.
- CLS 0 foi obtido reservando no esqueleto de `/resultado` as mesmas tags, classes e alturas do
  conteúdo final: título (32 px), introdução de duas linhas (`min-h-12`), área das ações
  (Exportar/JSON/Nova geração, que quebram em duas linhas no mobile) e o grid. Trocar esqueleto
  por pacote não desloca nenhum elemento.
- **First Load JS de `/`: 230,8 kB gzip** (749,9 kB sem compressão; 226,1 kB de transferência
  real). O Next declara 12 chunks de módulo para a rota; o polyfill `noModule`
  (`0cz1d0…js`) é declarado à parte, o Chromium não o baixa e ele **não** entra na conta.
  A meta original do design (< 180 kB) foi **revista para < 250 kB gzip**: dos 230,8 kB,
  128,3 kB são a base do framework (react-dom e runtime do Next 16/Turbopack) e o restante são
  dependências exigidas ou escolhidas na stack — zod 34 kB e TanStack Query 12 kB (exigidas
  pela spec; dados client-side e contrato validado no cliente), react-hook-form 11 kB e
  tailwind-merge 8 kB (escolhas de implementação) — mais o código do app. Com 128 kB de base
  do framework, 180 kB deixaria ~50 kB para todo o resto, o que não paga essas dependências.

### Como reproduzir a medição de CLS/LCP

```powershell
# 1. build de medição com o mock embutido e servidor de produção
$env:NEXT_PUBLIC_API_MOCK=1; npm run build
npm run start -- -p 3100
```

```js
// 2. medir.js — Playwright já é dependência de desenvolvimento
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 720 } })).newPage();
  await page.addInitScript(() => {
    window.m = { lcp: 0, cls: 0 };
    new PerformanceObserver((l) => { for (const e of l.getEntries()) window.m.lcp = e.startTime; })
      .observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) { if (!e.hadRecentInput) window.m.cls += e.value; } })
      .observe({ type: 'layout-shift', buffered: true });
  });
  await page.goto('http://localhost:3100/resultado/01JAVCNFLCARD00000000001', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  console.log(await page.evaluate(() => window.m)); // { lcp: …, cls: 0 }
  await browser.close();
})();
```

```powershell
node medir.js   # repetir trocando a rota e o viewport (390×844 para mobile)
```

Equivalente com Lighthouse (não instalado aqui; exige `npx lighthouse`, baixa na hora):
`npx lighthouse http://localhost:3100/ --preset=desktop --only-categories=performance --chrome-flags="--headless"`.

Cobertura de `src/features/**` + `src/services/**`: 90,4% statements, 82,1% branches,
95,1% functions, 94,2% lines (limiares do `vitest.config.mts`: 80/70/80/80).

## Testes E2E (Playwright)

Os testes cobrem os cenários de geração, upload, histórico, landing, área da empresa, área do aluno, tour, responsividade e acessibilidade (axe), rodando com o mock de API no browser (`NEXT_PUBLIC_API_MOCK=1`).

```bash
npx playwright install chromium   # uma vez por máquina
npm run e2e                       # sobe o next dev e roda os 16 testes
npm run e2e -- 6-landing          # filtra por arquivo
```

| Arquivo | Cobertura |
|---|---|
| `1-gerar-flashcards.spec.ts` | Geração, virar cartão e exportar Markdown/CSV |
| `2-upload-quiz.spec.ts` | Upload de Markdown, quiz e placar |
| `3-historico-exportacao.spec.ts` | Histórico, download JSON e CSV indisponível |
| `4-acessibilidade.spec.ts` | axe sem violação crítica nas rotas principais |
| `5-responsivo.spec.ts` | Sem rolagem horizontal em 375 px e 320 px |
| `6-landing-empresa.spec.ts` | Landing, geração, publicação, edição, aluno, vínculo e exclusão |
| `7-aluno-catalogo.spec.ts` | Identificação, catálogo, quiz, 404 unificado e troca de aluno |
| `8-tour.spec.ts` | Auto-start, persistência, reinício e `?tour=1` |

- `playwright.config.ts` usa `workers: 1` e nunca reaproveita um servidor já no ar
  (`reuseExistingServer: false`), para não rodar contra o FastAPI real por acidente.
  Pare qualquer `next dev` na porta 3000 antes de rodar.
- Cada teste abre um contexto de browser novo; o estado do mock (jobs, pacotes,
  alunos e vínculos) vive na memória da página, então recarregar a página reseta
  o estado para as fixtures semeadas. A navegação entre telas é feita por links
  para preservar o que foi gerado na mesma sessão.
- Os specs que não testam o tour gravam `novamente.tour` via `addInitScript`
  para impedir que o auto-start cubra a tela durante o fluxo.
- Reporter `list` no terminal e relatório HTML em `playwright-report/` (`open: 'never'`, não abre
  sozinho); traces de retry ficam em `test-results/`. Ambos são ignorados pelo git.

## Notas de manutenção

- `vitest.config.mts` exclui `e2e/**`: os specs do Playwright casam com o include padrão do
  Vitest e usam outro runner.
- `storybook-static/`, `.next/`, `coverage/`, `playwright-report/` e `test-results/` são
  artefatos de build e ficam fora do git.
