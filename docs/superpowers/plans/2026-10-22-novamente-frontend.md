# NovaMente Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a interface Next.js do NovaMente que gera, visualiza, reabre e exporta materiais didáticos adaptados a partir de documentação técnica, operando por completo contra mocks e pronta para o FastAPI.

**Architecture:** Next.js App Router com shells em Server Component e dados sempre client-side via TanStack Query. As camadas são UI → hook → `NovaMenteApi` → `fetch('/api/v1/...')`, com MSW interceptando a rede em dev, teste e Storybook. Renderização de conteúdo usa um registry por `tipo` (Strategy/OCP) e cada visualizador recebe só o recorte de dados que usa (ISP).

**Tech Stack:** Next.js (App Router, TS estrito), Tailwind CSS, shadcn/ui, TanStack Query, Zustand, react-hook-form + zod, framer-motion, react-markdown, MSW, Vitest + Testing Library, Storybook, Playwright + axe.

**Spec:** `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md`

## Global Constraints

- O app vive em `frontend/`; o backend futuro em `backend/`. Todos os caminhos deste plano são relativos a `frontend/` salvo indicação contrária.
- Base HTTP: `/api/v1`, sempre caminho relativo. Sem `NEXT_PUBLIC_API_URL`. Rewrites do Next apontam para `API_BASE_URL ?? http://localhost:8000`.
- Sem autenticação. Histórico global.
- Formatos de saída: `Flashcards`, `Quiz`, `Tutorial`, `ResumoExecutivo`. Roteiro de Aula não existe.
- Perfis: `Iniciante`, `Desenvolvedor`, `LiderTecnico`, `Gestor`. Nichos: `Fintech`, `Saude`, `Ecommerce`, `Geral`. Níveis: `Didatico`, `Tecnico`, `Executivo`.
- Limites: título 3–150 caracteres; texto 200–50.000; arquivo ≤ 10.485.760 bytes; extensões `.pdf`, `.md`, `.txt`; página de histórico 12 por padrão, máximo 50.
- Polling do job: 1.500 ms, 3.000 ms após 60 s, timeout de 5 min, sem polling em aba oculta, progresso monotônico.
- Skins: `violeta` (default) e `ciano`, via `data-skin` no `<html>` e chave `novamente.skin` no localStorage.
- Toda string de UI em pt-BR e em `src/lib/mensagens.ts`. Nenhum texto solto em componente.
- Cobertura mínima: 80% de linhas e 80% de funções em `src/features/**` e `src/services/**`; branches 70%.
- axe sem violação crítica nas três rotas; `prefers-reduced-motion` remove o flip dos flashcards.
- Nenhum componente importa `fetch`; nenhum teste usa `mockApiClient` (mock é de rede, via MSW).

## Review Focus

1. **Título com acentos, emoji, quebras de linha ou 200 caracteres** — deve virar um slug ASCII estável e um nome de arquivo válido em `Content-Disposition`, sem `%` cru nem caractere de controle.
2. **Arquivo com extensão válida e conteúdo ilegível** (PDF protegido, binário renomeado para `.md`) — deve virar erro no campo do arquivo, com a mensagem do servidor, e nunca travar o formulário.
3. **Job com progresso regressivo ou etapas fora de ordem** — a barra não pode voltar e uma etapa concluída não pode "desmarcar".
4. **Pacote cujo `conteudo_adaptado.tipo` não corresponde a `metadados.formato_gerado`** — deve produzir `ErrorState`, nunca tela branca ou crash de render.
5. **Texto colado no limite com emoji e acentos** (50.000 e 50.001 caracteres) — o contador e a validação devem concordar com o servidor, sem contar bytes no lugar de caracteres.

---

## File Structure

```
frontend/src/
  app/
    layout.tsx                      fontes, skin anti-flash, providers
    page.tsx                        shell de /
    resultado/[id]/page.tsx         shell de /resultado/[id]
    historico/page.tsx              shell de /historico
    providers.tsx                   QueryClient + ApiProvider + SkinProvider + MockProvider
  components/
    ui/                             shadcn (button, card, badge, skeleton, tabs, select,
                                    tooltip, progress, separator) + Dropzone
    forms/
      IngestionForm.tsx             composição do formulário
      campos/ParametrosFields.tsx   Perfil, Formato, Nicho, Nível (radio/select/segmented)
      campos/FonteDocumento.tsx     tabs texto/arquivo + textarea + dropzone
    views/
      ContentRenderer.tsx           registry por tipo (OCP)
      FlashcardCard.tsx             cartão 3D
      FlashcardDeck.tsx             navegação e flip
      InteractiveQuiz.tsx           quiz com feedback e revisão
      MarkdownView.tsx              markdown sanitizado
      OCIPanel.tsx                  score, clareza, bucket
      ScoreGauge.tsx                gauge acessível
      JobProgress.tsx               6 etapas + barra + falha
      ResultadoHeader.tsx           título, badges, exportação
      ResultadoView.tsx             página de resultado (client)
      ExportMenu.tsx                md/pdf/csv
      GerarView.tsx                 composição de / (client)
      HistoricoView.tsx             composição de /historico (client)
    layout/
      AppShell.tsx                  header + main
      Header.tsx                    nav e SkinSwitcher
      SkinSwitcher.tsx              troca de skin
      HealthBanner.tsx              banner de API degradada
  features/
    adaptations/{useAdaptationForm,useCreateAdaptation,useAdaptation,useAdaptationHistory,useExport}.ts
    jobs/useAdaptationJob.ts
    oci/useOciStatus.ts
    health/useHealth.ts
    theme/{useSkin,SkinProvider}.tsx
  services/api/
    NovaMenteApi.ts                 interface
    httpApiClient.ts                implementação fetch
    endpoints.ts                    URLs e query strings
    erros.ts                        ErroApi / ErroRede / mensagemDoErro
    ApiProvider.tsx                 injeção
    download.ts                     blob → arquivo
  types/{schemas,novamente,api}.ts
  mocks/
    browser.ts, server.ts, estadoJobs.ts, fixtures.test.ts
    handlers/{index,adaptacoes,jobs,oci,health}.ts
    fixtures/{flashcards,quiz,tutorial,resumo}-vcn-*.json
  themes/{tokens.css,registry.ts}
  lib/{cn,constants,mensagens,formatadores}.ts
  test/setup.ts
e2e/                                3 fluxos + a11y
.storybook/preview.ts
```

Arquivos que mudam juntos ficam juntos: todos os campos de parâmetro vivem em `ParametrosFields.tsx` (quatro componentes pequenos e coesos) e a fonte do documento em `FonteDocumento.tsx`, em vez de seis arquivos de 15 linhas.

### Task 1: Fundação do projeto e tooling

**Files:**
- Create: `frontend/` (create-next-app), `vitest.config.ts`, `src/test/setup.ts`, `src/lib/cn.ts`, `src/lib/utils.ts`, `src/app/providers.tsx`, `.env.example`
- Modify: `package.json`, `src/app/layout.tsx`, `src/app/page.tsx`
- Test: `src/lib/cn.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: `cn(...entradas: ClassValue[]): string`; `Providers`; scripts `test`, `test:coverage`, `typecheck`, `e2e`; Vitest configurado com `@/` → `src/`.

- [ ] **Step 1: Criar o projeto e instalar dependências**

No diretório raiz `D:\ArqProg\System_Folders\Desktop\NovaMente`:

```bash
git init
npx create-next-app@latest frontend --typescript --eslint --tailwind --app --src-dir --import-alias "@/*" --use-npm --yes
cd frontend
npm i @tanstack/react-query zustand react-hook-form @hookform/resolvers zod framer-motion lucide-react clsx tailwind-merge react-markdown remark-gfm rehype-sanitize
npm i -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom @vitest/coverage-v8 msw msw-storybook-addon @playwright/test @axe-core/playwright @tailwindcss/typography
npx shadcn@latest init -d -y
npx shadcn@latest add button card badge skeleton tabs select tooltip progress separator dropdown-menu
npx storybook@latest init --yes
npx playwright install chromium
```

Se o `create-next-app` perguntar algo além das flags, aceite o padrão. `git init` na raiz é necessário porque o diretório ainda não é um repositório; se você não quiser versionar, pule os passos de commit de todas as tasks.

- [ ] **Step 2: Configurar scripts e Vitest**

`package.json` (apenas o bloco `scripts`):

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "e2e": "playwright test",
    "storybook": "storybook dev -p 6006"
  }
}
```

`vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    coverage: {
      provider: 'v8',
      include: ['src/features/**/*.{ts,tsx}', 'src/services/**/*.{ts,tsx}'],
      thresholds: { lines: 80, statements: 80, functions: 80, branches: 70 },
    },
  },
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
});
```

`src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => cleanup());

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock);

// Node não resolve URL relativa; o app sempre chama caminho relativo.
const fetchOriginal = globalThis.fetch;
globalThis.fetch = ((entrada: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof entrada === 'string' && entrada.startsWith('/') ? `http://localhost${entrada}` : entrada;
  return fetchOriginal(url as RequestInfo, init);
}) as typeof fetch;
```

`.env.example`:

```
# Liga o worker do MSW no browser (dev, Storybook e E2E).
NEXT_PUBLIC_API_MOCK=1
# Destino dos rewrites /api/v1 (server-side).
API_BASE_URL=http://localhost:8000
```

Se o `.gitignore` do Next ignorar `.env*`, acrescente `!.env.example` para que o arquivo de exemplo entre no repositório.

- [ ] **Step 3: Escrever o teste que falha para `cn`**

`src/lib/cn.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
  it('resolve conflito de utilitários do Tailwind mantendo o último', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });

  it('ignora valores falsy', () => {
    expect(cn('text-sm', false, undefined, null)).toBe('text-sm');
  });
});
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `npm test -- src/lib/cn.test.ts`
Expected: FAIL — `Failed to resolve import "./cn"`.

- [ ] **Step 5: Implementar `cn` e o alias do shadcn**

`src/lib/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...entradas: ClassValue[]) {
  return twMerge(clsx(entradas));
}
```

`src/lib/utils.ts` (os componentes do shadcn importam `@/lib/utils`):

```ts
export { cn } from './cn';
```

- [ ] **Step 6: Rodar e ver passar**

Run: `npm test -- src/lib/cn.test.ts`
Expected: PASS (2 testes).

- [ ] **Step 7: Providers, layout e página mínima**

`src/app/providers.tsx`:

```tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 2, staleTime: 30_000, refetchOnWindowFocus: false },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

`src/app/layout.tsx`:

```tsx
import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Providers } from './providers';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

export const metadata: Metadata = {
  title: 'NovaMente — material didático a partir de documentação técnica',
  description: 'Gere flashcards, quizzes, tutoriais e resumos executivos ancorados na sua documentação.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" data-skin="violeta" className={`${inter.variable} ${mono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

`src/app/page.tsx`:

```tsx
export default function Home() {
  return <main className="p-8">NovaMente</main>;
}
```

`next.config.ts` (cria/ substitui):

```ts
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.API_BASE_URL ?? 'http://localhost:8000'}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 8: Verificar build e commit**

Run: `npm run typecheck && npm run build && npm test`
Expected: todos os comandos com exit 0.

```bash
git add frontend
git commit -m "chore(frontend): scaffold Next.js, Vitest, shadcn e Storybook"
```

---

### Task 2: Tokens, skins e casca da aplicação

**Files:**
- Create: `src/themes/tokens.css`, `src/themes/registry.ts`, `src/lib/mensagens.ts`, `src/features/theme/useSkin.ts`, `src/features/theme/SkinProvider.tsx`, `src/components/layout/SkinSwitcher.tsx`, `src/components/layout/Header.tsx`, `src/components/layout/AppShell.tsx`
- Modify: `src/app/globals.css`, `src/app/layout.tsx`, `src/app/page.tsx`
- Test: `src/components/layout/SkinSwitcher.test.tsx`

**Interfaces:**
- Consumes: `cn`.
- Produces: `SKINS`, `SkinId`, `useSkin()` (`{ skin, setSkin }`), `SkinProvider`, `AppShell`, `Header`, `SkinSwitcher`.

- [ ] **Step 1: Escrever o teste que falha**

`src/components/layout/SkinSwitcher.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { SkinProvider } from '@/features/theme/SkinProvider';
import { useSkin } from '@/features/theme/useSkin';
import { SkinSwitcher } from './SkinSwitcher';

describe('SkinSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
    useSkin.setState({ skin: 'violeta' });
    document.documentElement.dataset.skin = 'violeta';
  });

  it('aplica a skin no <html> e persiste no localStorage', async () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: /ciano/i }));

    expect(document.documentElement.dataset.skin).toBe('ciano');
    expect(JSON.parse(localStorage.getItem('novamente.skin')!).state.skin).toBe('ciano');
  });

  it('anuncia a skin ativa com aria-pressed', async () => {
    render(
      <SkinProvider>
        <SkinSwitcher />
      </SkinProvider>,
    );

    expect(screen.getByRole('button', { name: /violeta/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /ciano/i })).toHaveAttribute('aria-pressed', 'false');
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/layout/SkinSwitcher.test.tsx`
Expected: FAIL — módulos `SkinProvider`, `useSkin` e `SkinSwitcher` não existem.

- [ ] **Step 3: Tokens e registry**

`src/themes/tokens.css`:

```css
:root,
[data-skin='violeta'] {
  --bg: #0b0d14;
  --surface: #12141d;
  --surface-elevated: #191c27;
  --border: #262a38;
  --border-strong: #343a4d;
  --fg: #e8eaf2;
  --fg-muted: #9aa1b5;
  --accent: #8b5cf6;
  --accent-fg: #0b0d14;
  --accent-muted: #2a2145;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #f87171;
  --ring: #a78bfa;
}

[data-skin='ciano'] {
  --bg: #0a0f14;
  --surface: #111820;
  --surface-elevated: #18212b;
  --border: #243140;
  --border-strong: #324154;
  --fg: #e6edf3;
  --fg-muted: #94a3b8;
  --accent: #22d3ee;
  --accent-fg: #04121a;
  --accent-muted: #0d2b33;
  --success: #34d399;
  --warning: #fbbf24;
  --danger: #fb7185;
  --ring: #67e8f9;
}
```

`src/themes/registry.ts`:

```ts
export const SKINS = {
  violeta: { id: 'violeta', nome: 'Violeta' },
  ciano: { id: 'ciano', nome: 'Ciano' },
} as const;

export type SkinId = keyof typeof SKINS;

export const SKIN_PADRAO: SkinId = 'violeta';
```

`src/lib/mensagens.ts` (versão inicial; a Task 3 substitui pelo arquivo completo):

```ts
export const M = {
  app: {
    nome: 'NovaMente',
    navGerar: 'Gerar',
    navHistorico: 'Histórico',
    navPrincipal: 'Principal',
    tema: 'Tema',
    emConstrucao: 'Em construção',
  },
  comum: {
    carregando: 'Carregando…',
    tentarNovamente: 'Tentar novamente',
    voltar: 'Voltar',
    erroTitulo: 'Algo deu errado',
    irParaConteudo: 'Ir para o conteúdo',
  },
} as const;
```

- [ ] **Step 4: Store, provider e switcher**

`src/features/theme/useSkin.ts`:

```ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { SKIN_PADRAO, type SkinId } from '@/themes/registry';

interface SkinState {
  skin: SkinId;
  setSkin: (skin: SkinId) => void;
}

export const useSkin = create<SkinState>()(
  persist(
    (set) => ({
      skin: SKIN_PADRAO,
      setSkin: (skin) => set({ skin }),
    }),
    { name: 'novamente.skin', version: 1 },
  ),
);
```

`src/features/theme/SkinProvider.tsx`:

```tsx
'use client';

import { useEffect } from 'react';
import { useSkin } from './useSkin';

export function SkinProvider({ children }: { children: React.ReactNode }) {
  const skin = useSkin((estado) => estado.skin);

  useEffect(() => {
    document.documentElement.dataset.skin = skin;
  }, [skin]);

  return <>{children}</>;
}
```

`src/components/layout/SkinSwitcher.tsx`:

```tsx
'use client';

import { useSkin } from '@/features/theme/useSkin';
import { SKINS, type SkinId } from '@/themes/registry';
import { cn } from '@/lib/cn';

export function SkinSwitcher() {
  const skin = useSkin((estado) => estado.skin);
  const setSkin = useSkin((estado) => estado.setSkin);

  return (
    <div role="group" aria-label="Tema" className="flex items-center gap-1 rounded-full border p-1">
      {(Object.keys(SKINS) as SkinId[]).map((id) => (
        <button
          key={id}
          type="button"
          aria-pressed={skin === id}
          onClick={() => setSkin(id)}
          className={cn(
            'rounded-full px-3 py-1 text-xs transition-colors',
            skin === id ? 'bg-[var(--accent)] text-[var(--accent-fg)]' : 'text-[var(--fg-muted)]',
          )}
        >
          {SKINS[id].nome}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm test -- src/components/layout/SkinSwitcher.test.tsx`
Expected: PASS (2 testes).

- [ ] **Step 6: Casca, layout com anti-flash e página**

`src/components/layout/Header.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { SkinSwitcher } from './SkinSwitcher';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';

const NAV = [
  { href: '/', rotulo: M.app.navGerar },
  { href: '/historico', rotulo: M.app.navHistorico },
];

export function Header() {
  const caminho = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="font-semibold tracking-tight">
            {M.app.nome}
          </Link>
          <nav aria-label="Principal" className="flex gap-1">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={caminho === item.href ? 'page' : undefined}
                className={cn(
                  'rounded-md px-3 py-2 text-sm',
                  caminho === item.href
                    ? 'bg-[var(--accent-muted)] text-[var(--fg)]'
                    : 'text-[var(--fg-muted)] hover:text-[var(--fg)]',
                )}
              >
                {item.rotulo}
              </Link>
            ))}
          </nav>
        </div>
        <SkinSwitcher />
      </div>
    </header>
  );
}
```

`src/components/layout/AppShell.tsx`:

```tsx
import { Header } from './Header';

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-[var(--bg)] text-[var(--fg)]">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--accent-fg)]"
      >
        Ir para o conteúdo
      </a>
      <Header />
      <main id="conteudo" className="mx-auto max-w-[1280px] px-4 py-8">
        {children}
      </main>
    </div>
  );
}
```

`src/app/globals.css` — **não substitua o arquivo inteiro**. O gerador atual usa `tw-animate-css`, `shadcn/tailwind.css` e `@custom-variant dark`, dos quais os componentes Radix dependem. Edite o arquivo:

1. mantenha os três `@import` iniciais e o `@custom-variant dark`;
2. acrescente `@plugin '@tailwindcss/typography';` e `@import '../themes/tokens.css';` logo após os imports;
3. **não** remova o bloco `@theme inline` existente; altere só a linha `--color-accent: var(--accent);` para `--color-accent: var(--accent-muted);`;
4. acrescente o bloco de alias abaixo **depois** do `@theme inline` — ele liga os nomes do shadcn aos nossos tokens, mantendo `--accent` como cor de marca e usando `--accent-muted` no hover;
5. acrescente o `@layer base` no fim.

```css
/* Aliases: shadcn/ui → tokens NovaMente */
:root,
.dark {
  --background: var(--bg);
  --foreground: var(--fg);
  --card: var(--surface);
  --card-foreground: var(--fg);
  --popover: var(--surface-elevated);
  --popover-foreground: var(--fg);
  --primary: var(--accent);
  --primary-foreground: var(--accent-fg);
  --secondary: var(--surface-elevated);
  --secondary-foreground: var(--fg);
  --muted: var(--surface-elevated);
  --muted-foreground: var(--fg-muted);
  --accent-foreground: var(--fg);
  --destructive: var(--danger);
  --input: var(--border);
  --radius: 0.75rem;
}

@layer base {
  body {
    background: var(--bg);
    color: var(--fg);
    font-family: var(--font-inter), system-ui, sans-serif;
  }

  :focus-visible {
    outline: 2px solid var(--ring);
    outline-offset: 2px;
  }
}
```

`src/app/layout.tsx` — substituir o `<html>` e envolver com `SkinProvider` e o script anti-flash:

```tsx
import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Providers } from './providers';
import { SkinProvider } from '@/features/theme/SkinProvider';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

export const metadata: Metadata = {
  title: 'NovaMente — material didático a partir de documentação técnica',
  description: 'Gere flashcards, quizzes, tutoriais e resumos executivos ancorados na sua documentação.',
};

const scriptSkin = `try{var b=localStorage.getItem('novamente.skin');var s=b?JSON.parse(b).state.skin:null;document.documentElement.dataset.skin=s==='ciano'?'ciano':'violeta'}catch(e){document.documentElement.dataset.skin='violeta'}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: scriptSkin }} />
      </head>
      <body>
        <Providers>
          <SkinProvider>{children}</SkinProvider>
        </Providers>
      </body>
    </html>
  );
}
```

`src/app/page.tsx`:

```tsx
import { AppShell } from '@/components/layout/AppShell';

export default function Home() {
  return <AppShell>Em construção</AppShell>;
}
```

- [ ] **Step 7: Verificar e commitar**

Run: `npm run typecheck && npm test && npm run build`
Expected: exit 0 nos três.

```bash
git add frontend
git commit -m "feat(frontend): tokens de tema, duas skins e casca da aplicação"
```

---

### Task 3: Contrato de dados, rótulos e formatadores

**Files:**
- Create: `src/types/schemas.ts`, `src/types/novamente.ts`, `src/types/api.ts`, `src/lib/constants.ts`, `src/lib/mensagens.ts`, `src/lib/formatadores.ts`
- Test: `src/types/schemas.test.ts`, `src/lib/formatadores.test.ts`

**Interfaces:**
- Consumes: nada (apenas `zod`).
- Produces: `LIMITES`, `EXTENSOES_ACEITAS`, `AdaptacaoInputSchema`, `AdaptacaoUploadInputSchema`, `AdaptacaoPacoteSchema`, `JobRespostaSchema`, `ApiProblemaSchema`, `ApiProblemaErroSchema`, `AdaptacaoResumoSchema`, `PaginaAdaptacoesSchema`, `OciStatusSchema`, `HealthRespostaSchema`, `CodigoErroSchema`, `EtapaJobSchema`; tipos `AdaptacaoInput`, `AdaptacaoUploadInput`, `AdaptacaoPacote`, `ConteudoAdaptado`, `FlashcardItem`, `QuizItem`, `JobResposta`, `EtapaJob`, `JobStatus`, `AdaptacaoResumo`, `PaginaAdaptacoes`, `OciStatus`, `HealthResposta`, `ApiProblema`, `FormatoExportacao`; `ETAPAS`, `ROTULOS_*`, `M`, `slugify`, `formatarBytes`, `formatarPercentual`, `faixaAncoragem`, `formatarDataRelativa`, `nomeArquivoPacote`, `nomeArquivoExportacao`.

- [ ] **Step 1: Escrever os testes que falham**

`src/types/schemas.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  AdaptacaoInputSchema,
  AdaptacaoPacoteSchema,
  AdaptacaoUploadInputSchema,
  JobRespostaSchema,
  LIMITES,
  ApiProblemaSchema,
} from './schemas';

const pacoteBase = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN', 'Sub-redes'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'Dominando VCN',
    introducao_contextualizada: 'Imagine a VCN como um bairro privado.',
    itens: [
      { frente: 'O que é VCN?', verso: 'Rede virtual privada.' },
      { frente: 'O que é subnet?', verso: 'Subdivisão da VCN.' },
      { frente: 'O que é IGW?', verso: 'Porta de entrada da internet.' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
};

const entradaValida = {
  documento_titulo: 'Introdução à VCN',
  documento_conteudo: 'a'.repeat(LIMITES.textoMin),
  perfil_destinatario: 'Iniciante',
  formato_saida: 'Flashcards',
  nicho_setor: 'Geral',
  nivel_detalhe: 'Didatico',
};

describe('AdaptacaoInputSchema', () => {
  it('aceita entrada válida e aplica trim no título', () => {
    const r = AdaptacaoInputSchema.parse({ ...entradaValida, documento_titulo: '  Introdução  ' });
    expect(r.documento_titulo).toBe('Introdução');
  });

  it('rejeita texto abaixo do mínimo e acima do máximo', () => {
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: 'a'.repeat(199) }).success).toBe(false);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: 'a'.repeat(50_001) }).success).toBe(false);
  });

  it('conta caracteres, não bytes, em texto com acentos e emoji', () => {
    const texto = 'ã'.repeat(200);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: texto }).success).toBe(true);
    const comEmoji = '😀'.repeat(50_001);
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, documento_conteudo: comEmoji }).success).toBe(false);
  });

  it('rejeita campo desconhecido', () => {
    expect(AdaptacaoInputSchema.safeParse({ ...entradaValida, extra: 1 }).success).toBe(false);
  });
});

const baseUpload = {
  documento_titulo: entradaValida.documento_titulo,
  perfil_destinatario: entradaValida.perfil_destinatario,
  formato_saida: entradaValida.formato_saida,
  nicho_setor: entradaValida.nicho_setor,
  nivel_detalhe: entradaValida.nivel_detalhe,
};

describe('AdaptacaoUploadInputSchema', () => {
  it('aceita arquivo .pdf pequeno', () => {
    const arquivo = new File(['conteudo'], 'manual.pdf', { type: 'application/pdf' });
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo }).success).toBe(true);
  });

  it('rejeita extensão não suportada, arquivo vazio e arquivo grande', () => {
    const docx = new File(['x'], 'manual.docx');
    const vazio = new File([''], 'manual.md');
    const grande = new File([new Uint8Array(LIMITES.arquivoMaxBytes + 1)], 'manual.pdf');
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: docx }).success).toBe(false);
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: vazio }).success).toBe(false);
    expect(AdaptacaoUploadInputSchema.safeParse({ ...baseUpload, arquivo: grande }).success).toBe(false);
  });
});

describe('AdaptacaoPacoteSchema', () => {
  it('aceita pacote coerente', () => {
    expect(AdaptacaoPacoteSchema.safeParse(pacoteBase).success).toBe(true);
  });

  it('rejeita tipo de conteúdo incompatível com o formato', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      metadados: { ...pacoteBase.metadados, formato_gerado: 'Quiz' },
    });
    expect(r.success).toBe(false);
  });

  it('rejeita resposta_correta fora das opções', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      metadados: { ...pacoteBase.metadados, formato_gerado: 'Quiz' },
      conteudo_adaptado: {
        tipo: 'quiz',
        titulo: 'Quiz VCN',
        introducao_contextualizada: 'Teste seus conhecimentos.',
        itens: [{ pergunta: 'P?', opcoes: ['a', 'b'], resposta_correta: 2, explicacao: 'porque' }],
      },
    });
    expect(r.success).toBe(false);
  });

  it('rejeita menos de 3 flashcards', () => {
    const r = AdaptacaoPacoteSchema.safeParse({
      ...pacoteBase,
      conteudo_adaptado: { ...pacoteBase.conteudo_adaptado, itens: pacoteBase.conteudo_adaptado.itens.slice(0, 2) },
    });
    expect(r.success).toBe(false);
  });
});

describe('JobRespostaSchema', () => {
  const jobBase = {
    job_id: 'j1',
    status: 'running',
    etapa_atual: 'extraindo',
    etapas_concluidas: [],
    progresso_percentual: 10,
    iniciado_em: '2026-10-21T14:02:11Z',
    atualizado_em: '2026-10-21T14:02:13Z',
  };

  it('aceita job em andamento', () => {
    expect(JobRespostaSchema.safeParse(jobBase).success).toBe(true);
  });

  it('exige resultado e adaptacao_id quando succeeded', () => {
    expect(JobRespostaSchema.safeParse({ ...jobBase, status: 'succeeded', etapa_atual: null }).success).toBe(false);
    expect(
      JobRespostaSchema.safeParse({
        ...jobBase,
        status: 'succeeded',
        etapa_atual: null,
        progresso_percentual: 100,
        adaptacao_id: pacoteBase.adaptacao_id,
        resultado: pacoteBase,
      }).success,
    ).toBe(true);
  });

  it('exige erro quando failed', () => {
    expect(JobRespostaSchema.safeParse({ ...jobBase, status: 'failed' }).success).toBe(false);
  });
});

describe('ApiProblemaSchema', () => {
  it('aceita erro com campos', () => {
    const r = ApiProblemaSchema.safeParse({
      erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Mínimo de 3' } },
    });
    expect(r.success).toBe(true);
  });

  it('rejeita código fora do contrato', () => {
    expect(ApiProblemaSchema.safeParse({ erro: { codigo: 'QUALQUER', mensagem: 'x' } }).success).toBe(false);
  });
});
```

`src/lib/formatadores.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  faixaAncoragem,
  formatarBytes,
  formatarPercentual,
  nomeArquivoExportacao,
  nomeArquivoPacote,
  slugify,
} from './formatadores';
import type { AdaptacaoPacote } from '@/types/novamente';

const pacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  documento: { titulo: 'Introdução à Arquitetura de Redes VCN — Ação & Cia' },
  metadados: { perfil_aplicado: 'LiderTecnico', formato_gerado: 'ResumoExecutivo' },
} as unknown as AdaptacaoPacote;

describe('slugify', () => {
  it('remove acentos e normaliza separadores', () => {
    expect(slugify('Introdução à Arquitetura de Redes VCN')).toBe('introducao-a-arquitetura-de-redes-vcn');
  });

  it('troca emoji e pontuação por hífen único e remove hífens das pontas', () => {
    expect(slugify('  🚀 VCN: o guia!!!  ')).toBe('vcn-o-guia');
  });

  it('limita a 60 caracteres sem terminar em hífen', () => {
    const s = slugify('palavra '.repeat(20));
    expect(s.length).toBeLessThanOrEqual(60);
    expect(s.endsWith('-')).toBe(false);
  });
});

describe('formatarBytes', () => {
  it('usa unidades binárias em pt-BR', () => {
    expect(formatarBytes(1024)).toBe('1 KB');
    expect(formatarBytes(10 * 1024 * 1024)).toBe('10 MB');
  });
});

describe('formatarPercentual', () => {
  it('converte 0..1 em porcentagem inteira', () => {
    expect(formatarPercentual(0.98)).toBe('98%');
    expect(formatarPercentual(0.945)).toBe('95%');
  });
});

describe('faixaAncoragem', () => {
  it('classifica nos limites', () => {
    expect(faixaAncoragem(0.9)).toBe('alta');
    expect(faixaAncoragem(0.89)).toBe('media');
    expect(faixaAncoragem(0.7)).toBe('media');
    expect(faixaAncoragem(0.69)).toBe('baixa');
  });
});

describe('nomeArquivoPacote e nomeArquivoExportacao', () => {
  it('usa slug do documento, perfil, formato e 8 caracteres do id', () => {
    expect(nomeArquivoExportacao(pacote, 'md')).toBe(
      'novamente-introducao-a-arquitetura-de-redes-vcn-acao-cia-lider-tecnico-resumo-executivo-01javcnf.md',
    );
    expect(nomeArquivoPacote(pacote)).toMatch(/^novamente-.*-01javcnf\.json$/);
  });

  it('não contém caractere inválido para cabeçalho HTTP', () => {
    expect(nomeArquivoExportacao(pacote, 'pdf')).toMatch(/^[a-z0-9.-]+$/);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/types/schemas.test.ts src/lib/formatadores.test.ts`
Expected: FAIL — módulos não encontrados.

- [ ] **Step 3: Implementar os schemas**

`src/types/schemas.ts`:

```ts
import { z } from 'zod';

export const LIMITES = {
  tituloMin: 3,
  tituloMax: 150,
  textoMin: 200,
  textoMax: 50_000,
  arquivoMaxBytes: 10 * 1024 * 1024,
  paginaPadrao: 12,
  paginaMax: 50,
} as const;

export const EXTENSOES_ACEITAS = ['.pdf', '.md', '.txt'] as const;

const dataIso = z
  .string()
  .refine(
    (v) => /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v) && !Number.isNaN(Date.parse(v)),
    'Data ISO 8601 inválida',
  );

export const perfilSchema = z.enum(['Iniciante', 'Desenvolvedor', 'LiderTecnico', 'Gestor']);
export const formatoSaidaSchema = z.enum(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']);
export const nichoSchema = z.enum(['Fintech', 'Saude', 'Ecommerce', 'Geral']);
export const nivelDetalheSchema = z.enum(['Didatico', 'Tecnico', 'Executivo']);
export const formatoExportacaoSchema = z.enum(['md', 'pdf', 'csv']);

export const tituloSchema = z
  .string()
  .trim()
  .min(LIMITES.tituloMin, 'Mínimo de 3 caracteres')
  .max(LIMITES.tituloMax, 'Máximo de 150 caracteres');

export const textoSchema = z
  .string()
  .trim()
  .min(LIMITES.textoMin, 'Mínimo de 200 caracteres')
  .max(LIMITES.textoMax, 'Máximo de 50.000 caracteres');

export const arquivoSchema = z
  .custom<File>((v) => typeof File !== 'undefined' && v instanceof File, { message: 'Selecione um arquivo.' })
  .refine((f) => f.size > 0, 'Arquivo vazio.')
  .refine((f) => f.size <= LIMITES.arquivoMaxBytes, 'Arquivo acima de 10 MB.')
  .refine(
    (f) => EXTENSOES_ACEITAS.some((ext) => f.name.toLowerCase().endsWith(ext)),
    'Use um arquivo .pdf, .md ou .txt.',
  );

export const AdaptacaoInputSchema = z
  .object({
    documento_titulo: tituloSchema,
    documento_conteudo: textoSchema,
    perfil_destinatario: perfilSchema,
    formato_saida: formatoSaidaSchema,
    nicho_setor: nichoSchema,
    nivel_detalhe: nivelDetalheSchema,
  })
  .strict();

export const AdaptacaoUploadInputSchema = z
  .object({
    arquivo: arquivoSchema,
    documento_titulo: tituloSchema,
    perfil_destinatario: perfilSchema,
    formato_saida: formatoSaidaSchema,
    nicho_setor: nichoSchema,
    nivel_detalhe: nivelDetalheSchema,
  })
  .strict();

export const FlashcardItemSchema = z
  .object({
    frente: z.string().trim().min(1),
    verso: z.string().trim().min(1),
    dica_didatica: z.string().trim().min(1).optional(),
  })
  .strict();

export const QuizItemSchema = z
  .object({
    pergunta: z.string().trim().min(1),
    opcoes: z.array(z.string().trim().min(1)).min(2).max(6),
    resposta_correta: z.number().int().min(0),
    explicacao: z.string().trim().min(1),
  })
  .strict();

export const ConteudoAdaptadoSchema = z.discriminatedUnion('tipo', [
  z
    .object({
      tipo: z.literal('flashcards'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.array(FlashcardItemSchema).min(3).max(30),
    })
    .strict(),
  z
    .object({
      tipo: z.literal('quiz'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.array(QuizItemSchema).min(1).max(20),
    })
    .strict(),
  z
    .object({
      tipo: z.literal('markdown'),
      titulo: z.string().min(1),
      introducao_contextualizada: z.string().min(1),
      itens: z.string().min(40),
    })
    .strict(),
]);

export const DocumentoRefSchema = z
  .object({
    titulo: z.string().min(1),
    origem: z.enum(['upload', 'texto']),
    nome_arquivo: z.string().min(1).optional(),
    tamanho_bytes: z.number().int().nonnegative().optional(),
  })
  .strict();

export const MetadadosSchema = z
  .object({
    perfil_aplicado: perfilSchema,
    formato_gerado: formatoSaidaSchema,
    nivel_detalhe_aplicado: nivelDetalheSchema,
    nicho_setor_aplicado: nichoSchema,
    tempo_estimado_estudo_minutos: z.number().int().min(1),
    conceitos_chave: z.array(z.string().min(1)).min(1).max(12),
  })
  .strict();

export const AvaliacaoQualidadeSchema = z
  .object({
    ancoragem_fonte_score: z.number().min(0).max(1),
    clareza_pedagogica: z.enum(['Alta', 'Media', 'Baixa']),
    observacoes: z.string().min(1).optional(),
  })
  .strict();

export const ArmazenamentoOciSchema = z
  .object({
    bucket: z.string().min(1),
    objeto_id: z.string().min(1),
    status_upload: z.enum(['concluido', 'falha']),
  })
  .strict();

export const CodigoErroSchema = z.enum([
  'VALIDACAO',
  'ARQUIVO_INVALIDO',
  'DOCUMENTO_ILEGIVEL',
  'LIMITE_EXCEDIDO',
  'ADAPTACAO_NAO_ENCONTRADA',
  'JOB_NAO_ENCONTRADO',
  'JOB_FINALIZADO',
  'FORMATO_INCOMPATIVEL',
  'FORMATO_DESCONHECIDO',
  'OCI_INDISPONIVEL',
  'INTERNO',
]);

export const ApiProblemaErroSchema = z
  .object({
    codigo: CodigoErroSchema,
    mensagem: z.string().min(1),
    campos: z.record(z.string(), z.string()).optional(),
    request_id: z.string().min(1).optional(),
  })
  .strict();

export const ApiProblemaSchema = z.object({ erro: ApiProblemaErroSchema }).strict();

const formatoParaTipo = {
  Flashcards: 'flashcards',
  Quiz: 'quiz',
  Tutorial: 'markdown',
  ResumoExecutivo: 'markdown',
} as const;

export const AdaptacaoPacoteSchema = z
  .object({
    adaptacao_id: z.string().min(1),
    status: z.literal('sucesso'),
    criado_em: dataIso,
    documento: DocumentoRefSchema,
    metadados: MetadadosSchema,
    conteudo_adaptado: ConteudoAdaptadoSchema,
    avaliacao_qualidade: AvaliacaoQualidadeSchema,
    armazenamento_oci: ArmazenamentoOciSchema,
  })
  .strict()
  .superRefine((pacote, ctx) => {
    const esperado = formatoParaTipo[pacote.metadados.formato_gerado];
    if (pacote.conteudo_adaptado.tipo !== esperado) {
      ctx.addIssue({
        code: 'custom',
        path: ['conteudo_adaptado', 'tipo'],
        message: `Formato ${pacote.metadados.formato_gerado} exige conteúdo ${esperado}.`,
      });
    }
    if (pacote.conteudo_adaptado.tipo === 'quiz') {
      pacote.conteudo_adaptado.itens.forEach((item, indice) => {
        if (item.resposta_correta >= item.opcoes.length) {
          ctx.addIssue({
            code: 'custom',
            path: ['conteudo_adaptado', 'itens', indice, 'resposta_correta'],
            message: 'resposta_correta fora do intervalo de opções.',
          });
        }
      });
    }
  });

export const EtapaJobSchema = z.enum([
  'extraindo',
  'chunking',
  'embeddings',
  'gerando',
  'revisando',
  'armazenando',
]);

export const JobRespostaSchema = z
  .object({
    job_id: z.string().min(1),
    status: z.enum(['queued', 'running', 'succeeded', 'failed', 'cancelled']),
    etapa_atual: EtapaJobSchema.nullable(),
    etapas_concluidas: z.array(EtapaJobSchema),
    progresso_percentual: z.number().min(0).max(100),
    mensagem: z.string().min(1).optional(),
    iniciado_em: dataIso,
    atualizado_em: dataIso,
    adaptacao_id: z.string().min(1).optional(),
    resultado: AdaptacaoPacoteSchema.optional(),
    erro: ApiProblemaErroSchema.optional(),
  })
  .strict()
  .superRefine((job, ctx) => {
    if (job.status === 'succeeded' && (!job.resultado || !job.adaptacao_id)) {
      ctx.addIssue({ code: 'custom', message: 'Job concluído exige resultado e adaptacao_id.' });
    }
    if (job.status === 'failed' && !job.erro) {
      ctx.addIssue({ code: 'custom', message: 'Job com falha exige erro.' });
    }
  });

export const AdaptacaoResumoSchema = z
  .object({
    adaptacao_id: z.string().min(1),
    criado_em: dataIso,
    documento: DocumentoRefSchema,
    perfil_aplicado: perfilSchema,
    formato_gerado: formatoSaidaSchema,
    nivel_detalhe_aplicado: nivelDetalheSchema,
    tempo_estimado_estudo_minutos: z.number().int().min(1),
    ancoragem_fonte_score: z.number().min(0).max(1),
    status_upload: z.enum(['concluido', 'falha']),
    conceitos_chave: z.array(z.string().min(1)).max(6),
  })
  .strict();

export const PaginaAdaptacoesSchema = z
  .object({
    itens: z.array(AdaptacaoResumoSchema),
    pagina: z.number().int().min(1),
    tamanho_pagina: z.number().int().min(1).max(LIMITES.paginaMax),
    total: z.number().int().min(0),
    total_paginas: z.number().int().min(0),
  })
  .strict();

export const OciStatusSchema = z
  .object({
    configurado: z.boolean(),
    bucket: z.string().min(1).optional(),
    regiao: z.string().min(1).optional(),
    total_objetos: z.number().int().min(0).optional(),
    bytes_armazenados: z.number().int().min(0).optional(),
    ultimo_upload_em: dataIso.optional(),
    mensagem: z.string().min(1).optional(),
    verificado_em: dataIso,
  })
  .strict();

export const HealthRespostaSchema = z
  .object({
    status: z.enum(['ok', 'degraded']),
    versao: z.string().min(1),
    oci: z.enum(['ok', 'indisponivel']),
    llm: z.enum(['ok', 'indisponivel']),
    verificado_em: dataIso,
  })
  .strict();
```

`src/types/novamente.ts`:

```ts
import type { z } from 'zod';
import type {
  AdaptacaoInputSchema,
  AdaptacaoPacoteSchema,
  AdaptacaoResumoSchema,
  AdaptacaoUploadInputSchema,
  ApiProblemaErroSchema,
  EtapaJobSchema,
  HealthRespostaSchema,
  JobRespostaSchema,
  OciStatusSchema,
  PaginaAdaptacoesSchema,
  perfilSchema,
  formatoSaidaSchema,
  nichoSchema,
  nivelDetalheSchema,
  formatoExportacaoSchema,
  ConteudoAdaptadoSchema,
  FlashcardItemSchema,
  QuizItemSchema,
} from './schemas';

export type PerfilDestinatario = z.infer<typeof perfilSchema>;
export type FormatoSaida = z.infer<typeof formatoSaidaSchema>;
export type NichoSetor = z.infer<typeof nichoSchema>;
export type NivelDetalhe = z.infer<typeof nivelDetalheSchema>;
export type FormatoExportacao = z.infer<typeof formatoExportacaoSchema>;
export type AdaptacaoInput = z.infer<typeof AdaptacaoInputSchema>;
export type AdaptacaoUploadInput = z.infer<typeof AdaptacaoUploadInputSchema>;
export type AdaptacaoPacote = z.infer<typeof AdaptacaoPacoteSchema>;
export type AdaptacaoResumo = z.infer<typeof AdaptacaoResumoSchema>;
export type PaginaAdaptacoes = z.infer<typeof PaginaAdaptacoesSchema>;
export type ConteudoAdaptado = z.infer<typeof ConteudoAdaptadoSchema>;
export type FlashcardItem = z.infer<typeof FlashcardItemSchema>;
export type QuizItem = z.infer<typeof QuizItemSchema>;
export type JobResposta = z.infer<typeof JobRespostaSchema>;
export type JobStatus = JobResposta['status'];
export type EtapaJob = z.infer<typeof EtapaJobSchema>;
export type ApiProblemaErro = z.infer<typeof ApiProblemaErroSchema>;
export type ApiProblema = { erro: ApiProblemaErro };
export type OciStatus = z.infer<typeof OciStatusSchema>;
export type HealthResposta = z.infer<typeof HealthRespostaSchema>;
export type OrigemDocumento = 'upload' | 'texto';
```

`src/types/api.ts`:

```ts
export type {
  ApiProblema,
  ApiProblemaErro,
  AdaptacaoResumo,
  PaginaAdaptacoes,
  JobResposta,
  JobStatus,
  EtapaJob,
  OciStatus,
  HealthResposta,
} from './novamente';
```

- [ ] **Step 4: Rodar e ver falhar ainda**

Run: `npm test -- src/types/schemas.test.ts`
Expected: PASS nos schemas; `formatadores.test.ts` continua FAIL (módulo ausente).

- [ ] **Step 5: Implementar rótulos, mensagens e formatadores**

`src/lib/constants.ts`:

```ts
import type { EtapaJob, FormatoSaida, NivelDetalhe, PerfilDestinatario } from '@/types/novamente';

export const PERFIS: { valor: PerfilDestinatario; rotulo: string; descricao: string }[] = [
  { valor: 'Iniciante', rotulo: 'Iniciante / Transição de Carreira', descricao: 'Sem jargão, com analogias' },
  { valor: 'Desenvolvedor', rotulo: 'Desenvolvedor Júnior / Pleno', descricao: 'Precisão técnica e exemplos de código' },
  { valor: 'LiderTecnico', rotulo: 'Líder Técnico / Arquiteto', descricao: 'Decisões, trade-offs e padrões' },
  { valor: 'Gestor', rotulo: 'Gestor / Executivo (Não Técnico)', descricao: 'Impacto, custo e risco' },
];

export const FORMATOS: { valor: FormatoSaida; rotulo: string; descricao: string }[] = [
  { valor: 'Flashcards', rotulo: 'Flashcards', descricao: 'Memorização por repetição' },
  { valor: 'Quiz', rotulo: 'Quiz interativo', descricao: 'Perguntas com justificativa' },
  { valor: 'Tutorial', rotulo: 'Tutorial', descricao: 'Guia passo a passo' },
  { valor: 'ResumoExecutivo', rotulo: 'Resumo Executivo (TL;DR)', descricao: 'Essência em poucos minutos' },
];

export const NICHOS = [
  { valor: 'Fintech', rotulo: 'Fintech' },
  { valor: 'Saude', rotulo: 'Saúde' },
  { valor: 'Ecommerce', rotulo: 'E-commerce' },
  { valor: 'Geral', rotulo: 'Geral' },
] as const;

export const NIVEIS: { valor: NivelDetalhe; rotulo: string }[] = [
  { valor: 'Didatico', rotulo: 'Didático' },
  { valor: 'Tecnico', rotulo: 'Técnico' },
  { valor: 'Executivo', rotulo: 'Executivo' },
];

export const ETAPAS: EtapaJob[] = ['extraindo', 'chunking', 'embeddings', 'gerando', 'revisando', 'armazenando'];

export const ROTULOS_ETAPA: Record<EtapaJob, string> = {
  extraindo: 'Extraindo texto',
  chunking: 'Segmentando conteúdo',
  embeddings: 'Gerando embeddings',
  gerando: 'Redigindo material',
  revisando: 'Revisando fidelidade',
  armazenando: 'Salvando no OCI',
};

export const INTERVALO_POLL_MS = 1_500;
export const INTERVALO_POLL_LONGO_MS = 3_000;
export const LIMITE_TEMPO_JOB_MS = 5 * 60 * 1_000;
export const JANELA_POLL_RAPIDO_MS = 60_000;

export const DOCUMENTO_DEMO = `A Virtual Cloud Network (VCN) é uma rede privada e personalizável configurada na Oracle Cloud Infrastructure. Semelhante a uma rede de data center tradicional, a VCN oferece controle total sobre o ambiente de rede, incluindo sub-redes públicas e privadas, tabelas de roteamento, Internet Gateways, NAT Gateways e Security Lists para controle de tráfego via regras de entrada (ingress) e saída (egress). Cada sub-rede pode ser pública ou privada, e o roteamento decide para onde o tráfego segue.`;
```

`src/lib/mensagens.ts` — **substituir** o arquivo inicial da Task 2 por esta versão completa (as seções `app` e `comum` continuam idênticas):

```ts
export const M = {
  app: {
    nome: 'NovaMente',
    navGerar: 'Gerar',
    navHistorico: 'Histórico',
    navPrincipal: 'Principal',
    tema: 'Tema',
    emConstrucao: 'Em construção',
  },
  comum: {
    carregando: 'Carregando…',
    tentarNovamente: 'Tentar novamente',
    voltar: 'Voltar',
    erroTitulo: 'Algo deu errado',
    irParaConteudo: 'Ir para o conteúdo',
  },
  formulario: {
    titulo: 'Gerar material didático',
    abaTexto: 'Colar texto',
    abaArquivo: 'Enviar arquivo',
    campoTitulo: 'Título do documento',
    placeholderTitulo: 'Ex.: Introdução à Arquitetura de Redes VCN na OCI',
    campoTexto: 'Conteúdo técnico',
    placeholderTexto: 'Cole aqui o trecho da documentação…',
    contador: (atual: number, maximo: number) => `${atual.toLocaleString('pt-BR')} / ${maximo.toLocaleString('pt-BR')}`,
    campoArquivo: 'Arquivo do documento',
    dropzone: 'Arraste o arquivo ou clique para selecionar',
    dropzoneAjuda: 'PDF, Markdown ou TXT, até 10 MB',
    removerArquivo: 'Remover arquivo',
    campoPerfil: 'Perfil do destinatário',
    campoFormato: 'Formato de saída',
    campoNicho: 'Nicho / setor',
    campoNivel: 'Nível de detalhe',
    enviar: 'Gerar material',
    enviando: 'Criando geração…',
    cancelarGeracao: 'Cancelar geração',
    cenarios: 'Cenários de demonstração',
    resumoErros: 'Corrija os campos destacados.',
  },
  job: {
    titulo: 'Gerando seu material',
    timeout: 'A geração passou de 5 minutos e foi interrompida. Tente novamente.',
    falhaTitulo: 'A geração falhou',
    perdida: 'Esta geração foi perdida. Tente novamente.',
  },
  resultado: {
    exportar: 'Exportar',
    baixarJson: 'Baixar JSON',
    novaGeracao: 'Nova geração',
    ancoragem: 'Ancoragem na fonte',
    clareza: 'Clareza pedagógica',
    observacoes: 'Observações',
    bucket: 'Bucket',
    objeto: 'Objeto',
    tempoEstimado: (minutos: number) => `${minutos} min de estudo`,
    naoPersistido: 'Material exibido, mas não persistido no OCI.',
  },
  quiz: {
    confirmar: 'Confirmar',
    proxima: 'Próxima',
    reiniciar: 'Refazer',
    correto: 'Resposta correta',
    incorreto: 'Resposta incorreta',
    placar: (acertos: number, total: number) => `${acertos} / ${total}`,
    revisar: 'Revisar erradas',
    semErros: 'Você acertou todas.',
  },
  historico: {
    titulo: 'Histórico',
    vazio: 'Nenhum material gerado ainda.',
    vazioCta: 'Gerar o primeiro material',
    busca: 'Buscar por título ou conceito',
    todosFormatos: 'Todos os formatos',
    todosPerfis: 'Todos os perfis',
    pagina: (pagina: number, total: number) => `Página ${pagina} de ${total}`,
    anterior: 'Anterior',
    proxima: 'Próxima',
  },
  oci: {
    titulo: 'Armazenamento OCI',
    naoConfigurado: 'OCI não configurado',
    objetos: 'Objetos',
    ultimoUpload: 'Último upload',
    falhaUpload: 'Falha no upload',
    concluido: 'Persistido no OCI',
  },
  erro: {
    rede: 'Não foi possível falar com o servidor.',
    generico: 'Erro inesperado. Tente novamente.',
    contrato: 'O servidor respondeu em um formato inesperado.',
  },
} as const;
```

`src/lib/formatadores.ts`:

```ts
import type { AdaptacaoPacote, FormatoExportacao, PerfilDestinatario, FormatoSaida } from '@/types/novamente';

const SLUG_PERFIL: Record<PerfilDestinatario, string> = {
  Iniciante: 'iniciante',
  Desenvolvedor: 'desenvolvedor',
  LiderTecnico: 'lider-tecnico',
  Gestor: 'gestor',
};

const SLUG_FORMATO: Record<FormatoSaida, string> = {
  Flashcards: 'flashcards',
  Quiz: 'quiz',
  Tutorial: 'tutorial',
  ResumoExecutivo: 'resumo-executivo',
};

export function slugify(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/g, '');
}

export function formatarBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024))} MB`;
}

export function formatarPercentual(valor: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 }).format(valor);
}

export function faixaAncoragem(valor: number): 'alta' | 'media' | 'baixa' {
  if (valor >= 0.9) return 'alta';
  if (valor >= 0.7) return 'media';
  return 'baixa';
}

export function formatarDataRelativa(iso: string, agora = Date.now()): string {
  const diferenca = new Date(iso).getTime() - agora;
  const minutos = Math.round(diferenca / 60_000);
  const formato = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });
  if (Math.abs(minutos) < 60) return formato.format(minutos, 'minute');
  const horas = Math.round(minutos / 60);
  if (Math.abs(horas) < 24) return formato.format(horas, 'hour');
  return formato.format(Math.round(horas / 24), 'day');
}

function baseNome(pacote: AdaptacaoPacote): string {
  const id8 = pacote.adaptacao_id.slice(0, 8).toLowerCase();
  return `novamente-${slugify(pacote.documento.titulo)}-${SLUG_PERFIL[pacote.metadados.perfil_aplicado]}-${SLUG_FORMATO[pacote.metadados.formato_gerado]}-${id8}`;
}

export function nomeArquivoPacote(pacote: AdaptacaoPacote): string {
  return `${baseNome(pacote)}.json`;
}

export function nomeArquivoExportacao(pacote: AdaptacaoPacote, formato: FormatoExportacao): string {
  return `${baseNome(pacote)}.${formato}`;
}
```

- [ ] **Step 6: Rodar e ver passar**

Run: `npm test -- src/types/schemas.test.ts src/lib/formatadores.test.ts`
Expected: PASS em todos.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): contrato zod, rótulos pt-BR e formatadores"
```

---

### Task 4: Camada de serviço HTTP

**Files:**
- Create: `src/services/api/erros.ts`, `src/services/api/NovaMenteApi.ts`, `src/services/api/endpoints.ts`, `src/services/api/httpApiClient.ts`, `src/services/api/ApiProvider.tsx`
- Modify: `src/app/providers.tsx`
- Test: `src/services/api/httpApiClient.test.ts`, `src/services/api/erros.test.ts`

**Interfaces:**
- Consumes: tipos e schemas da Task 3.
- Produces: `ErroApi` (`{ problema, status }`), `ErroRede`, `ErroContrato`, `mensagemDoErro(e): string`, `NovaMenteApi` (10 métodos), `httpApiClient`, `ApiProvider`, `useApi()`.

- [ ] **Step 1: Escrever os testes que falham**

`src/services/api/erros.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { ErroApi, ErroContrato, ErroRede, mensagemDoErro, paraProblema } from './erros';

describe('paraProblema', () => {
  it('usa o corpo quando já é ApiProblema', () => {
    const corpo = { erro: { codigo: 'VALIDACAO', mensagem: 'Inválido', campos: { a: 'b' } } };
    expect(paraProblema(422, corpo)).toEqual(corpo);
  });

  it('cria fallback quando o corpo não segue o contrato', () => {
    const p = paraProblema(502, '<html>Bad gateway</html>');
    expect(p.erro.codigo).toBe('INTERNO');
    expect(p.erro.mensagem).toContain('502');
  });
});

describe('mensagemDoErro', () => {
  it('prefere a mensagem do servidor', () => {
    const e = new ErroApi({ erro: { codigo: 'LIMITE_EXCEDIDO', mensagem: 'Arquivo acima de 10 MB.' } }, 413);
    expect(mensagemDoErro(e)).toBe('Arquivo acima de 10 MB.');
  });

  it('distingue rede, contrato e desconhecido', () => {
    expect(mensagemDoErro(new ErroRede())).toContain('servidor');
    expect(mensagemDoErro(new ErroContrato())).toContain('formato inesperado');
    expect(mensagemDoErro(new Error('x'))).toContain('inesperado');
  });
});
```

`src/services/api/httpApiClient.test.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { httpApiClient } from './httpApiClient';
import { ErroApi, ErroRede } from './erros';

const pacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'VCN',
    introducao_contextualizada: 'Intro',
    itens: [
      { frente: 'a', verso: 'b' },
      { frente: 'c', verso: 'd' },
      { frente: 'e', verso: 'f' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'b', objeto_id: 'o.json', status_upload: 'concluido' },
};

let corpoRecebido: unknown = null;
let formRecebido: FormData | null = null;
let queryRecebida = '';

const server = setupServer(
  http.post('*/api/v1/adaptacoes', async ({ request }) => {
    corpoRecebido = await request.json();
    return HttpResponse.json(
      {
        job_id: 'j1',
        status: 'queued',
        etapa_atual: null,
        etapas_concluidas: [],
        progresso_percentual: 0,
        iniciado_em: '2026-10-21T14:02:11Z',
        atualizado_em: '2026-10-21T14:02:11Z',
      },
      { status: 202 },
    );
  }),
  http.post('*/api/v1/adaptacoes/upload', async ({ request }) => {
    formRecebido = await request.formData();
    return HttpResponse.json(
      {
        job_id: 'j2',
        status: 'queued',
        etapa_atual: null,
        etapas_concluidas: [],
        progresso_percentual: 0,
        iniciado_em: '2026-10-21T14:02:11Z',
        atualizado_em: '2026-10-21T14:02:11Z',
      },
      { status: 202 },
    );
  }),
  http.get('*/api/v1/adaptacoes', ({ request }) => {
    queryRecebida = new URL(request.url).search;
    return HttpResponse.json({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 });
  }),
  http.get('*/api/v1/adaptacoes/:id', () => HttpResponse.json(pacote)),
  http.get('*/api/v1/adaptacoes/:id/download', () =>
    HttpResponse.json(pacote, { headers: { 'Content-Disposition': 'attachment; filename="x.json"' } }),
  ),
  http.get('*/api/v1/adaptacoes/:id/exportacao', () => new HttpResponse('%PDF-1.4', {
    headers: { 'Content-Type': 'application/pdf' },
  })),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  corpoRecebido = null;
  formRecebido = null;
  queryRecebida = '';
});
afterAll(() => server.close());

const entrada = {
  documento_titulo: 'VCN',
  documento_conteudo: 'a'.repeat(200),
  perfil_destinatario: 'Iniciante' as const,
  formato_saida: 'Flashcards' as const,
  nicho_setor: 'Geral' as const,
  nivel_detalhe: 'Didatico' as const,
};

describe('httpApiClient', () => {
  it('envia JSON para criação por texto', async () => {
    const job = await httpApiClient.criarPorTexto(entrada);
    expect(job.job_id).toBe('j1');
    expect(corpoRecebido).toEqual(entrada);
  });

  it('envia multipart sem documento_conteudo', async () => {
    const arquivo = new File(['abc'], 'manual.pdf', { type: 'application/pdf' });
    await httpApiClient.criarPorArquivo({ ...entrada, documento_conteudo: undefined, arquivo } as never);
    expect(formRecebido?.get('arquivo')).toBeInstanceOf(File);
    expect(formRecebido?.get('documento_conteudo')).toBeNull();
    expect(formRecebido?.get('perfil_destinatario')).toBe('Iniciante');
  });

  it('monta query string só com filtros preenchidos', async () => {
    await httpApiClient.listar({ pagina: 2, formato: 'Quiz', q: '' });
    expect(queryRecebida).toContain('pagina=2');
    expect(queryRecebida).toContain('formato=Quiz');
    expect(queryRecebida).not.toContain('q=');
  });

  it('devolve blob na exportação', async () => {
    const blob = await httpApiClient.exportar('id1', 'pdf');
    expect(blob.type).toBe('application/pdf');
    expect(await blob.text()).toBe('%PDF-1.4');
  });

  it('converte erro 422 em ErroApi com campos', async () => {
    server.use(
      http.post('*/api/v1/adaptacoes', () =>
        HttpResponse.json(
          { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Mínimo de 3' } } },
          { status: 422 },
        ),
      ),
    );
    await expect(httpApiClient.criarPorTexto(entrada)).rejects.toMatchObject({
      name: 'ErroApi',
      status: 422,
      problema: { erro: { campos: { documento_titulo: 'Mínimo de 3' } } },
    });
  });

  it('converte falha de rede em ErroRede', async () => {
    server.use(http.post('*/api/v1/adaptacoes', () => HttpResponse.error()));
    await expect(httpApiClient.criarPorTexto(entrada)).rejects.toBeInstanceOf(ErroRede);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/services/api`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar erros e endpoints**

`src/services/api/erros.ts`:

```ts
import type { ApiProblema } from '@/types/novamente';
import { ApiProblemaSchema } from '@/types/schemas';
import { M } from '@/lib/mensagens';

export class ErroApi extends Error {
  constructor(
    public readonly problema: ApiProblema,
    public readonly status: number,
  ) {
    super(problema.erro.mensagem);
    this.name = 'ErroApi';
  }
}

export class ErroRede extends Error {
  constructor() {
    super(M.erro.rede);
    this.name = 'ErroRede';
  }
}

export class ErroContrato extends Error {
  constructor(public readonly detalhe: string) {
    super(M.erro.contrato);
    this.name = 'ErroContrato';
  }
}

export function paraProblema(status: number, corpo: unknown): ApiProblema {
  const analisado = ApiProblemaSchema.safeParse(corpo);
  if (analisado.success) return analisado.data;
  return {
    erro: {
      codigo: 'INTERNO',
      mensagem: `Erro inesperado no servidor (HTTP ${status}).`,
    },
  };
}

export function mensagemDoErro(erro: unknown): string {
  if (erro instanceof ErroApi) return erro.problema.erro.mensagem;
  if (erro instanceof ErroRede) return erro.message;
  if (erro instanceof ErroContrato) return erro.message;
  return M.erro.generico;
}
```

`src/services/api/endpoints.ts`:

```ts
const BASE = '/api/v1';

export const urls = {
  adaptacoes: `${BASE}/adaptacoes`,
  upload: `${BASE}/adaptacoes/upload`,
  job: (jobId: string) => `${BASE}/jobs/${encodeURIComponent(jobId)}`,
  adaptacao: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}`,
  download: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}/download`,
  exportacao: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}/exportacao`,
  ociStatus: `${BASE}/oci/status`,
  health: `${BASE}/health`,
};

export function montarQuery(params: Record<string, string | number | undefined>): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === '') continue;
    busca.set(chave, String(valor));
  }
  const texto = busca.toString();
  return texto ? `?${texto}` : '';
}
```

- [ ] **Step 4: Implementar a interface e o cliente**

`src/services/api/NovaMenteApi.ts`:

```ts
import type {
  AdaptacaoInput,
  AdaptacaoPacote,
  AdaptacaoUploadInput,
  FormatoExportacao,
  HealthResposta,
  JobResposta,
  OciStatus,
  PaginaAdaptacoes,
} from '@/types/novamente';

export interface ListarAdaptacoesParams {
  pagina?: number;
  tamanho_pagina?: number;
  formato?: string;
  perfil?: string;
  q?: string;
  ordenar?: 'criado_em:desc' | 'criado_em:asc' | 'ancoragem:desc';
}

export interface NovaMenteApi {
  criarPorTexto(input: AdaptacaoInput): Promise<JobResposta>;
  criarPorArquivo(input: AdaptacaoUploadInput): Promise<JobResposta>;
  obterJob(jobId: string): Promise<JobResposta>;
  cancelarJob(jobId: string): Promise<JobResposta>;
  listar(params?: ListarAdaptacoesParams): Promise<PaginaAdaptacoes>;
  obter(adaptacaoId: string): Promise<AdaptacaoPacote>;
  baixarJson(adaptacaoId: string): Promise<Blob>;
  exportar(adaptacaoId: string, formato: FormatoExportacao): Promise<Blob>;
  statusOci(): Promise<OciStatus>;
  health(): Promise<HealthResposta>;
}
```

`src/services/api/httpApiClient.ts`:

```ts
import type { NovaMenteApi, ListarAdaptacoesParams } from './NovaMenteApi';
import { montarQuery, urls } from './endpoints';
import { ErroApi, ErroRede, paraProblema } from './erros';
import type {
  AdaptacaoInput,
  AdaptacaoPacote,
  AdaptacaoUploadInput,
  FormatoExportacao,
  HealthResposta,
  JobResposta,
  OciStatus,
  PaginaAdaptacoes,
} from '@/types/novamente';

async function lerCorpo(resposta: Response): Promise<unknown> {
  try {
    return await resposta.json();
  } catch {
    return null;
  }
}

async function pedir<T>(caminho: string, init?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, init);
  } catch {
    throw new ErroRede();
  }
  if (!resposta.ok) {
    throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
  }
  return (await resposta.json()) as T;
}

async function pedirArquivo(caminho: string): Promise<Blob> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho);
  } catch {
    throw new ErroRede();
  }
  if (!resposta.ok) {
    throw new ErroApi(paraProblema(resposta.status, await lerCorpo(resposta)), resposta.status);
  }
  return resposta.blob();
}

function formDataDe(input: AdaptacaoUploadInput): FormData {
  const form = new FormData();
  form.set('arquivo', input.arquivo);
  form.set('documento_titulo', input.documento_titulo);
  form.set('perfil_destinatario', input.perfil_destinatario);
  form.set('formato_saida', input.formato_saida);
  form.set('nicho_setor', input.nicho_setor);
  form.set('nivel_detalhe', input.nivel_detalhe);
  return form;
}

export const httpApiClient: NovaMenteApi = {
  criarPorTexto: (input) =>
    pedir<JobResposta>(urls.adaptacoes, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    }),

  criarPorArquivo: (input) =>
    pedir<JobResposta>(urls.upload, { method: 'POST', body: formDataDe(input) }),

  obterJob: (jobId) => pedir<JobResposta>(urls.job(jobId)),

  cancelarJob: (jobId) => pedir<JobResposta>(urls.job(jobId), { method: 'DELETE' }),

  listar: (params: ListarAdaptacoesParams = {}) =>
    pedir<PaginaAdaptacoes>(
      `${urls.adaptacoes}${montarQuery({
        pagina: params.pagina,
        tamanho_pagina: params.tamanho_pagina,
        formato: params.formato,
        perfil: params.perfil,
        q: params.q,
        ordenar: params.ordenar,
      })}`,
    ),

  obter: (adaptacaoId) => pedir<AdaptacaoPacote>(urls.adaptacao(adaptacaoId)),

  baixarJson: (adaptacaoId) => pedirArquivo(urls.download(adaptacaoId)),

  exportar: (adaptacaoId, formato: FormatoExportacao) =>
    pedirArquivo(`${urls.exportacao(adaptacaoId)}${montarQuery({ formato })}`),

  statusOci: () => pedir<OciStatus>(urls.ociStatus),

  health: () => pedir<HealthResposta>(urls.health),
};
```

- [ ] **Step 5: Provider e ajuste do retry**

`src/services/api/ApiProvider.tsx`:

```tsx
'use client';

import { createContext, useContext } from 'react';
import { httpApiClient } from './httpApiClient';
import type { NovaMenteApi } from './NovaMenteApi';

const ApiContext = createContext<NovaMenteApi | null>(null);

export function ApiProvider({
  client = httpApiClient,
  children,
}: {
  client?: NovaMenteApi;
  children: React.ReactNode;
}) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): NovaMenteApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error('useApi exige ApiProvider');
  return api;
}
```

`src/app/providers.tsx` — substituir o `defaultOptions`:

```tsx
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';

// dentro do useState(() => new QueryClient({...}))
queries: {
  retry: (tentativa, erro) => {
    if (erro instanceof ErroApi && erro.status < 500) return false;
    return tentativa < 2;
  },
  staleTime: 30_000,
  refetchOnWindowFocus: false,
},
```

E envolver: `<ApiProvider><QueryClientProvider client={client}>{children}</QueryClientProvider></ApiProvider>`.

- [ ] **Step 6: Rodar e ver passar**

Run: `npm test -- src/services/api`
Expected: PASS (6 testes em `httpApiClient` + 4 em `erros`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): cliente HTTP com DIP, erros tipados e injeção de API"
```

---

### Task 5: Mocks MSW, fixtures e contrato executável

**Files:**
- Create: `src/mocks/fixtures/flashcards-vcn-iniciante.json`, `quiz-vcn-desenvolvedor.json`, `tutorial-vcn-lider.json`, `resumo-vcn-gestor.json`, `src/mocks/estadoJobs.ts`, `src/mocks/handlers/{index,adaptacoes,jobs,oci,health}.ts`, `src/mocks/browser.ts`, `src/mocks/server.ts`, `src/mocks/MockProvider.tsx`
- Modify: `src/app/providers.tsx`, `.storybook/preview.ts`, `public/mockServiceWorker.js` (gerado)
- Test: `src/mocks/fixtures.test.ts`, `src/mocks/handlers.test.ts`

**Interfaces:**
- Consumes: clientes e schemas das Tasks 3 e 4.
- Produces: handlers de todas as rotas, `worker`, `server`, `configurarDuracaoJob(ms)`, `limparEstadoMock()`, `semearHistorico(qtd)`, `MockProvider`.

- [ ] **Step 1: Escrever os testes que falham**

`src/mocks/fixtures.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { AdaptacaoPacoteSchema } from '@/types/schemas';
import flashcards from './fixtures/flashcards-vcn-iniciante.json';
import quiz from './fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from './fixtures/tutorial-vcn-lider.json';
import resumo from './fixtures/resumo-vcn-gestor.json';

describe('fixtures de demonstração', () => {
  it.each([
    ['flashcards', flashcards],
    ['quiz', quiz],
    ['tutorial', tutorial],
    ['resumo', resumo],
  ])('%s respeita o contrato AdaptacaoPacote', (_nome, fixture) => {
    const resultado = AdaptacaoPacoteSchema.safeParse(fixture);
    expect(resultado.success, resultado.success ? '' : JSON.stringify(resultado.error.issues)).toBe(true);
  });

  it('cobre os quatro formatos', () => {
    const formatos = [flashcards, quiz, tutorial, resumo].map((p) => (p as { metadados: { formato_gerado: string } }).metadados.formato_gerado);
    expect(new Set(formatos)).toEqual(new Set(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']));
  });
});
```

`src/mocks/handlers.test.ts`:

```ts
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { server } from './server';
import { configurarDuracaoJob, limparEstadoMock, semearHistorico } from './estadoJobs';
import { httpApiClient } from '@/services/api/httpApiClient';

const entrada = {
  documento_titulo: 'Introdução à VCN',
  documento_conteudo: 'A '.repeat(120),
  perfil_destinatario: 'Iniciante' as const,
  formato_saida: 'Flashcards' as const,
  nicho_setor: 'Geral' as const,
  nivel_detalhe: 'Didatico' as const,
};

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  limparEstadoMock();
  configurarDuracaoJob(6000);
});
afterAll(() => server.close());

describe('handlers de adaptação', () => {
  it('cria job em 202 e conclui com pacote válido', async () => {
    configurarDuracaoJob(30);
    const criado = await httpApiClient.criarPorTexto(entrada);
    expect(criado.status).toBe('queued');

    await new Promise((r) => setTimeout(r, 60));
    const job = await httpApiClient.obterJob(criado.job_id);

    expect(job.status).toBe('succeeded');
    expect(job.resultado?.metadados.formato_gerado).toBe('Flashcards');
    expect(job.resultado?.documento.titulo).toBe(entrada.documento_titulo);
    expect(job.progresso_percentual).toBe(100);

    const pacote = await httpApiClient.obter(job.adaptacao_id!);
    expect(pacote.conteudo_adaptado.tipo).toBe('flashcards');
  });

  it('respeita limite de texto com 422 e campos', async () => {
    await expect(httpApiClient.criarPorTexto({ ...entrada, documento_conteudo: 'x' })).rejects.toMatchObject({
      status: 422,
      problema: { erro: { codigo: 'VALIDACAO' } },
    });
  });

  it('rejeita extensão inválida no upload com 415', async () => {
    const arquivo = new File(['x'], 'manual.docx');
    await expect(
      httpApiClient.criarPorArquivo({ ...entrada, documento_conteudo: undefined, arquivo } as never),
    ).rejects.toMatchObject({ status: 415, problema: { erro: { codigo: 'ARQUIVO_INVALIDO' } } });
  });

  it('cancela job em andamento e recusa cancelar finalizado', async () => {
    configurarDuracaoJob(60_000);
    const criado = await httpApiClient.criarPorTexto(entrada);
    const cancelado = await httpApiClient.cancelarJob(criado.job_id);
    expect(cancelado.status).toBe('cancelled');
    await expect(httpApiClient.cancelarJob(criado.job_id)).rejects.toMatchObject({ status: 409 });
  });

  it('pagina e filtra o histórico', async () => {
    semearHistorico(14);
    const pagina1 = await httpApiClient.listar({ pagina: 1, tamanho_pagina: 12 });
    expect(pagina1.itens).toHaveLength(12);
    expect(pagina1.total_paginas).toBe(2);
    const soQuiz = await httpApiClient.listar({ formato: 'Quiz' });
    expect(soQuiz.itens.every((i) => i.formato_gerado === 'Quiz')).toBe(true);
  });

  it('exporta csv só para flashcards', async () => {
    configurarDuracaoJob(10);
    const criado = await httpApiClient.criarPorTexto({ ...entrada, formato_saida: 'ResumoExecutivo' });
    await new Promise((r) => setTimeout(r, 30));
    const job = await httpApiClient.obterJob(criado.job_id);
    await expect(httpApiClient.exportar(job.adaptacao_id!, 'csv')).rejects.toMatchObject({ status: 409 });
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/mocks`
Expected: FAIL — fixtures e handlers ausentes.

- [ ] **Step 3: Criar as quatro fixtures**

`src/mocks/fixtures/flashcards-vcn-iniciante.json`:

```json
{
  "adaptacao_id": "01JAVCNFLCARD00000000001",
  "status": "sucesso",
  "criado_em": "2026-10-21T14:02:11Z",
  "documento": { "titulo": "Introdução à Arquitetura de Redes VCN na OCI", "origem": "texto" },
  "metadados": {
    "perfil_aplicado": "Iniciante",
    "formato_gerado": "Flashcards",
    "nivel_detalhe_aplicado": "Didatico",
    "nicho_setor_aplicado": "Geral",
    "tempo_estimado_estudo_minutos": 5,
    "conceitos_chave": ["VCN", "Sub-redes", "Internet Gateway", "Security Lists", "NAT Gateway"]
  },
  "conteudo_adaptado": {
    "tipo": "flashcards",
    "titulo": "Dominando Redes na Nuvem (VCN) do Zero",
    "introducao_contextualizada": "Imagine a VCN como o seu próprio bairro particular e seguro dentro da nuvem da Oracle, onde você decide quem entra e quem sai.",
    "itens": [
      { "frente": "O que é uma VCN na Oracle Cloud?", "verso": "É a sua rede virtual privada e personalizada dentro da nuvem da Oracle, funcionando como a infraestrutura de rede da sua empresa.", "dica_didatica": "Pense nela como o terreno cercado onde seus servidores moram." },
      { "frente": "Para que servem as Security Lists?", "verso": "São porteiros virtuais com listas de regras que definem exatamente que tipo de tráfego pode entrar ou sair da sua rede.", "dica_didatica": "Regras de entrada são ingress e regras de saída são egress." },
      { "frente": "O que é uma sub-rede pública?", "verso": "É uma subdivisão da VCN cujo tráfego pode chegar à internet por meio de um Internet Gateway." },
      { "frente": "O que é uma sub-rede privada?", "verso": "É uma subdivisão sem rota direta para a internet, usada para bancos de dados e serviços internos." },
      { "frente": "O que faz o Internet Gateway?", "verso": "Conecta a VCN à internet, permitindo tráfego de entrada e saída para recursos públicos." },
      { "frente": "O que faz o NAT Gateway?", "verso": "Permite que recursos em sub-redes privadas iniciem conexões para a internet sem ficarem expostos." },
      { "frente": "O que é uma tabela de roteamento?", "verso": "É o mapa que decide para onde o tráfego de cada sub-rede deve seguir." },
      { "frente": "O que significa ingress e egress?", "verso": "Ingress é tráfego que entra na rede; egress é tráfego que sai dela." }
    ]
  },
  "avaliacao_qualidade": {
    "ancoragem_fonte_score": 0.98,
    "clareza_pedagogica": "Alta",
    "observacoes": "Linguagem ajustada com analogias para público iniciante, sem jargões excessivos."
  },
  "armazenamento_oci": {
    "bucket": "novamente-conteudos-educativos",
    "objeto_id": "novamente-introducao-a-arquitetura-de-redes-vcn-na-oci-iniciante-flashcards-01javcnf.json",
    "status_upload": "concluido"
  }
}
```

`src/mocks/fixtures/quiz-vcn-desenvolvedor.json`:

```json
{
  "adaptacao_id": "01JAVCNQUIZ000000000002",
  "status": "sucesso",
  "criado_em": "2026-10-21T14:10:00Z",
  "documento": { "titulo": "Introdução à Arquitetura de Redes VCN na OCI", "origem": "upload", "nome_arquivo": "vcn-oci.md", "tamanho_bytes": 4821 },
  "metadados": {
    "perfil_aplicado": "Desenvolvedor",
    "formato_gerado": "Quiz",
    "nivel_detalhe_aplicado": "Tecnico",
    "nicho_setor_aplicado": "Geral",
    "tempo_estimado_estudo_minutos": 8,
    "conceitos_chave": ["VCN", "CIDR", "Security List", "Route Table", "NAT Gateway", "Service Gateway"]
  },
  "conteudo_adaptado": {
    "tipo": "quiz",
    "titulo": "VCN na prática: roteamento e isolamento",
    "introducao_contextualizada": "Seis perguntas para validar decisões de rede antes de subir uma carga na OCI.",
    "itens": [
      { "pergunta": "Qual componente permite acesso à internet a partir de uma sub-rede privada sem expor os recursos?", "opcoes": ["Internet Gateway", "NAT Gateway", "Service Gateway", "Dynamic Routing Gateway"], "resposta_correta": 1, "explicacao": "O NAT Gateway faz tradução de endereço para tráfego iniciado de dentro da sub-rede privada." },
      { "pergunta": "Onde as regras de firewall de uma sub-rede são aplicadas?", "opcoes": ["Security Lists associadas à sub-rede", "Tabela de roteamento", "Internet Gateway", "Bucket do Object Storage"], "resposta_correta": 0, "explicacao": "Security Lists são associadas à sub-rede e valem para todas as VNICs nela." },
      { "pergunta": "Uma tabela de roteamento define o destino do tráfego com base em quê?", "opcoes": ["No nome do bucket", "No CIDR de destino", "No tamanho do arquivo", "Na versão do SDK"], "resposta_correta": 1, "explicacao": "Cada regra casa um prefixo CIDR de destino com um gateway ou alvo." },
      { "pergunta": "Para acessar o Object Storage sem passar pela internet, o gateway indicado é:", "opcoes": ["NAT Gateway", "Internet Gateway", "Service Gateway", "Local Peering Gateway"], "resposta_correta": 2, "explicacao": "O Service Gateway dá acesso privado a serviços da OCI, incluindo Object Storage." },
      { "pergunta": "Duas VCNs que precisam se comunicar de forma privada usam:", "opcoes": ["Local Peering Gateway", "Internet Gateway", "Security List", "NAT Gateway"], "resposta_correta": 0, "explicacao": "O Local Peering Gateway conecta VCNs na mesma região sem tráfego público." },
      { "pergunta": "Qual é o efeito de uma regra egress ausente em uma Security List?", "opcoes": ["Nada, egress é opcional", "Todo tráfego de saída é negado", "O tráfego é roteado pelo NAT", "O bucket fica público"], "resposta_correta": 1, "explicacao": "Security Lists são stateful apenas para conexões estabelecidas; sem regra egress, novas saídas são negadas." }
    ]
  },
  "avaliacao_qualidade": {
    "ancoragem_fonte_score": 0.94,
    "clareza_pedagogica": "Alta",
    "observacoes": "Questões focadas em decisão de arquitetura, com justificativa técnica em cada alternativa correta."
  },
  "armazenamento_oci": {
    "bucket": "novamente-conteudos-educativos",
    "objeto_id": "novamente-introducao-a-arquitetura-de-redes-vcn-na-oci-desenvolvedor-quiz-01javcnqu.json",
    "status_upload": "concluido"
  }
}
```

`src/mocks/fixtures/tutorial-vcn-lider.json`:

```json
{
  "adaptacao_id": "01JAVCNTUTO000000000003",
  "status": "sucesso",
  "criado_em": "2026-10-21T14:20:00Z",
  "documento": { "titulo": "Introdução à Arquitetura de Redes VCN na OCI", "origem": "upload", "nome_arquivo": "vcn-oci.pdf", "tamanho_bytes": 184320 },
  "metadados": {
    "perfil_aplicado": "LiderTecnico",
    "formato_gerado": "Tutorial",
    "nivel_detalhe_aplicado": "Tecnico",
    "nicho_setor_aplicado": "Geral",
    "tempo_estimado_estudo_minutos": 12,
    "conceitos_chave": ["Topologia", "Segmentação", "Roteamento", "Security Lists", "Peering"]
  },
  "conteudo_adaptado": {
    "tipo": "markdown",
    "titulo": "Desenhando uma VCN pronta para produção",
    "introducao_contextualizada": "Um roteiro de decisões para sair do diagrama inicial e chegar a uma topologia que aguenta crescimento, auditoria e isolamento.",
    "itens": "## 1. Defina o bloco CIDR antes de criar recursos\n\nEscolha um bloco que não colida com a rede on-premise. Um /16 dá espaço para sub-redes /24 sem retrabalho.\n\n## 2. Separe camadas em sub-redes distintas\n\nAplique uma sub-rede pública apenas para load balancers e bastion. Aplicação e banco ficam em sub-redes privadas.\n\n## 3. Roteie por intenção\n\nSub-redes públicas usam Internet Gateway. Sub-redes privadas usam NAT Gateway para saída e Service Gateway para Object Storage.\n\n## 4. Feche por padrão\n\nSecurity Lists começam negando tudo. Abra porta e origem específicas, com justificativa registrada no repositório de infraestrutura.\n\n## 5. Planeje o crescimento\n\nReserve faixas para peering com outras VCNs e para expansão regional. Documente o mapa de CIDRs junto do código.\n\n## 6. Verifique antes de promover\n\nSimule o fluxo com um recurso de teste em cada sub-rede e confirme que nenhum caminho inesperado para a internet existe."
  },
  "avaliacao_qualidade": {
    "ancoragem_fonte_score": 0.96,
    "clareza_pedagogica": "Alta",
    "observacoes": "Foco em decisões e trade-offs, sem repetir a introdução conceitual."
  },
  "armazenamento_oci": {
    "bucket": "novamente-conteudos-educativos",
    "objeto_id": "novamente-introducao-a-arquitetura-de-redes-vcn-na-oci-lider-tecnico-tutorial-01javcntut.json",
    "status_upload": "concluido"
  }
}
```

`src/mocks/fixtures/resumo-vcn-gestor.json`:

```json
{
  "adaptacao_id": "01JAVCNRESU000000000004",
  "status": "sucesso",
  "criado_em": "2026-10-21T14:30:00Z",
  "documento": { "titulo": "Introdução à Arquitetura de Redes VCN na OCI", "origem": "texto" },
  "metadados": {
    "perfil_aplicado": "Gestor",
    "formato_gerado": "ResumoExecutivo",
    "nivel_detalhe_aplicado": "Executivo",
    "nicho_setor_aplicado": "Geral",
    "tempo_estimado_estudo_minutos": 3,
    "conceitos_chave": ["Custo", "Isolamento", "Conformidade", "Escalabilidade", "Risco operacional"]
  },
  "conteudo_adaptado": {
    "tipo": "markdown",
    "titulo": "VCN em três minutos: o que a liderança precisa decidir",
    "introducao_contextualizada": "A rede na nuvem é uma decisão de negócio: define exposição de dados, custo de tráfego e velocidade de entrega.",
    "itens": "## O que é\n\nA VCN é a rede privada da empresa dentro da Oracle Cloud. Todo recurso nasce conectado a ela.\n\n## Por que importa\n\nIsolamento mal definido vira incidente de segurança; topologia confusa vira atraso de entrega e custo de tráfego inesperado.\n\n## Decisões que sobem para a liderança\n\n- **Exposição:** o que fica público e o que fica privado.\n- **Conformidade:** trilha de auditoria das regras de firewall.\n- **Custo:** tráfego entre zonas e uso de NAT Gateway.\n- **Escalabilidade:** reserva de faixas para novas unidades de negócio.\n\n## Próximo passo\n\nAprovar o mapa de sub-redes e o dono do repositório de infraestrutura, com revisão trimestral das regras de acesso."
  },
  "avaliacao_qualidade": {
    "ancoragem_fonte_score": 0.99,
    "clareza_pedagogica": "Alta",
    "observacoes": "Sem jargão de implementação; foco em impacto, risco e decisão."
  },
  "armazenamento_oci": {
    "bucket": "novamente-conteudos-educativos",
    "objeto_id": "novamente-introducao-a-arquitetura-de-redes-vcn-na-oci-gestor-resumo-executivo-01javcnres.json",
    "status_upload": "concluido"
  }
}
```

- [ ] **Step 4: Implementar o estado dos jobs e os handlers**

`src/mocks/estadoJobs.ts`:

```ts
import type { AdaptacaoPacote, AdaptacaoResumo, EtapaJob, JobResposta } from '@/types/novamente';
import { ETAPAS } from '@/lib/constants';
import flashcards from './fixtures/flashcards-vcn-iniciante.json';
import quiz from './fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from './fixtures/tutorial-vcn-lider.json';
import resumo from './fixtures/resumo-vcn-gestor.json';

interface Registro {
  job: JobResposta;
  pacote: AdaptacaoPacote;
  inicio: number;
  duracao: number;
}

const jobs = new Map<string, Registro>();
const pacotes = new Map<string, AdaptacaoPacote>();
let duracaoPadrao = 6000;
let sequencia = 0;

const FAIXAS = [20, 35, 55, 80, 90, 100];

export function configurarDuracaoJob(ms: number) {
  duracaoPadrao = ms;
}

function agoraIso() {
  return new Date().toISOString();
}

export function novoId(): string {
  sequencia += 1;
  return `01JMOCK${String(sequencia).padStart(18, '0')}`;
}

export function criarJob(pacote: AdaptacaoPacote, duracao = duracaoPadrao): JobResposta {
  const job: JobResposta = {
    job_id: novoId(),
    status: 'queued',
    etapa_atual: null,
    etapas_concluidas: [],
    progresso_percentual: 0,
    iniciado_em: agoraIso(),
    atualizado_em: agoraIso(),
  };
  jobs.set(job.job_id, { job, pacote, inicio: Date.now(), duracao });
  return structuredClone(job);
}

function avancar(registro: Registro): JobResposta {
  if (registro.job.status === 'succeeded' || registro.job.status === 'failed' || registro.job.status === 'cancelled') {
    return structuredClone(registro.job);
  }

  const razao = Math.min(1, (Date.now() - registro.inicio) / registro.duracao);
  const indice = Math.min(ETAPAS.length - 1, Math.floor(razao * ETAPAS.length));
  const progresso = razao >= 1 ? 100 : FAIXAS[indice];

  registro.job = {
    ...registro.job,
    status: razao >= 1 ? 'succeeded' : 'running',
    etapa_atual: razao >= 1 ? null : (ETAPAS[indice] as EtapaJob),
    etapas_concluidas: razao >= 1 ? [...ETAPAS] : ETAPAS.slice(0, indice),
    progresso_percentual: progresso,
    mensagem: razao >= 1 ? undefined : `Etapa: ${ETAPAS[indice]}`,
    atualizado_em: agoraIso(),
    ...(razao >= 1 ? { adaptacao_id: registro.pacote.adaptacao_id, resultado: registro.pacote } : {}),
  };

  if (razao >= 1) pacotes.set(registro.pacote.adaptacao_id, registro.pacote);
  return structuredClone(registro.job);
}

export function obterJob(jobId: string): JobResposta | undefined {
  const registro = jobs.get(jobId);
  if (!registro) return undefined;
  return avancar(registro);
}

export function cancelarJob(jobId: string): JobResposta | 'finalizado' | undefined {
  const registro = jobs.get(jobId);
  if (!registro) return undefined;
  if (['succeeded', 'failed', 'cancelled'].includes(registro.job.status)) return 'finalizado';
  registro.job = { ...registro.job, status: 'cancelled', etapa_atual: null, atualizado_em: agoraIso() };
  return structuredClone(registro.job);
}

export function registrarPacote(pacote: AdaptacaoPacote) {
  pacotes.set(pacote.adaptacao_id, pacote);
}

export function obterPacote(id: string): AdaptacaoPacote | undefined {
  return pacotes.get(id);
}

export function listarPacotes(): AdaptacaoPacote[] {
  return [...pacotes.values()].sort((a, b) => Date.parse(b.criado_em) - Date.parse(a.criado_em));
}

export function resumir(pacote: AdaptacaoPacote): AdaptacaoResumo {
  return {
    adaptacao_id: pacote.adaptacao_id,
    criado_em: pacote.criado_em,
    documento: pacote.documento,
    perfil_aplicado: pacote.metadados.perfil_aplicado,
    formato_gerado: pacote.metadados.formato_gerado,
    nivel_detalhe_aplicado: pacote.metadados.nivel_detalhe_aplicado,
    tempo_estimado_estudo_minutos: pacote.metadados.tempo_estimado_estudo_minutos,
    ancoragem_fonte_score: pacote.avaliacao_qualidade.ancoragem_fonte_score,
    status_upload: pacote.armazenamento_oci.status_upload,
    conceitos_chave: pacote.metadados.conceitos_chave.slice(0, 6),
  };
}

export function semearHistorico(quantidade: number) {
  const bases = [flashcards, quiz, tutorial, resumo] as unknown as AdaptacaoPacote[];
  for (let i = 0; i < quantidade; i += 1) {
    const base = structuredClone(bases[i % bases.length]);
    base.adaptacao_id = `01JSEED${String(i).padStart(19, '0')}`;
    base.criado_em = new Date(Date.now() - (i + 1) * 3_600_000).toISOString();
    base.documento = { ...base.documento, titulo: `Manual de exemplo ${i + 1}` };
    pacotes.set(base.adaptacao_id, base);
  }
}

export function limparEstadoMock() {
  jobs.clear();
  pacotes.clear();
  sequencia = 0;
  duracaoPadrao = 6000;
}
```

`src/mocks/handlers/adaptacoes.ts`:

```ts
import { http, HttpResponse } from 'msw';
import flashcards from '../fixtures/flashcards-vcn-iniciante.json';
import quiz from '../fixtures/quiz-vcn-desenvolvedor.json';
import tutorial from '../fixtures/tutorial-vcn-lider.json';
import resumo from '../fixtures/resumo-vcn-gestor.json';
import { AdaptacaoInputSchema, AdaptacaoUploadInputSchema } from '@/types/schemas';
import type { AdaptacaoInput, AdaptacaoPacote, FormatoSaida } from '@/types/novamente';
import { criarJob, listarPacotes, obterPacote, registrarPacote, resumir as resumirPacote } from '../estadoJobs';
import { nomeArquivoPacote } from '@/lib/formatadores';

const POR_FORMATO: Record<FormatoSaida, unknown> = {
  Flashcards: flashcards,
  Quiz: quiz,
  Tutorial: tutorial,
  ResumoExecutivo: resumo,
};

function problemas(campos: Record<string, string>) {
  return HttpResponse.json(
    { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos } },
    { status: 422 },
  );
}

let contadorPacotes = 0;

function montarPacote(entrada: AdaptacaoInput, extra: Partial<AdaptacaoPacote['documento']> = {}): AdaptacaoPacote {
  const base = structuredClone(POR_FORMATO[entrada.formato_saida]) as AdaptacaoPacote;
  contadorPacotes += 1;
  const id = `01J${Date.now().toString(36).toUpperCase()}${String(contadorPacotes).padStart(12, '0')}`
    .toUpperCase()
    .slice(0, 26);
  const pacote: AdaptacaoPacote = {
    ...base,
    adaptacao_id: id,
    criado_em: new Date().toISOString(),
    documento: { titulo: entrada.documento_titulo, origem: 'texto', ...extra },
    metadados: {
      ...base.metadados,
      perfil_aplicado: entrada.perfil_destinatario,
      formato_gerado: entrada.formato_saida,
      nivel_detalhe_aplicado: entrada.nivel_detalhe,
      nicho_setor_aplicado: entrada.nicho_setor,
    },
  };
  return {
    ...pacote,
    armazenamento_oci: { ...pacote.armazenamento_oci, objeto_id: nomeArquivoPacote(pacote) },
  };
}

export const handlersAdaptacoes = [
  http.post('*/api/v1/adaptacoes', async ({ request }) => {
    const corpo = await request.json();
    const analisado = AdaptacaoInputSchema.safeParse(corpo);
    if (!analisado.success) {
      const campos = Object.fromEntries(
        analisado.error.issues.map((i) => [i.path.join('.'), i.message]),
      );
      return problemas(campos);
    }
    const pacote = montarPacote(analisado.data);
    const job = criarJob(pacote);
    return HttpResponse.json(job, { status: 202, headers: { Location: `/api/v1/jobs/${job.job_id}` } });
  }),

  http.post('*/api/v1/adaptacoes/upload', async ({ request }) => {
    const form = await request.formData();
    const arquivo = form.get('arquivo');
    if (!(arquivo instanceof File)) {
      return problemas({ arquivo: 'Selecione um arquivo.' });
    }
    if (arquivo.size > 10 * 1024 * 1024) {
      return HttpResponse.json(
        { erro: { codigo: 'LIMITE_EXCEDIDO', mensagem: 'Arquivo acima de 10 MB.', campos: { arquivo: 'Arquivo acima de 10 MB.' } } },
        { status: 413 },
      );
    }
    if (!/\.(pdf|md|txt)$/i.test(arquivo.name)) {
      return HttpResponse.json(
        { erro: { codigo: 'ARQUIVO_INVALIDO', mensagem: 'Use um arquivo .pdf, .md ou .txt.', campos: { arquivo: 'Formato não suportado.' } } },
        { status: 415 },
      );
    }
    if (form.has('documento_conteudo')) {
      return problemas({ documento_conteudo: 'não permitido quando há arquivo' });
    }
    const entrada = {
      documento_titulo: String(form.get('documento_titulo') ?? ''),
      documento_conteudo: 'a'.repeat(200),
      perfil_destinatario: String(form.get('perfil_destinatario')),
      formato_saida: String(form.get('formato_saida')),
      nicho_setor: String(form.get('nicho_setor')),
      nivel_detalhe: String(form.get('nivel_detalhe')),
    };
    const analisado = AdaptacaoInputSchema.safeParse(entrada);
    if (!analisado.success) {
      return problemas({ documento_titulo: 'Informe um título válido.' });
    }
    const pacote = montarPacote(analisado.data, {
      origem: 'upload',
      nome_arquivo: arquivo.name,
      tamanho_bytes: arquivo.size,
    });
    const job = criarJob(pacote);
    return HttpResponse.json(job, { status: 202, headers: { Location: `/api/v1/jobs/${job.job_id}` } });
  }),

  http.get('*/api/v1/adaptacoes', ({ request }) => {
    const url = new URL(request.url);
    const pagina = Math.max(1, Number(url.searchParams.get('pagina') ?? 1));
    const tamanho = Math.min(50, Math.max(1, Number(url.searchParams.get('tamanho_pagina') ?? 12)));
    const formato = url.searchParams.get('formato');
    const perfil = url.searchParams.get('perfil');
    const q = (url.searchParams.get('q') ?? '').toLowerCase();

    const todos = listarPacotes()
      .map((p) => ({ p, resumo: resumirPacote(p) }))
      .filter(({ resumo }) => (formato ? resumo.formato_gerado === formato : true))
      .filter(({ resumo }) => (perfil ? resumo.perfil_aplicado === perfil : true))
      .filter(({ resumo }) =>
        q ? resumo.documento.titulo.toLowerCase().includes(q) || resumo.conceitos_chave.join(' ').toLowerCase().includes(q) : true,
      )
      .sort((a, b) => Date.parse(b.resumo.criado_em) - Date.parse(a.resumo.criado_em));

    const inicio = (pagina - 1) * tamanho;
    return HttpResponse.json({
      itens: todos.slice(inicio, inicio + tamanho).map(({ resumo }) => resumo),
      pagina,
      tamanho_pagina: tamanho,
      total: todos.length,
      total_paginas: Math.ceil(todos.length / tamanho),
    });
  }),

  http.get('*/api/v1/adaptacoes/:id', ({ params }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) {
      return HttpResponse.json(
        { erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } },
        { status: 404 },
      );
    }
    return HttpResponse.json(pacote);
  }),

  http.get('*/api/v1/adaptacoes/:id/download', ({ params }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) {
      return HttpResponse.json(
        { erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } },
        { status: 404 },
      );
    }
    return HttpResponse.json(pacote, {
      headers: { 'Content-Disposition': `attachment; filename="${pacote.adaptacao_id}.json"` },
    });
  }),

  http.get('*/api/v1/adaptacoes/:id/exportacao', ({ params, request }) => {
    const pacote = obterPacote(String(params.id));
    if (!pacote) {
      return HttpResponse.json(
        { erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } },
        { status: 404 },
      );
    }
    const formato = new URL(request.url).searchParams.get('formato');
    if (formato === 'csv') {
      if (pacote.conteudo_adaptado.tipo !== 'flashcards') {
        return HttpResponse.json(
          { erro: { codigo: 'FORMATO_INCOMPATIVEL', mensagem: 'CSV está disponível apenas para Flashcards.' } },
          { status: 409 },
        );
      }
      const linhas = ['frente;verso;dica'];
      pacote.conteudo_adaptado.itens.forEach((i) => linhas.push(`"${i.frente}";"${i.verso}";"${i.dica_didatica ?? ''}"`));
      return new HttpResponse(linhas.join('\n'), { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
    }
    if (formato === 'md') {
      const itens = pacote.conteudo_adaptado;
      const corpo =
        itens.tipo === 'markdown'
          ? itens.itens
          : itens.tipo === 'flashcards'
            ? itens.itens.map((i) => `### ${i.frente}\n\n${i.verso}`).join('\n\n')
            : itens.itens.map((q) => `### ${q.pergunta}\n\n${q.opcoes.map((o, n) => `${n + 1}. ${o}`).join('\n')}\n\n_${q.explicacao}_`).join('\n\n');
      return new HttpResponse(`# ${itens.titulo}\n\n${itens.introducao_contextualizada}\n\n${corpo}\n`, {
        headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
      });
    }
    if (formato === 'pdf') {
      return new HttpResponse('%PDF-1.4\n% mock\n', { headers: { 'Content-Type': 'application/pdf' } });
    }
    return HttpResponse.json(
      { erro: { codigo: 'FORMATO_DESCONHECIDO', mensagem: 'Formato de exportação desconhecido.' } },
      { status: 400 },
    );
  }),
];

// Semeia o histórico com um pacote já concluído, para a demo nunca abrir vazia.
registrarPacote(flashcards as unknown as AdaptacaoPacote);
```

`src/mocks/handlers/jobs.ts`:

```ts
import { http, HttpResponse } from 'msw';
import { cancelarJob, obterJob } from '../estadoJobs';

export const handlersJobs = [
  http.get('*/api/v1/jobs/:id', ({ params }) => {
    const job = obterJob(String(params.id));
    if (!job) {
      return HttpResponse.json(
        { erro: { codigo: 'JOB_NAO_ENCONTRADO', mensagem: 'Geração não encontrada.' } },
        { status: 404 },
      );
    }
    return HttpResponse.json(job);
  }),

  http.delete('*/api/v1/jobs/:id', ({ params }) => {
    const resultado = cancelarJob(String(params.id));
    if (!resultado) {
      return HttpResponse.json(
        { erro: { codigo: 'JOB_NAO_ENCONTRADO', mensagem: 'Geração não encontrada.' } },
        { status: 404 },
      );
    }
    if (resultado === 'finalizado') {
      return HttpResponse.json(
        { erro: { codigo: 'JOB_FINALIZADO', mensagem: 'Esta geração já terminou.' } },
        { status: 409 },
      );
    }
    return HttpResponse.json(resultado);
  }),
];
```

`src/mocks/handlers/oci.ts`:

```ts
import { http, HttpResponse } from 'msw';

export const handlersOci = [
  http.get('*/api/v1/oci/status', () =>
    HttpResponse.json({
      configurado: true,
      bucket: 'novamente-conteudos-educativos',
      regiao: 'sa-saopaulo-1',
      total_objetos: 4,
      bytes_armazenados: 412_000,
      ultimo_upload_em: new Date().toISOString(),
      verificado_em: new Date().toISOString(),
    }),
  ),
];
```

`src/mocks/handlers/health.ts`:

```ts
import { http, HttpResponse } from 'msw';

export const handlersHealth = [
  http.get('*/api/v1/health', () =>
    HttpResponse.json({
      status: 'ok',
      versao: '0.1.0-mock',
      oci: 'ok',
      llm: 'ok',
      verificado_em: new Date().toISOString(),
    }),
  ),
];
```

`src/mocks/handlers/index.ts`:

```ts
import { handlersAdaptacoes } from './adaptacoes';
import { handlersJobs } from './jobs';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [...handlersAdaptacoes, ...handlersJobs, ...handlersOci, ...handlersHealth];
```

`src/mocks/server.ts`:

```ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);
```

`src/mocks/browser.ts`:

```ts
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

- [ ] **Step 5: Ligar o MSW no app e no Storybook**

Gerar o service worker do MSW:

```bash
npx msw init public --save
```

`src/mocks/MockProvider.tsx`:

```tsx
'use client';

import { useEffect, useState } from 'react';

const MOCK_ATIVO = process.env.NEXT_PUBLIC_API_MOCK === '1';

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [pronto, setPronto] = useState(!MOCK_ATIVO);

  useEffect(() => {
    if (pronto) return;
    let cancelado = false;
    import('./browser').then(async ({ worker }) => {
      await worker.start({ onUnhandledRequest: 'bypass' });
      if (!cancelado) setPronto(true);
    });
    return () => {
      cancelado = true;
    };
  }, [pronto]);

  if (!pronto) return <div className="p-8 text-sm text-[var(--fg-muted)]">Preparando ambiente de demonstração…</div>;
  return <>{children}</>;
}
```

`src/app/providers.tsx` — envolver com `MockProvider`:

```tsx
return (
  <MockProvider>
    <ApiProvider>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  </MockProvider>
);
```

`.storybook/preview.ts` — substituir por:

```ts
import type { Preview } from '@storybook/nextjs-vite';
import { initialize, mswLoader } from 'msw-storybook-addon';
import { handlers } from '../src/mocks/handlers';
import '../src/app/globals.css';

initialize({ onUnhandledRequest: 'bypass' });

const preview: Preview = {
  loaders: [mswLoader],
  parameters: {
    msw: { handlers },
    backgrounds: { disable: true },
  },
};

export default preview;
```

Se o Storybook gerar `@storybook/react` em vez de `@storybook/nextjs`, ajuste o import do tipo `Preview` para o pacote instalado.

- [ ] **Step 6: Rodar e ver passar**

Run: `npm test -- src/mocks`
Expected: PASS — 5 testes de fixture/contrato e 6 de handlers.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "test(frontend): MSW, fixtures validadas e ciclo completo de job mockado"
```

---

### Task 6: Formulário de ingestão

**Files:**
- Create: `src/components/ui/Dropzone.tsx`, `src/components/forms/campos/ParametrosFields.tsx`, `src/components/forms/campos/FonteDocumento.tsx`, `src/components/forms/IngestionForm.tsx`, `src/features/adaptations/useCreateAdaptation.ts`, `src/features/adaptations/useAdaptationForm.ts`
- Modify: `src/lib/mensagens.ts` (novas chaves de erro e ação)
- Test: `src/components/ui/Dropzone.test.tsx`, `src/components/forms/IngestionForm.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `ErroApi`, `mensagemDoErro`, `LIMITES`, `PERFIS`, `FORMATOS`, `NICHOS`, `NIVEIS`, `M`, `formatarBytes`.
- Produces: `Dropzone({ arquivo, aoSelecionar, erro })`; `useCreateAdaptation()` → `{ criar, repetir, cancelar, enviando, job }`; `useAdaptationForm(onCriado)` → `{ form, aba, trocarAba, enviar, enviando, erroGeral, dispararCenario }`; `IngestionForm({ onCriado, desabilitado })`; tipos `ValoresFormulario` e `Cenario`.

- [ ] **Step 1: Escrever os testes que falham**

`src/components/ui/Dropzone.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Dropzone } from './Dropzone';

describe('Dropzone', () => {
  it('mostra nome e tamanho do arquivo selecionado', async () => {
    const aoSelecionar = vi.fn();
    render(<Dropzone arquivo={new File(['abc'], 'manual.pdf')} aoSelecionar={aoSelecionar} />);
    expect(screen.getByText('manual.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remover arquivo/i })).toBeInTheDocument();
  });

  it('entrega o arquivo escolhido pelo input', async () => {
    const aoSelecionar = vi.fn();
    render(<Dropzone arquivo={null} aoSelecionar={aoSelecionar} />);
    const arquivo = new File(['abc'], 'doc.md', { type: 'text/markdown' });
    await userEvent.upload(screen.getByLabelText(/arraste o arquivo/i), arquivo);
    expect(aoSelecionar).toHaveBeenCalledWith(arquivo);
  });

  it('anuncia erro com role alert', () => {
    render(<Dropzone arquivo={null} aoSelecionar={vi.fn()} erro="Extensão inválida." />);
    expect(screen.getByRole('alert')).toHaveTextContent('Extensão inválida.');
  });
});
```

`src/components/forms/IngestionForm.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { IngestionForm } from './IngestionForm';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { JobResposta } from '@/types/novamente';

const job: JobResposta = {
  job_id: 'j1',
  status: 'queued',
  etapa_atual: null,
  etapas_concluidas: [],
  progresso_percentual: 0,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
};

function renderizar(criarPorTexto = vi.fn().mockResolvedValue(job), criarPorArquivo = vi.fn().mockResolvedValue(job)) {
  const api = { criarPorTexto, criarPorArquivo } as unknown as NovaMenteApi;
  const onCriado = vi.fn();
  render(
    <ApiProvider client={api}>
      <IngestionForm onCriado={onCriado} />
    </ApiProvider>,
  );
  return { criarPorTexto, criarPorArquivo, onCriado };
}

const titulo = () => screen.getByLabelText(/título do documento/i);
const texto = () => screen.getByLabelText(/conteúdo técnico/i);

describe('IngestionForm', () => {
  it('bloqueia envio com título curto e texto curto', async () => {
    const { criarPorTexto } = renderizar();
    await userEvent.type(titulo(), 'VC');
    fireEvent.change(texto(), { target: { value: 'curto' } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Informe um título de 3 a 150 caracteres.')).toBeInTheDocument();
    expect(screen.getByText('Mínimo de 200 caracteres.')).toBeInTheDocument();
    expect(criarPorTexto).not.toHaveBeenCalled();
  });

  it('envia o payload de texto com os parâmetros escolhidos', async () => {
    const { criarPorTexto, onCriado } = renderizar();
    await userEvent.type(titulo(), 'Introdução à VCN');
    fireEvent.change(texto(), { target: { value: 'a'.repeat(200) } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    await waitFor(() => expect(criarPorTexto).toHaveBeenCalledTimes(1));
    expect(criarPorTexto.mock.calls[0][0]).toMatchObject({
      documento_titulo: 'Introdução à VCN',
      documento_conteudo: 'a'.repeat(200),
      perfil_destinatario: 'Iniciante',
      formato_saida: 'Flashcards',
      nicho_setor: 'Geral',
      nivel_detalhe: 'Didatico',
    });
    expect(onCriado).toHaveBeenCalledWith(job, expect.any(Function));
  });

  it('preserva o título ao trocar de aba', async () => {
    renderizar();
    await userEvent.type(titulo(), 'Documento técnico');
    await userEvent.click(screen.getByRole('tab', { name: /enviar arquivo/i }));
    expect(titulo()).toHaveValue('Documento técnico');
  });

  it('rejeita extensão não suportada no upload', async () => {
    const { criarPorArquivo } = renderizar();
    await userEvent.type(titulo(), 'Manual interno');
    await userEvent.click(screen.getByRole('tab', { name: /enviar arquivo/i }));
    await userEvent.upload(
      screen.getByLabelText(/arraste o arquivo/i),
      new File(['x'], 'manual.docx'),
    );
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Use um arquivo .pdf, .md ou .txt.')).toBeInTheDocument();
    expect(criarPorArquivo).not.toHaveBeenCalled();
  });

  it('devolve erro por campo vindo do servidor', async () => {
    const criarPorTexto = vi.fn().mockRejectedValue(
      new ErroApi(
        { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Título já usado.' } } },
        422,
      ),
    );
    renderizar(criarPorTexto);
    await userEvent.type(titulo(), 'Introdução à VCN');
    fireEvent.change(texto(), { target: { value: 'a'.repeat(200) } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Título já usado.')).toBeInTheDocument();
  });

  it('conta caracteres, não bytes, no contador', async () => {
    renderizar();
    fireEvent.change(texto(), { target: { value: '😀'.repeat(50) } });
    expect(await screen.findByText('50 / 50.000')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/ui/Dropzone.test.tsx src/components/forms/IngestionForm.test.tsx`
Expected: FAIL — componentes ausentes.

- [ ] **Step 3: Acrescentar mensagens e criar o Dropzone**

`src/lib/mensagens.ts` — adicionar dentro de `formulario`, antes de `resumoErros`:

```ts
    erros: {
      titulo: 'Informe um título de 3 a 150 caracteres.',
      textoMin: 'Mínimo de 200 caracteres.',
      textoMax: 'Máximo de 50.000 caracteres.',
      arquivoObrigatorio: 'Selecione um arquivo.',
      arquivoVazio: 'O arquivo está vazio.',
      arquivoGrande: 'Arquivo acima de 10 MB.',
      arquivoTipo: 'Use um arquivo .pdf, .md ou .txt.',
    },
```

`src/components/ui/Dropzone.tsx`:

```tsx
'use client';

import { useId, useState } from 'react';
import { UploadCloud, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { M } from '@/lib/mensagens';
import { formatarBytes } from '@/lib/formatadores';
import { cn } from '@/lib/cn';

interface Props {
  arquivo: File | null;
  aoSelecionar: (arquivo: File | null) => void;
  erro?: string;
  desabilitado?: boolean;
}

export function Dropzone({ arquivo, aoSelecionar, erro, desabilitado }: Props) {
  const [arrastando, setArrastando] = useState(false);
  const id = useId();

  return (
    <div>
      <div
        data-arrastando={arrastando}
        onDragOver={(e) => {
          e.preventDefault();
          if (!desabilitado) setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          if (desabilitado) return;
          const escolhido = e.dataTransfer.files?.[0];
          if (escolhido) aoSelecionar(escolhido);
        }}
        className={cn(
          'flex min-h-[160px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-6 text-center',
          arrastando && 'border-[var(--accent)] bg-[var(--accent-muted)]',
          erro && 'border-[var(--danger)]',
        )}
      >
        {arquivo ? (
          <div className="flex w-full items-center justify-between gap-3">
            <div className="text-left">
              <p className="text-sm font-medium break-all">{arquivo.name}</p>
              <p className="text-xs text-[var(--fg-muted)]">{formatarBytes(arquivo.size)}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => aoSelecionar(null)}
              disabled={desabilitado}
            >
              <X aria-hidden className="mr-1 h-4 w-4" />
              {M.formulario.removerArquivo}
            </Button>
          </div>
        ) : (
          <label htmlFor={id} className="flex cursor-pointer flex-col items-center gap-2">
            <UploadCloud aria-hidden className="h-6 w-6 text-[var(--accent)]" />
            <span className="text-sm">{M.formulario.dropzone}</span>
            <span className="text-xs text-[var(--fg-muted)]">{M.formulario.dropzoneAjuda}</span>
          </label>
        )}
        <input
          id={id}
          type="file"
          accept=".pdf,.md,.txt"
          className="sr-only"
          disabled={desabilitado}
          onChange={(e) => {
            const escolhido = e.target.files?.[0];
            if (escolhido) aoSelecionar(escolhido);
          }}
        />
      </div>
      {erro && (
        <p role="alert" className="mt-2 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Rodar e ver o Dropzone passar**

Run: `npm test -- src/components/ui/Dropzone.test.tsx`
Expected: PASS (3 testes).

- [ ] **Step 5: Hooks de criação e formulário**

`src/features/adaptations/useCreateAdaptation.ts`:

```ts
'use client';

import { useCallback, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';import type { AdaptacaoInput, AdaptacaoUploadInput, JobResposta } from '@/types/novamente';

export type Envio = AdaptacaoInput | AdaptacaoUploadInput;

export function useCreateAdaptation() {
  const api = useApi();
  const [enviando, setEnviando] = useState(false);
  const [job, setJob] = useState<JobResposta | null>(null);
  const ultimoEnvioRef = useRef<Envio | null>(null);

  const criar = useCallback(
    async (entrada: Envio) => {
      setEnviando(true);
      try {
        const resposta =
          'arquivo' in entrada ? await api.criarPorArquivo(entrada) : await api.criarPorTexto(entrada);
        ultimoEnvioRef.current = entrada;
        setJob(resposta);
        return resposta;
      } finally {
        setEnviando(false);
      }
    },
    [api],
  );

  const repetir = useCallback(async () => {
    const entrada = ultimoEnvioRef.current;
    if (!entrada) return null;
    return criar(entrada);
  }, [criar]);

  const cancelar = useCallback(async () => {
    if (!job) return;
    try {
      await api.cancelarJob(job.job_id);
    } finally {
      setJob(null);
    }
  }, [api, job]);

  return { criar, repetir, cancelar, enviando, job };
}
```

`src/features/adaptations/useAdaptationForm.ts`:

```ts
'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';
import type { AdaptacaoInput, AdaptacaoUploadInput, FormatoSaida, JobResposta, NivelDetalhe, PerfilDestinatario } from '@/types/novamente';
import { useCreateAdaptation, type Envio } from './useCreateAdaptation';

const FormularioSchema = z
  .object({
    modo: z.enum(['texto', 'arquivo']),
    documento_titulo: z.string(),
    documento_conteudo: z.string().optional(),
    arquivo: z.custom<File>().nullable().optional(),
    perfil_destinatario: z.enum(['Iniciante', 'Desenvolvedor', 'LiderTecnico', 'Gestor']),
    formato_saida: z.enum(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']),
    nicho_setor: z.enum(['Fintech', 'Saude', 'Ecommerce', 'Geral']),
    nivel_detalhe: z.enum(['Didatico', 'Tecnico', 'Executivo']),
  })
  .superRefine((valores, ctx) => {
    const titulo = valores.documento_titulo.trim();
    if (titulo.length < LIMITES.tituloMin || titulo.length > LIMITES.tituloMax) {
      ctx.addIssue({ code: 'custom', path: ['documento_titulo'], message: M.formulario.erros.titulo });
    }
    if (valores.modo === 'texto') {
      const texto = (valores.documento_conteudo ?? '').trim();
      if (texto.length < LIMITES.textoMin) {
        ctx.addIssue({ code: 'custom', path: ['documento_conteudo'], message: M.formulario.erros.textoMin });
      } else if (texto.length > LIMITES.textoMax) {
        ctx.addIssue({ code: 'custom', path: ['documento_conteudo'], message: M.formulario.erros.textoMax });
      }
    } else {
      if (!valores.arquivo) {
        ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoObrigatorio });
      } else {
        if (valores.arquivo.size === 0) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoVazio });
        }
        if (valores.arquivo.size > LIMITES.arquivoMaxBytes) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoGrande });
        }
        if (!/\.(pdf|md|txt)$/i.test(valores.arquivo.name)) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoTipo });
        }
      }
    }
  });

export type ValoresFormulario = z.infer<typeof FormularioSchema>;
export type Aba = 'texto' | 'arquivo';

export interface Cenario {
  titulo: string;
  perfil: PerfilDestinatario;
  formato: FormatoSaida;
  nivel: NivelDetalhe;
}

const VALORES_INICIAIS: ValoresFormulario = {
  modo: 'texto',
  documento_titulo: '',
  documento_conteudo: '',
  arquivo: null,
  perfil_destinatario: 'Iniciante',
  formato_saida: 'Flashcards',
  nicho_setor: 'Geral',
  nivel_detalhe: 'Didatico',
};

function paraEnvio(valores: ValoresFormulario): Envio {
  const base = {
    documento_titulo: valores.documento_titulo.trim(),
    perfil_destinatario: valores.perfil_destinatario,
    formato_saida: valores.formato_saida,
    nicho_setor: valores.nicho_setor,
    nivel_detalhe: valores.nivel_detalhe,
  };
  return valores.modo === 'texto'
    ? ({ ...base, documento_conteudo: (valores.documento_conteudo ?? '').trim() } satisfies AdaptacaoInput)
    : ({ ...base, arquivo: valores.arquivo as File } satisfies AdaptacaoUploadInput);
}

export function useAdaptationForm(onCriado: (job: JobResposta, repetir: () => Promise<JobResposta | null>) => void) {
  const { criar, repetir, enviando } = useCreateAdaptation();
  const [aba, setAba] = useState<Aba>('texto');
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const form = useForm<ValoresFormulario>({
    resolver: zodResolver(FormularioSchema),
    mode: 'onBlur',
    defaultValues: VALORES_INICIAIS,
  });

  const mapearErro = useCallback(
    (erro: unknown) => {
      if (erro instanceof ErroApi && erro.problema.erro.campos) {
        for (const [campo, mensagem] of Object.entries(erro.problema.erro.campos)) {
          form.setError(campo as keyof ValoresFormulario, { message: mensagem });
        }
      }
      setErroGeral(mensagemDoErro(erro));
    },
    [form],
  );

  const enviarValores = useCallback(
    async (valores: ValoresFormulario) => {
      setErroGeral(null);
      try {
        const job = await criar(paraEnvio(valores));
        onCriado(job, repetir);
      } catch (erro) {
        mapearErro(erro);
      }
    },
    [criar, mapearErro, onCriado, repetir],
  );

  const enviar = form.handleSubmit(enviarValores);

  const trocarAba = useCallback(
    (nova: Aba) => {
      setAba(nova);
      setErroGeral(null);
      form.clearErrors();
      form.setValue('modo', nova);
      if (nova === 'texto') form.setValue('arquivo', null);
      else form.setValue('documento_conteudo', '');
    },
    [form],
  );

  const dispararCenario = useCallback(
    async (cenario: Cenario, documento: string) => {
      form.reset({
        ...VALORES_INICIAIS,
        modo: 'texto',
        documento_titulo: cenario.titulo,
        documento_conteudo: documento.repeat(Math.ceil(LIMITES.textoMin / documento.length) + 1),
        perfil_destinatario: cenario.perfil,
        formato_saida: cenario.formato,
        nivel_detalhe: cenario.nivel,
      });
      setAba('texto');
      const valores: ValoresFormulario = {
        ...VALORES_INICIAIS,
        modo: 'texto',
        documento_titulo: cenario.titulo,
        documento_conteudo: documento.repeat(Math.ceil(LIMITES.textoMin / documento.length) + 1),
        perfil_destinatario: cenario.perfil,
        formato_saida: cenario.formato,
        nivel_detalhe: cenario.nivel,
      };
      await enviarValores(valores);
    },
    [enviarValores, form],
  );

  return { form, aba, trocarAba, enviar, enviando, erroGeral, dispararCenario };
}
```

- [ ] **Step 6: Componentes de campo e o formulário**

`src/components/forms/campos/ParametrosFields.tsx`:

```tsx
'use client';

import type { UseFormReturn } from 'react-hook-form';
import type { ValoresFormulario } from '@/features/adaptations/useAdaptationForm';
import { PERFIS, FORMATOS, NICHOS, NIVEIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';

type Props = { form: UseFormReturn<ValoresFormulario> };

function Erro({ mensagem }: { mensagem?: string }) {
  if (!mensagem) return null;
  return (
    <p role="alert" className="mt-1 text-sm text-[var(--danger)]">
      {mensagem}
    </p>
  );
}

export function PerfilField({ form }: Props) {
  const atual = form.watch('perfil_destinatario');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoPerfil}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {PERFIS.map((perfil) => (
          <label
            key={perfil.valor}
            className={cn(
              'cursor-pointer rounded-lg border p-3 text-sm',
              atual === perfil.valor && 'border-[var(--accent)] bg-[var(--accent-muted)]',
            )}
          >
            <input type="radio" value={perfil.valor} className="sr-only" {...form.register('perfil_destinatario')} />
            <span className="block font-medium">{perfil.rotulo}</span>
            <span className="block text-xs text-[var(--fg-muted)]">{perfil.descricao}</span>
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.perfil_destinatario?.message} />
    </fieldset>
  );
}

export function FormatoField({ form }: Props) {
  const atual = form.watch('formato_saida');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoFormato}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {FORMATOS.map((formato) => (
          <label
            key={formato.valor}
            className={cn(
              'cursor-pointer rounded-lg border p-3 text-sm',
              atual === formato.valor && 'border-[var(--accent)] bg-[var(--accent-muted)]',
            )}
          >
            <input type="radio" value={formato.valor} className="sr-only" {...form.register('formato_saida')} />
            <span className="block font-medium">{formato.rotulo}</span>
            <span className="block text-xs text-[var(--fg-muted)]">{formato.descricao}</span>
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.formato_saida?.message} />
    </fieldset>
  );
}

export function NichoField({ form }: Props) {
  return (
    <div>
      <label htmlFor="nicho" className="mb-2 block text-sm font-medium">
        {M.formulario.campoNicho}
      </label>
      <select
        id="nicho"
        className="h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
        {...form.register('nicho_setor')}
      >
        {NICHOS.map((nicho) => (
          <option key={nicho.valor} value={nicho.valor}>
            {nicho.rotulo}
          </option>
        ))}
      </select>
      <Erro mensagem={form.formState.errors.nicho_setor?.message} />
    </div>
  );
}

export function NivelField({ form }: Props) {
  const atual = form.watch('nivel_detalhe');
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium">{M.formulario.campoNivel}</legend>
      <div className="flex rounded-md border p-1">
        {NIVEIS.map((nivel) => (
          <label
            key={nivel.valor}
            className={cn(
              'flex-1 cursor-pointer rounded px-2 py-1.5 text-center text-sm',
              atual === nivel.valor && 'bg-[var(--accent)] text-[var(--accent-fg)]',
            )}
          >
            <input type="radio" value={nivel.valor} className="sr-only" {...form.register('nivel_detalhe')} />
            {nivel.rotulo}
          </label>
        ))}
      </div>
      <Erro mensagem={form.formState.errors.nivel_detalhe?.message} />
    </fieldset>
  );
}
```

`src/components/forms/campos/FonteDocumento.tsx`:

```tsx
'use client';

import type { UseFormReturn } from 'react-hook-form';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dropzone } from '@/components/ui/Dropzone';
import type { Aba, ValoresFormulario } from '@/features/adaptations/useAdaptationForm';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';

export function FonteDocumento({
  form,
  aba,
  trocarAba,
  desabilitado,
}: {
  form: UseFormReturn<ValoresFormulario>;
  aba: Aba;
  trocarAba: (aba: Aba) => void;
  desabilitado?: boolean;
}) {
  const conteudo = form.watch('documento_conteudo') ?? '';
  const arquivo = form.watch('arquivo') ?? null;
  const erros = form.formState.errors;

  return (
    <Tabs value={aba} onValueChange={(v) => trocarAba(v as Aba)}>
      <TabsList>
        <TabsTrigger value="texto">{M.formulario.abaTexto}</TabsTrigger>
        <TabsTrigger value="arquivo">{M.formulario.abaArquivo}</TabsTrigger>
      </TabsList>

      <TabsContent value="texto">
        <label htmlFor="documento-conteudo" className="mb-2 block text-sm font-medium">
          {M.formulario.campoTexto}
        </label>
        <textarea
          id="documento-conteudo"
          rows={10}
          disabled={desabilitado}
          placeholder={M.formulario.placeholderTexto}
          aria-invalid={Boolean(erros.documento_conteudo)}
          aria-describedby="contador-texto"
          className="w-full rounded-md border bg-[var(--surface)] p-3 text-sm"
          {...form.register('documento_conteudo')}
        />
        <div className="mt-1 flex items-center justify-between gap-3">
          {erros.documento_conteudo ? (
            <p role="alert" className="text-sm text-[var(--danger)]">
              {erros.documento_conteudo.message}
            </p>
          ) : (
            <span />
          )}
          <p
            id="contador-texto"
            className={conteudo.length > LIMITES.textoMax * 0.9 ? 'text-xs text-[var(--warning)]' : 'text-xs text-[var(--fg-muted)]'}
          >
            {M.formulario.contador(conteudo.length, LIMITES.textoMax)}
          </p>
        </div>
      </TabsContent>

      <TabsContent value="arquivo">
        <p className="mb-2 block text-sm font-medium">{M.formulario.campoArquivo}</p>
        <Dropzone
          arquivo={arquivo}
          erro={erros.arquivo?.message}
          desabilitado={desabilitado}
          aoSelecionar={(novo) => form.setValue('arquivo', novo, { shouldValidate: true })}
        />
      </TabsContent>
    </Tabs>
  );
}
```

`src/components/forms/IngestionForm.tsx`:

```tsx
'use client';

import { useId } from 'react';
import { Button } from '@/components/ui/button';
import { useAdaptationForm } from '@/features/adaptations/useAdaptationForm';
import type { JobResposta } from '@/types/novamente';
import { M } from '@/lib/mensagens';
import { FonteDocumento } from './campos/FonteDocumento';
import { FormatoField, NivelField, NichoField, PerfilField } from './campos/ParametrosFields';

export function IngestionForm({
  onCriado,
  desabilitado,
}: {
  onCriado: (job: JobResposta, repetir: () => Promise<JobResposta | null>) => void;
  desabilitado?: boolean;
}) {
  const { form, aba, trocarAba, enviar, enviando, erroGeral } = useAdaptationForm(onCriado);
  const idTitulo = useId();
  const erros = form.formState.errors;

  return (
    <form onSubmit={enviar} noValidate aria-label={M.formulario.titulo} className="space-y-6">
      {erroGeral && (
        <div role="alert" className="rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
          {erroGeral}
        </div>
      )}

      <div>
        <label htmlFor={idTitulo} className="mb-2 block text-sm font-medium">
          {M.formulario.campoTitulo}
        </label>
        <input
          id={idTitulo}
          type="text"
          maxLength={200}
          disabled={desabilitado}
          placeholder={M.formulario.placeholderTitulo}
          aria-invalid={Boolean(erros.documento_titulo)}
          className="h-10 w-full rounded-md border bg-[var(--surface)] px-3 text-sm"
          {...form.register('documento_titulo')}
        />
        {erros.documento_titulo && (
          <p role="alert" className="mt-1 text-sm text-[var(--danger)]">
            {erros.documento_titulo.message}
          </p>
        )}
      </div>

      <FonteDocumento form={form} aba={aba} trocarAba={trocarAba} desabilitado={desabilitado} />
      <PerfilField form={form} />
      <FormatoField form={form} />
      <div className="grid gap-4 sm:grid-cols-2">
        <NichoField form={form} />
        <NivelField form={form} />
      </div>

      <Button type="submit" disabled={enviando || desabilitado} className="w-full">
        {enviando ? M.formulario.enviando : M.formulario.enviar}
      </Button>
    </form>
  );
}
```

- [ ] **Step 7: Rodar e ver passar**

Run: `npm test -- src/components/forms src/components/ui`
Expected: PASS (6 testes de formulário + 3 do Dropzone).

Se o Radix reclamar de `pointer-events` no jsdom ao clicar nas tabs, adicione em `src/test/setup.ts`:

```ts
if (!('PointerEvent' in window)) {
  // @ts-expect-error - polyfill mínimo para Radix em jsdom
  window.PointerEvent = MouseEvent;
}
```

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat(frontend): formulário de ingestão com validação zod e duas origens"
```

---

### Task 7: Job, progresso e composição da geração

**Files:**
- Create: `src/features/jobs/useAdaptationJob.ts`, `src/components/views/JobProgress.tsx`, `src/components/views/GerarView.tsx`
- Modify: `src/app/page.tsx`
- Test: `src/features/jobs/useAdaptationJob.test.tsx`, `src/components/views/JobProgress.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `useAdaptationJob`, `IngestionForm`, `ETAPAS`, `ROTULOS_ETAPA`, `M`, `Progress` (shadcn).
- Produces: `useAdaptationJob(jobId, aoConcluir, opcoes)` → `{ job, erro, carregando, estourou, perdido, cancelado }`; `JobProgress`; `GerarView`.

- [ ] **Step 1: Escrever os testes que falham**

`src/features/jobs/useAdaptationJob.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useAdaptationJob } from './useAdaptationJob';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote, JobResposta } from '@/types/novamente';

const pacote = { adaptacao_id: 'a1' } as unknown as AdaptacaoPacote;

const emAndamento = (progresso: number): JobResposta => ({
  job_id: 'j1',
  status: 'running',
  etapa_atual: 'extraindo',
  etapas_concluidas: [],
  progresso_percentual: progresso,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:12Z',
});

function montar(obterJob: NovaMenteApi['obterJob']) {
  const api = { obterJob } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </ApiProvider>
  );
  return { wrapper, client };
}

describe('useAdaptationJob', () => {
  it('polla e chama aoConcluir com o pacote', async () => {
    const respostas = [
      emAndamento(20),
      emAndamento(60),
      { ...emAndamento(100), status: 'succeeded' as const, etapa_atual: null, adaptacao_id: 'a1', resultado: pacote },
    ];
    const obterJob = vi.fn().mockImplementation(() => Promise.resolve(respostas.shift()!));
    const aoConcluir = vi.fn();
    const { wrapper } = montar(obterJob);

    renderHook(() => useAdaptationJob('j1', aoConcluir, { intervaloRapidoMs: 10 }), { wrapper });

    await waitFor(() => expect(aoConcluir).toHaveBeenCalledWith(pacote), { timeout: 3000 });
    expect(obterJob.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it('marca estourou após o timeout e para de pollar', async () => {
    const obterJob = vi.fn().mockResolvedValue(emAndamento(10));
    const { wrapper } = montar(obterJob);

    const { result } = renderHook(
      () => useAdaptationJob('j1', vi.fn(), { intervaloRapidoMs: 10, timeoutMs: 40 }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.estourou).toBe(true), { timeout: 3000 });
    const chamadas = obterJob.mock.calls.length;
    await new Promise((r) => setTimeout(r, 80));
    expect(obterJob.mock.calls.length).toBe(chamadas);
  });

  it('sinaliza job perdido quando a API responde 404', async () => {
    const obterJob = vi.fn().mockRejectedValue(
      new ErroApi({ erro: { codigo: 'JOB_NAO_ENCONTRADO', mensagem: 'sumiu' } }, 404),
    );
    const { wrapper } = montar(obterJob);

    const { result } = renderHook(() => useAdaptationJob('j1', vi.fn(), { intervaloRapidoMs: 10 }), { wrapper });

    await waitFor(() => expect(result.current.perdido).toBe(true), { timeout: 3000 });
  });
});
```

`src/components/views/JobProgress.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { JobProgress } from './JobProgress';
import type { JobResposta } from '@/types/novamente';

const job = (over: Partial<JobResposta> = {}): JobResposta => ({
  job_id: 'j1',
  status: 'running',
  etapa_atual: 'embeddings',
  etapas_concluidas: ['extraindo', 'chunking'],
  progresso_percentual: 45,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:38Z',
  ...over,
});

describe('JobProgress', () => {
  it('lista as seis etapas e marca a atual', () => {
    render(<JobProgress job={job()} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText('Extraindo texto')).toBeInTheDocument();
    expect(screen.getByText('Salvando no OCI')).toBeInTheDocument();
    expect(screen.getByText('Gerando embeddings').closest('li')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  it('nunca deixa o progresso regredir', () => {
    const { rerender } = render(
      <JobProgress job={job({ progresso_percentual: 60 })} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />,
    );
    expect(screen.getByText('60%')).toBeInTheDocument();
    rerender(<JobProgress job={job({ progresso_percentual: 30 })} estourou={false} aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.queryByText('30%')).not.toBeInTheDocument();
  });

  it('mostra falha com mensagem e request_id, e permite tentar de novo', async () => {
    const aoTentarNovamente = vi.fn();
    render(
      <JobProgress
        job={job({
          status: 'failed',
          etapa_atual: null,
          erro: { codigo: 'DOCUMENTO_ILEGIVEL', mensagem: 'PDF sem texto.', request_id: 'req-1' },
        })}
        estourou={false}
        aoCancelar={vi.fn()}
        aoTentarNovamente={aoTentarNovamente}
      />,
    );
    expect(screen.getByText('PDF sem texto.')).toBeInTheDocument();
    expect(screen.getByText(/req-1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /tentar novamente/i }));
    expect(aoTentarNovamente).toHaveBeenCalled();
  });

  it('mostra mensagem de timeout', () => {
    render(<JobProgress job={job()} estourou aoCancelar={vi.fn()} aoTentarNovamente={vi.fn()} />);
    expect(screen.getByText(/passou de 5 minutos/i)).toBeInTheDocument();
  });

  it('cancela pelo botão', async () => {
    const aoCancelar = vi.fn();
    render(<JobProgress job={job()} estourou={false} aoCancelar={aoCancelar} aoTentarNovamente={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /cancelar geração/i }));
    expect(aoCancelar).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/features/jobs src/components/views/JobProgress.test.tsx`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar o hook de job**

`src/features/jobs/useAdaptationJob.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import {
  INTERVALO_POLL_LONGO_MS,
  INTERVALO_POLL_MS,
  JANELA_POLL_RAPIDO_MS,
  LIMITE_TEMPO_JOB_MS,
} from '@/lib/constants';
import type { AdaptacaoPacote } from '@/types/novamente';

interface Opcoes {
  intervaloRapidoMs?: number;
  intervaloLongoMs?: number;
  janelaRapidaMs?: number;
  timeoutMs?: number;
}

export function useAdaptationJob(
  jobId: string | null,
  aoConcluir: (pacote: AdaptacaoPacote) => void,
  opcoes: Opcoes = {},
) {
  const api = useApi();
  const {
    intervaloRapidoMs = INTERVALO_POLL_MS,
    intervaloLongoMs = INTERVALO_POLL_LONGO_MS,
    janelaRapidaMs = JANELA_POLL_RAPIDO_MS,
    timeoutMs = LIMITE_TEMPO_JOB_MS,
  } = opcoes;

  const inicioRef = useRef(0);
  const aoConcluirRef = useRef(aoConcluir);
  const [estourou, setEstourou] = useState(false);

  useEffect(() => {
    aoConcluirRef.current = aoConcluir;
  }, [aoConcluir]);

  useEffect(() => {
    if (!jobId) {
      setEstourou(false);
      inicioRef.current = 0;
      return;
    }
    inicioRef.current = Date.now();
    setEstourou(false);
    const timer = setTimeout(() => setEstourou(true), timeoutMs);
    return () => clearTimeout(timer);
  }, [jobId, timeoutMs]);

  const consulta = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.obterJob(jobId as string),
    enabled: Boolean(jobId) && !estourou,
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === 'succeeded' || status === 'failed' || status === 'cancelled') return false;
      return Date.now() - inicioRef.current < janelaRapidaMs ? intervaloRapidoMs : intervaloLongoMs;
    },
    refetchIntervalInBackground: false,
  });

  const job = consulta.data;

  useEffect(() => {
    if (job?.status === 'succeeded' && job.resultado) {
      aoConcluirRef.current(job.resultado);
    }
  }, [job]);

  const perdido = consulta.error instanceof ErroApi && consulta.error.problema.erro.codigo === 'JOB_NAO_ENCONTRADO';

  return {
    job,
    erro: consulta.error,
    carregando: consulta.isLoading,
    estourou,
    perdido,
    cancelado: job?.status === 'cancelled',
  };
}
```

- [ ] **Step 4: Implementar o `JobProgress`**

`src/components/views/JobProgress.tsx`:

```tsx
'use client';

import { useEffect, useState } from 'react';
import { Check, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ETAPAS, ROTULOS_ETAPA } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';
import type { JobResposta } from '@/types/novamente';

interface Props {
  job: JobResposta;
  estourou: boolean;
  aoCancelar: () => void;
  aoTentarNovamente: () => void;
  perdido?: boolean;
}

export function JobProgress({ job, estourou, aoCancelar, aoTentarNovamente, perdido }: Props) {
  const [progresso, setProgresso] = useState(0);

  useEffect(() => {
    setProgresso((anterior) => Math.max(anterior, Math.round(job.progresso_percentual)));
  }, [job.progresso_percentual]);

  const falhou = estourou || perdido || job.status === 'failed';
  const mensagem = estourou
    ? M.job.timeout
    : perdido
      ? M.job.perdida
      : job.erro?.mensagem;

  return (
    <section aria-labelledby="job-titulo" className="rounded-xl border p-6">
      <h2 id="job-titulo" className="text-lg font-semibold">
        {falhou ? M.job.falhaTitulo : M.job.titulo}
      </h2>

      <Progress value={progresso} aria-label="Progresso da geração" className="mt-4" />
      <p className="mt-2 text-sm text-[var(--fg-muted)]">{progresso}%</p>

      <ol className="mt-6 space-y-3">
        {ETAPAS.map((etapa) => {
          const concluida = job.etapas_concluidas.includes(etapa);
          const atual = job.etapa_atual === etapa && !falhou;
          return (
            <li
              key={etapa}
              aria-current={atual ? 'step' : undefined}
              className={cn('flex items-center gap-3 text-sm', !concluida && !atual && 'text-[var(--fg-muted)]')}
            >
              {concluida ? (
                <Check aria-hidden className="h-4 w-4 text-[var(--success)]" />
              ) : atual ? (
                <Loader2 aria-hidden className="h-4 w-4 animate-spin text-[var(--accent)]" />
              ) : (
                <span aria-hidden className="h-4 w-4 rounded-full border" />
              )}
              <span>{ROTULOS_ETAPA[etapa]}</span>
            </li>
          );
        })}
      </ol>

      <div aria-live="polite" className="mt-4 min-h-6 text-sm">
        {falhou ? (
          <div className="text-[var(--danger)]">
            <p className="flex items-center gap-2">
              <X aria-hidden className="h-4 w-4" />
              {mensagem}
            </p>
            {job.erro?.request_id && (
              <p className="mt-1 font-mono text-xs text-[var(--fg-muted)]">request_id: {job.erro.request_id}</p>
            )}
          </div>
        ) : (
          job.mensagem
        )}
      </div>

      <div className="mt-6 flex gap-3">
        {falhou ? (
          <Button onClick={aoTentarNovamente}>{M.comum.tentarNovamente}</Button>
        ) : (
          <Button variant="outline" onClick={aoCancelar}>
            {M.formulario.cancelarGeracao}
          </Button>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm test -- src/features/jobs src/components/views/JobProgress.test.tsx`
Expected: PASS (3 + 5 testes).

- [ ] **Step 6: Compor `GerarView` e a página**

`src/components/views/GerarView.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';
import { IngestionForm } from '@/components/forms/IngestionForm';
import { JobProgress } from './JobProgress';
import { Button } from '@/components/ui/button';
import { useApi } from '@/services/api/ApiProvider';
import { useAdaptationJob } from '@/features/jobs/useAdaptationJob';
import { M } from '@/lib/mensagens';
import type { JobResposta } from '@/types/novamente';

export function GerarView() {
  const router = useRouter();
  const api = useApi();
  const [jobId, setJobId] = useState<string | null>(null);
  const [repetir, setRepetir] = useState<(() => Promise<JobResposta | null>) | null>(null);

  const aoConcluir = useCallback(
    (pacote: { adaptacao_id: string }) => router.push(`/resultado/${pacote.adaptacao_id}`),
    [router],
  );

  const { job, estourou, perdido } = useAdaptationJob(jobId, aoConcluir);

  const aoCriar = useCallback((novo: JobResposta, repetirEnvio: () => Promise<JobResposta | null>) => {
    setRepetir(() => repetirEnvio);
    setJobId(novo.job_id);
  }, []);

  const cancelar = useCallback(async () => {
    if (!jobId) return;
    try {
      await api.cancelarJob(jobId);
    } finally {
      setJobId(null);
    }
  }, [api, jobId]);

  const tentarNovamente = useCallback(async () => {
    setJobId(null);
    const novo = await repetir?.();
    if (novo) setJobId(novo.job_id);
  }, [repetir]);

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
      <section aria-labelledby="form-titulo">
        <h1 id="form-titulo" className="mb-4 text-xl font-semibold">
          {M.formulario.titulo}
        </h1>
        <IngestionForm onCriado={aoCriar} desabilitado={Boolean(jobId)} />
      </section>

      <section aria-label="Resultado da geração">
        {jobId && job ? (
          <JobProgress
            job={job}
            estourou={estourou}
            perdido={perdido}
            aoCancelar={cancelar}
            aoTentarNovamente={tentarNovamente}
          />
        ) : jobId && perdido ? (
          <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
            <p className="text-[var(--danger)]">{M.job.perdida}</p>
            <Button className="mt-4" onClick={tentarNovamente}>
              {M.comum.tentarNovamente}
            </Button>
          </div>
        ) : jobId ? (
          <div className="h-[320px] animate-pulse rounded-xl border bg-[var(--surface)]" aria-label={M.comum.carregando} />
        ) : (
          <div className="flex h-[320px] items-center justify-center rounded-xl border border-dashed text-sm text-[var(--fg-muted)]">
            O material gerado aparece aqui.
          </div>
        )}
      </section>
    </div>
  );
}
```

`src/app/page.tsx`:

```tsx
import { AppShell } from '@/components/layout/AppShell';
import { GerarView } from '@/components/views/GerarView';

export default function Home() {
  return (
    <AppShell>
      <GerarView />
    </AppShell>
  );
}
```

- [ ] **Step 7: Verificar manualmente com o mock**

Run: `NEXT_PUBLIC_API_MOCK=1 npm run dev`

No PowerShell: `$env:NEXT_PUBLIC_API_MOCK=1; npm run dev`

Abra `http://localhost:3000`, cole 200+ caracteres, clique em "Gerar material" e confirme: as etapas avançam, a barra chega a 100% e a navegação vai para `/resultado/<id>` (a página ainda pode ser 404 nesta fase).

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat(frontend): job com polling, progresso monotônico e cancelamento"
```

---

### Task 8: Flashcards com flip 3D

**Files:**
- Create: `src/components/views/FlashcardCard.tsx`, `src/components/views/FlashcardDeck.tsx`, `src/components/views/FlashcardDeck.stories.tsx`
- Test: `src/components/views/FlashcardDeck.test.tsx`

**Interfaces:**
- Consumes: `FlashcardItem`, `M`, `Progress`.
- Produces: `FlashcardDeck({ itens })`, que é consumido pelo registry em Task 10.

- [ ] **Step 1: Escrever o teste que falha**

`src/components/views/FlashcardDeck.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { FlashcardDeck } from './FlashcardDeck';

const itens = [
  { frente: 'Frente 1', verso: 'Verso 1', dica_didatica: 'Dica 1' },
  { frente: 'Frente 2', verso: 'Verso 2' },
  { frente: 'Frente 3', verso: 'Verso 3' },
];

describe('FlashcardDeck', () => {
  it('começa no primeiro cartão, com a frente ativa', () => {
    render(<FlashcardDeck itens={itens} />);
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByText('Frente 1').closest('[data-ativa]')).toHaveAttribute('data-ativa', 'true');
  });

  it('vira o cartão ao clicar e ao teclar Enter', async () => {
    render(<FlashcardDeck itens={itens} />);
    const cartao = screen.getByRole('button', { name: /mostrar verso/i });
    await userEvent.click(cartao);
    expect(screen.getByRole('button', { name: /mostrar frente/i })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('navega com as setas e reseta o flip', async () => {
    render(<FlashcardDeck itens={itens} />);
    await userEvent.click(screen.getByRole('button', { name: /mostrar verso/i }));
    await userEvent.click(screen.getByRole('button', { name: /próximo/i }));
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /mostrar verso/i })).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(screen.getByRole('button', { name: /anterior/i }));
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('navega por teclado no deck', async () => {
    render(<FlashcardDeck itens={itens} />);
    screen.getByRole('region', { name: /flashcards/i }).focus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('mostra a dica didática sem exigir o verso e marca motion reduzido', () => {
    render(<FlashcardDeck itens={itens} />);
    expect(screen.getByText('Dica 1')).toBeInTheDocument();
    expect(screen.getByTestId('flashcard-palco')).toHaveAttribute('data-motion', 'completo');
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/views/FlashcardDeck.test.tsx`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar cartão e deck**

`src/components/views/FlashcardCard.tsx`:

```tsx
'use client';

import { motion, useReducedMotion } from 'framer-motion';
import type { FlashcardItem } from '@/types/novamente';
import { cn } from '@/lib/cn';

interface Props {
  item: FlashcardItem;
  virado: boolean;
  aoVirar: () => void;
}

export function FlashcardCard({ item, virado, aoVirar }: Props) {
  const reduzido = useReducedMotion();

  return (
    <motion.button
      type="button"
      onClick={aoVirar}
      aria-pressed={virado}
      aria-label={virado ? 'Mostrar frente' : 'Mostrar verso'}
      data-testid="flashcard-palco"
      data-motion={reduzido ? 'reduzido' : 'completo'}
      className="relative block h-[320px] w-full text-left [perspective:1200px]"
    >
      <motion.span
        aria-hidden
        className="absolute inset-0 block rounded-xl border bg-[var(--surface)] p-6"
        style={{ backfaceVisibility: 'hidden', transformStyle: 'preserve-3d' }}
        animate={{ rotateY: virado && !reduzido ? 180 : 0 }}
        transition={{ duration: reduzido ? 0 : 0.45 }}
        data-ativa={!virado}
      >
        <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">Frente</span>
        <span className="mt-3 block text-lg">{item.frente}</span>
      </motion.span>

      <span
        aria-hidden
        className={cn(
          'absolute inset-0 block rounded-xl border bg-[var(--surface-elevated)] p-6',
          !reduzido && '[transform:rotateY(180deg)]',
        )}
        style={{ backfaceVisibility: 'hidden' }}
        data-ativa={virado}
      >
        <span className="text-xs uppercase tracking-wide text-[var(--fg-muted)]">Verso</span>
        <span className="mt-3 block text-lg">{item.verso}</span>
      </span>
    </motion.button>
  );
}
```

`src/components/views/FlashcardDeck.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { FlashcardCard } from './FlashcardCard';
import { M } from '@/lib/mensagens';
import type { FlashcardItem } from '@/types/novamente';

export function FlashcardDeck({ itens }: { itens: FlashcardItem[] }) {
  const [indice, setIndice] = useState(0);
  const [virado, setVirado] = useState(false);
  const item = itens[indice];

  const irPara = (novo: number) => {
    setIndice(novo);
    setVirado(false);
  };

  return (
    <section
      role="region"
      aria-label={`Flashcards, ${itens.length} cartões`}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight' && indice < itens.length - 1) {
          e.preventDefault();
          irPara(indice + 1);
        }
        if (e.key === 'ArrowLeft' && indice > 0) {
          e.preventDefault();
          irPara(indice - 1);
        }
      }}
      className="space-y-4"
    >
      <div className="flex items-center justify-between text-sm text-[var(--fg-muted)]">
        <span>
          {indice + 1} / {itens.length}
        </span>
        <span>Clique ou pressione Enter para virar</span>
      </div>

      <Progress value={((indice + 1) / itens.length) * 100} aria-label="Progresso do deck" />

      <FlashcardCard item={item} virado={virado} aoVirar={() => setVirado((v) => !v)} />

      {item.dica_didatica && (
        <p className="rounded-md border border-dashed p-3 text-sm text-[var(--fg-muted)]">
          <strong className="text-[var(--fg)]">Dica: </strong>
          {item.dica_didatica}
        </p>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={() => irPara(indice - 1)} disabled={indice === 0}>
          <ArrowLeft aria-hidden className="mr-2 h-4 w-4" />
          Anterior
        </Button>
        <Button onClick={() => irPara(indice + 1)} disabled={indice === itens.length - 1}>
          Próximo
          <ArrowRight aria-hidden className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm test -- src/components/views/FlashcardDeck.test.tsx`
Expected: PASS (5 testes).

- [ ] **Step 5: Story do deck**

`src/components/views/FlashcardDeck.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { FlashcardDeck } from './FlashcardDeck';
import flashcards from '@/mocks/fixtures/flashcards-vcn-iniciante.json';

const itens = (flashcards as unknown as { conteudo_adaptado: { itens: never } }).conteudo_adaptado.itens;

const meta: Meta<typeof FlashcardDeck> = {
  title: 'Views/FlashcardDeck',
  component: FlashcardDeck,
  args: { itens },
};

export default meta;
type Story = StoryObj<typeof FlashcardDeck>;

export const Padrao: Story = {};
```

- [ ] **Step 6: Rodar o Storybook e conferir**

Run: `npm run storybook`
Expected: a story `Views/FlashcardDeck` renderiza, o cartão vira e as setas navegam.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/views
git commit -m "feat(frontend): deck de flashcards com flip 3D e navegação por teclado"
```

---

### Task 9: Quiz interativo

**Files:**
- Create: `src/components/views/InteractiveQuiz.tsx`, `src/components/views/InteractiveQuiz.stories.tsx`
- Test: `src/components/views/InteractiveQuiz.test.tsx`

**Interfaces:**
- Consumes: `QuizItem`, `M`, `Button`, `Progress`.
- Produces: `InteractiveQuiz({ itens })`, consumido pelo registry em Task 10.

- [ ] **Step 1: Escrever o teste que falha**

`src/components/views/InteractiveQuiz.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { InteractiveQuiz } from './InteractiveQuiz';

const itens = [
  {
    pergunta: 'O que é VCN?',
    opcoes: ['Rede privada', 'Bucket', 'Banco de dados'],
    resposta_correta: 0,
    explicacao: 'VCN é a rede privada da OCI.',
  },
  {
    pergunta: 'O que é NAT Gateway?',
    opcoes: ['Saída privada', 'Entrada pública'],
    resposta_correta: 0,
    explicacao: 'Permite saída sem exposição.',
  },
];

describe('InteractiveQuiz', () => {
  it('mantém Confirmar desabilitado sem seleção', () => {
    render(<InteractiveQuiz itens={itens} />);
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeDisabled();
  });

  it('dá feedback imediato e só então libera a próxima', async () => {
    render(<InteractiveQuiz itens={itens} />);
    await userEvent.click(screen.getByLabelText('Bucket'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));

    expect(screen.getByText('Resposta incorreta')).toBeInTheDocument();
    expect(screen.getByText('VCN é a rede privada da OCI.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /próxima/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /confirmar/i })).not.toBeInTheDocument();
  });

  it('calcula o placar e revisa as erradas', async () => {
    render(<InteractiveQuiz itens={itens} />);

    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    expect(screen.getByText('Resposta correta')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    await userEvent.click(screen.getByLabelText('Entrada pública'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));

    expect(screen.getByText('1 / 2')).toBeInTheDocument();
    expect(screen.getByText(/revisar erradas/i)).toBeInTheDocument();
    expect(screen.getByText('O que é NAT Gateway?')).toBeInTheDocument();
    expect(screen.getByText(/sua resposta/i)).toBeInTheDocument();
  });

  it('anuncia a pergunta como legend de fieldset', () => {
    render(<InteractiveQuiz itens={itens} />);
    expect(screen.getByRole('group', { name: /o que é vcn/i })).toBeInTheDocument();
  });

  it('permite refazer depois do placar', async () => {
    render(<InteractiveQuiz itens={[{ ...itens[0] }]} />);
    await userEvent.click(screen.getByLabelText('Rede privada'));
    await userEvent.click(screen.getByRole('button', { name: /confirmar/i }));
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    await userEvent.click(screen.getByRole('button', { name: /refazer/i }));
    expect(screen.getByRole('group', { name: /o que é vcn/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/views/InteractiveQuiz.test.tsx`
Expected: FAIL — módulo ausente.

- [ ] **Step 3: Implementar o quiz**

`src/components/views/InteractiveQuiz.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { M } from '@/lib/mensagens';
import { cn } from '@/lib/cn';
import type { QuizItem } from '@/types/novamente';

interface Resposta {
  item: number;
  escolhida: number;
  correta: boolean;
}

export function InteractiveQuiz({ itens }: { itens: QuizItem[] }) {
  const [indice, setIndice] = useState(0);
  const [selecionada, setSelecionada] = useState<number | null>(null);
  const [confirmada, setConfirmada] = useState(false);
  const [respostas, setRespostas] = useState<Resposta[]>([]);
  const [finalizado, setFinalizado] = useState(false);

  const item = itens[indice];
  const acertos = respostas.filter((r) => r.correta).length;
  const erradas = respostas.filter((r) => !r.correta);

  const reiniciar = () => {
    setIndice(0);
    setSelecionada(null);
    setConfirmada(false);
    setRespostas([]);
    setFinalizado(false);
  };

  if (finalizado) {
    return (
      <section aria-labelledby="quiz-placar" className="space-y-6">
        <div className="rounded-xl border p-6 text-center">
          <h2 id="quiz-placar" className="text-sm uppercase tracking-wide text-[var(--fg-muted)]">
            Placar
          </h2>
          <p className="mt-2 text-4xl font-semibold">{M.quiz.placar(acertos, itens.length)}</p>
          <Button className="mt-4" variant="outline" onClick={reiniciar}>
            {M.quiz.reiniciar}
          </Button>
        </div>

        <div>
          <h3 className="font-medium">{M.quiz.revisar}</h3>
          {erradas.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--success)]">{M.quiz.semErros}</p>
          ) : (
            <ul className="mt-3 space-y-4">
              {erradas.map((r) => {
                const questao = itens[r.item];
                return (
                  <li key={r.item} className="rounded-lg border p-4 text-sm">
                    <p className="font-medium">{questao.pergunta}</p>
                    <p className="mt-2 text-[var(--danger)]">
                      Sua resposta: {questao.opcoes[r.escolhida]}
                    </p>
                    <p className="text-[var(--success)]">
                      Correta: {questao.opcoes[questao.resposta_correta]}
                    </p>
                    <p className="mt-2 text-[var(--fg-muted)]">{questao.explicacao}</p>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    );
  }

  const correta = selecionada === item.resposta_correta;

  return (
    <section aria-labelledby="quiz-pergunta" className="space-y-5">
      <div className="flex items-center justify-between text-sm text-[var(--fg-muted)]">
        <span>
          Pergunta {indice + 1} de {itens.length}
        </span>
      </div>
      <Progress value={((indice + 1) / itens.length) * 100} aria-label="Progresso do quiz" />

      <fieldset>
        <legend id="quiz-pergunta" className="text-lg font-medium">
          {item.pergunta}
        </legend>
        <div className="mt-4 space-y-2">
          {item.opcoes.map((opcao, n) => {
            const marcada = selecionada === n;
            return (
              <label
                key={opcao}
                className={cn(
                  'flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm',
                  marcada && 'border-[var(--accent)] bg-[var(--accent-muted)]',
                  confirmada && n === item.resposta_correta && 'border-[var(--success)]',
                  confirmada && marcada && !correta && 'border-[var(--danger)]',
                )}
              >
                <input
                  type="radio"
                  name={`quiz-${indice}`}
                  checked={marcada}
                  disabled={confirmada}
                  onChange={() => setSelecionada(n)}
                />
                <span>{opcao}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div aria-live="polite" className="min-h-6 text-sm">
        {confirmada && (
          <div className={correta ? 'text-[var(--success)]' : 'text-[var(--danger)]'}>
            <p className="flex items-center gap-2 font-medium">
              {correta ? <CheckCircle2 aria-hidden className="h-4 w-4" /> : <XCircle aria-hidden className="h-4 w-4" />}
              {correta ? M.quiz.correto : M.quiz.incorreto}
            </p>
            <p className="mt-1 text-[var(--fg)]">{item.explicacao}</p>
          </div>
        )}
      </div>

      <div className="flex justify-end">
        {confirmada ? (
          <Button
            onClick={() => {
              if (indice === itens.length - 1) {
                setFinalizado(true);
                return;
              }
              setIndice(indice + 1);
              setSelecionada(null);
              setConfirmada(false);
            }}
          >
            {M.quiz.proxima}
          </Button>
        ) : (
          <Button
            disabled={selecionada === null}
            onClick={() => {
              if (selecionada === null) return;
              setRespostas((r) => [...r, { item: indice, escolhida: selecionada, correta }]);
              setConfirmada(true);
            }}
          >
            {M.quiz.confirmar}
          </Button>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm test -- src/components/views/InteractiveQuiz.test.tsx`
Expected: PASS (5 testes).

- [ ] **Step 5: Story**

`src/components/views/InteractiveQuiz.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { InteractiveQuiz } from './InteractiveQuiz';
import quiz from '@/mocks/fixtures/quiz-vcn-desenvolvedor.json';

const itens = (quiz as unknown as { conteudo_adaptado: { itens: never } }).conteudo_adaptado.itens;

const meta: Meta<typeof InteractiveQuiz> = {
  title: 'Views/InteractiveQuiz',
  component: InteractiveQuiz,
  args: { itens },
};

export default meta;
type Story = StoryObj<typeof InteractiveQuiz>;

export const Padrao: Story = {};
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/views
git commit -m "feat(frontend): quiz com feedback imediato, placar e revisão de erros"
```

---

### Task 10: Markdown, registry de renderizadores e OCI

**Files:**
- Create: `src/components/views/MarkdownView.tsx`, `src/components/views/ContentRenderer.tsx`, `src/components/views/ScoreGauge.tsx`, `src/components/views/OCIPanel.tsx`, `src/components/views/OCIPanel.stories.tsx`, `src/components/views/MarkdownView.stories.tsx`, `src/features/oci/useOciStatus.ts`
- Test: `src/components/views/ContentRenderer.test.tsx`, `src/components/views/OCIPanel.test.tsx`

**Interfaces:**
- Consumes: `ConteudoAdaptado`, `useApi`, `formatarPercentual`, `faixaAncoragem`, `formatarDataRelativa`, `M`.
- Produces: `ContentRenderer({ conteudo })`, `MarkdownView`, `OCIPanel({ armazenamento, avaliacao, oci })`, `ScoreGauge({ valor })`, `useOciStatus()`.

- [ ] **Step 1: Escrever os testes que falham**

`src/components/views/ContentRenderer.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContentRenderer } from './ContentRenderer';
import type { ConteudoAdaptado } from '@/types/novamente';

const flashcards: ConteudoAdaptado = {
  tipo: 'flashcards',
  titulo: 'Deck',
  introducao_contextualizada: 'Intro',
  itens: [
    { frente: 'Frente A', verso: 'Verso A' },
    { frente: 'Frente B', verso: 'Verso B' },
    { frente: 'Frente C', verso: 'Verso C' },
  ],
};

describe('ContentRenderer', () => {
  it('despacha flashcards para o deck', async () => {
    render(<ContentRenderer conteudo={flashcards} />);
    expect(await screen.findByText('Frente A')).toBeInTheDocument();
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('despacha quiz para o quiz interativo', async () => {
    render(
      <ContentRenderer
        conteudo={{
          tipo: 'quiz',
          titulo: 'Quiz',
          introducao_contextualizada: 'Intro',
          itens: [{ pergunta: 'Pergunta X?', opcoes: ['a', 'b'], resposta_correta: 0, explicacao: 'porque' }],
        }}
      />,
    );
    expect(await screen.findByText('Pergunta X?')).toBeInTheDocument();
  });

  it('renderiza markdown e remove script malicioso', async () => {
    render(
      <ContentRenderer
        conteudo={{
          tipo: 'markdown',
          titulo: 'Tutorial',
          introducao_contextualizada: 'Intro',
          itens: '## Passo 1\n\nTexto seguro.\n\n<script>alert(1)</script>',
        }}
      />,
    );
    expect(await screen.findByRole('heading', { name: 'Passo 1' })).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });

  it('cai em ErrorState quando o tipo não está no registry', () => {
    const invalido = { tipo: 'desconhecido', titulo: 'x', introducao_contextualizada: 'y', itens: 'z' } as never;
    render(<ContentRenderer conteudo={invalido} />);
    expect(screen.getByRole('alert')).toHaveTextContent(/formato inesperado/i);
  });
});
```

`src/components/views/OCIPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { OCIPanel } from './OCIPanel';

const armazenamento = { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' as const };
const avaliacao = { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' as const };

describe('OCIPanel', () => {
  it('mostra score, faixa e dados do bucket', () => {
    render(<OCIPanel armazenamento={armazenamento} avaliacao={avaliacao} />);
    expect(screen.getByText('98%')).toBeInTheDocument();
    expect(screen.getByTestId('score-gauge')).toHaveAttribute('data-faixa', 'alta');
    expect(screen.getByText('novamente')).toBeInTheDocument();
    expect(screen.getByText('a.json')).toBeInTheDocument();
    expect(screen.getByText('Persistido no OCI')).toBeInTheDocument();
  });

  it('avisa quando o upload falhou, sem esconder o conteúdo', () => {
    render(<OCIPanel armazenamento={{ ...armazenamento, status_upload: 'falha' }} avaliacao={avaliacao} />);
    expect(screen.getByText(/não persistido no OCI/i)).toBeInTheDocument();
  });

  it('mostra estado neutro quando o OCI não está configurado', () => {
    render(
      <OCIPanel
        armazenamento={armazenamento}
        avaliacao={avaliacao}
        oci={{ configurado: false, mensagem: 'Credenciais ausentes', verificado_em: '2026-10-21T14:00:00Z' }}
      />,
    );
    expect(screen.getByText('OCI não configurado')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/views/ContentRenderer.test.tsx src/components/views/OCIPanel.test.tsx`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar markdown, registry e OCI**

`src/components/views/MarkdownView.tsx`:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { ConteudoAdaptado } from '@/types/novamente';

type Props = { conteudo: Extract<ConteudoAdaptado, { tipo: 'markdown' }> };

export function MarkdownView({ conteudo }: Props) {
  return (
    <article className="prose prose-invert max-w-none">
      <h2>{conteudo.titulo}</h2>
      <p>{conteudo.introducao_contextualizada}</p>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {conteudo.itens}
      </ReactMarkdown>
    </article>
  );
}
```

`src/components/views/ContentRenderer.tsx`:

```tsx
'use client';

import dynamic from 'next/dynamic';
import { Skeleton } from '@/components/ui/skeleton';
import { ErroContrato, mensagemDoErro } from '@/services/api/erros';
import type { ConteudoAdaptado } from '@/types/novamente';

const carregandoDeck = () => <Skeleton className="h-[400px] w-full" />;

const FlashcardDeck = dynamic(() => import('./FlashcardDeck').then((m) => m.FlashcardDeck), {
  loading: carregandoDeck,
});
const InteractiveQuiz = dynamic(() => import('./InteractiveQuiz').then((m) => m.InteractiveQuiz), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
});
const MarkdownView = dynamic(() => import('./MarkdownView').then((m) => m.MarkdownView), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
});

type Renderizador = (conteudo: ConteudoAdaptado) => React.ReactNode;

const REGISTRY: Record<ConteudoAdaptado['tipo'], Renderizador> = {
  flashcards: (c) => (c.tipo === 'flashcards' ? <FlashcardDeck itens={c.itens} /> : null),
  quiz: (c) => (c.tipo === 'quiz' ? <InteractiveQuiz itens={c.itens} /> : null),
  markdown: (c) => (c.tipo === 'markdown' ? <MarkdownView conteudo={c} /> : null),
};

export function ContentRenderer({ conteudo }: { conteudo: ConteudoAdaptado }) {
  const renderizar = REGISTRY[conteudo.tipo];
  if (!renderizar) {
    return (
      <p role="alert" className="rounded-md border border-[var(--danger)] p-4 text-sm text-[var(--danger)]">
        {mensagemDoErro(new ErroContrato('tipo fora do registry'))}
      </p>
    );
  }
  return <>{renderizar(conteudo)}</>;
}
```

`src/components/views/ScoreGauge.tsx`:

```tsx
import { formatarPercentual, faixaAncoragem } from '@/lib/formatadores';

const CORES = {
  alta: 'bg-[var(--success)]',
  media: 'bg-[var(--warning)]',
  baixa: 'bg-[var(--danger)]',
} as const;

export function ScoreGauge({ valor, rotulo }: { valor: number; rotulo: string }) {
  const faixa = faixaAncoragem(valor);
  return (
    <div data-testid="score-gauge" data-faixa={faixa}>
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-[var(--fg-muted)]">{rotulo}</span>
        <span className="text-2xl font-semibold">{formatarPercentual(valor)}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-elevated)]" aria-hidden>
        <div className={`h-full ${CORES[faixa]}`} style={{ width: `${Math.round(valor * 100)}%` }} />
      </div>
    </div>
  );
}
```

`src/components/views/OCIPanel.tsx`:

```tsx
import { AlertTriangle, Database } from 'lucide-react';
import { ScoreGauge } from './ScoreGauge';
import { M } from '@/lib/mensagens';
import { formatarDataRelativa } from '@/lib/formatadores';
import type { AdaptacaoPacote, OciStatus } from '@/types/novamente';

interface Props {
  armazenamento: AdaptacaoPacote['armazenamento_oci'];
  avaliacao: AdaptacaoPacote['avaliacao_qualidade'];
  oci?: OciStatus;
}

export function OCIPanel({ armazenamento, avaliacao, oci }: Props) {
  return (
    <aside aria-labelledby="oci-titulo" className="space-y-5 rounded-xl border p-5">
      <h2 id="oci-titulo" className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <Database aria-hidden className="h-4 w-4 text-[var(--accent)]" />
        {M.oci.titulo}
      </h2>

      <ScoreGauge valor={avaliacao.ancoragem_fonte_score} rotulo={M.resultado.ancoragem} />

      <div>
        <p className="text-sm text-[var(--fg-muted)]">{M.resultado.clareza}</p>
        <p className="text-base font-medium">{avaliacao.clareza_pedagogica}</p>
      </div>

      {avaliacao.observacoes && (
        <div>
          <p className="text-sm text-[var(--fg-muted)]">{M.resultado.observacoes}</p>
          <p className="text-sm">{avaliacao.observacoes}</p>
        </div>
      )}

      <dl className="space-y-2 border-t pt-4 text-sm">
        <div>
          <dt className="text-[var(--fg-muted)]">{M.resultado.bucket}</dt>
          <dd className="font-mono text-xs">{armazenamento.bucket}</dd>
        </div>
        <div>
          <dt className="text-[var(--fg-muted)]">{M.resultado.objeto}</dt>
          <dd className="truncate font-mono text-xs" title={armazenamento.objeto_id}>
            {armazenamento.objeto_id}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--fg-muted)]">Status</dt>
          <dd>
            {armazenamento.status_upload === 'concluido' ? (
              <span className="text-[var(--success)]">{M.oci.concluido}</span>
            ) : (
              <span className="flex items-center gap-1 text-[var(--warning)]">
                <AlertTriangle aria-hidden className="h-4 w-4" />
                {M.oci.falhaUpload}
              </span>
            )}
          </dd>
        </div>
      </dl>

      {armazenamento.status_upload === 'falha' && (
        <p role="alert" className="rounded-md border border-[var(--warning)] p-3 text-sm text-[var(--warning)]">
          {M.resultado.naoPersistido}
        </p>
      )}

      {oci && !oci.configurado && (
        <p className="rounded-md border p-3 text-sm text-[var(--fg-muted)]">
          {M.oci.naoConfigurado}
          {oci.mensagem ? ` — ${oci.mensagem}` : ''}
        </p>
      )}

      {oci?.configurado && (
        <dl className="space-y-1 border-t pt-4 text-xs text-[var(--fg-muted)]">
          {oci.total_objetos !== undefined && (
            <div className="flex justify-between">
              <dt>{M.oci.objetos}</dt>
              <dd>{oci.total_objetos}</dd>
            </div>
          )}
          {oci.ultimo_upload_em && (
            <div className="flex justify-between gap-2">
              <dt>{M.oci.ultimoUpload}</dt>
              <dd>{formatarDataRelativa(oci.ultimo_upload_em)}</dd>
            </div>
          )}
        </dl>
      )}
    </aside>
  );
}
```

`src/features/oci/useOciStatus.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { OciStatusSchema } from '@/types/schemas';

export function useOciStatus() {
  const api = useApi();
  return useQuery({
    queryKey: ['oci-status'],
    queryFn: async () => OciStatusSchema.parse(await api.statusOci()),
    staleTime: 30_000,
  });
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm test -- src/components/views/ContentRenderer.test.tsx src/components/views/OCIPanel.test.tsx`
Expected: PASS (4 + 3 testes). Se o `dynamic` atrasar, os `findBy` já cobrem.

- [ ] **Step 5: Stories de markdown e OCI**

`src/components/views/MarkdownView.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { MarkdownView } from './MarkdownView';
import tutorial from '@/mocks/fixtures/tutorial-vcn-lider.json';

const conteudo = (tutorial as unknown as { conteudo_adaptado: never }).conteudo_adaptado;

const meta: Meta<typeof MarkdownView> = {
  title: 'Views/MarkdownView',
  component: MarkdownView,
  args: { conteudo },
};

export default meta;
type Story = StoryObj<typeof MarkdownView>;

export const Tutorial: Story = {};
```

`src/components/views/OCIPanel.stories.tsx`:

```tsx
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { OCIPanel } from './OCIPanel';
import flashcards from '@/mocks/fixtures/flashcards-vcn-iniciante.json';

const fixture = flashcards as unknown as {
  armazenamento_oci: never;
  avaliacao_qualidade: never;
};

const meta: Meta<typeof OCIPanel> = {
  title: 'Views/OCIPanel',
  component: OCIPanel,
  args: { armazenamento: fixture.armazenamento_oci, avaliacao: fixture.avaliacao_qualidade },
};

export default meta;
type Story = StoryObj<typeof OCIPanel>;

export const Sucesso: Story = {};

export const UploadFalhou: Story = {
  args: { armazenamento: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'falha' } },
};

export const OciNaoConfigurado: Story = {
  args: {
    oci: { configurado: false, mensagem: 'Credenciais ausentes', verificado_em: '2026-10-21T14:00:00Z' },
  },
};
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): registry de renderizadores, markdown sanitizado e painel OCI"
```

---

### Task 11: Página de resultado, download e exportação

**Files:**
- Create: `src/app/resultado/[id]/page.tsx`, `src/components/views/ResultadoView.tsx`, `src/components/views/ResultadoHeader.tsx`, `src/components/views/ExportMenu.tsx`, `src/features/adaptations/useAdaptation.ts`, `src/features/adaptations/useExport.ts`, `src/services/api/download.ts`
- Modify: `src/lib/mensagens.ts` (mensagens de erro da página e CSV)
- Test: `src/components/views/ResultadoView.test.tsx`, `src/features/adaptations/useExport.test.tsx`, `src/services/api/download.test.ts`

**Interfaces:**
- Consumes: `ContentRenderer`, `OCIPanel`, `useOciStatus`, `AdaptacaoPacoteSchema`, `nomeArquivoPacote`, `nomeArquivoExportacao`, `M`.
- Produces: `ResultadoView({ adaptacaoId })`, `useAdaptation(id)`, `useExport(pacote)` → `{ exportar, baixarJson, baixando, erro, csvDisponivel }`, `baixarBlob(blob, nome)`.

- [ ] **Step 1: Escrever os testes que falham**

`src/services/api/download.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { baixarBlob } from './download';

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.restoreAllMocks());

describe('baixarBlob', () => {
  it('dispara o download com o nome informado e revoga a URL', () => {
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    baixarBlob(new Blob(['conteudo']), 'arquivo.md');

    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clique).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
    expect(document.querySelector('a[download]')).toBeNull();
  });
});
```

`src/features/adaptations/useExport.test.tsx`:

```tsx
import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useExport } from './useExport';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote } from '@/types/novamente';

const pacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: { perfil_aplicado: 'Iniciante', formato_gerado: 'Flashcards' },
} as unknown as AdaptacaoPacote;

function montar(conteudo: AdaptacaoPacote['conteudo_adaptado']) {
  const api = {
    exportar: vi.fn().mockResolvedValue(new Blob(['# md'])),
    baixarJson: vi.fn().mockResolvedValue(new Blob(['{}'])),
  } as unknown as NovaMenteApi;
  const wrapper = ({ children }: { children: React.ReactNode }) => <ApiProvider client={api}>{children}</ApiProvider>;
  const completo = { ...pacote, conteudo_adaptado: conteudo } as unknown as AdaptacaoPacote;
  return { api, wrapper, completo };
}

describe('useExport', () => {
  it('exporta markdown com o nome de arquivo derivado do pacote', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const { api, wrapper, completo } = montar({
      tipo: 'flashcards',
      titulo: 'Deck',
      introducao_contextualizada: 'Intro',
      itens: [
        { frente: 'a', verso: 'b' },
        { frente: 'c', verso: 'd' },
        { frente: 'e', verso: 'f' },
      ],
    });

    const { result } = renderHook(() => useExport(completo), { wrapper });
    await result.current.exportar('md');

    expect(api.exportar).toHaveBeenCalledWith('01JAVCNFLCARD00000000001', 'md');
    expect(clique).toHaveBeenCalled();
  });

  it('habilita CSV apenas para flashcards', () => {
    URL.createObjectURL = vi.fn(() => 'blob:mock');
    URL.revokeObjectURL = vi.fn();
    const flashcards = montar({
      tipo: 'flashcards',
      titulo: 'Deck',
      introducao_contextualizada: 'Intro',
      itens: [
        { frente: 'a', verso: 'b' },
        { frente: 'c', verso: 'd' },
        { frente: 'e', verso: 'f' },
      ],
    });
    const tutorial = montar({
      tipo: 'markdown',
      titulo: 'Tutorial',
      introducao_contextualizada: 'Intro',
      itens: '## Passo 1\n\nConteúdo longo o suficiente para o schema aceitar o material.',
    });

    const a = renderHook(() => useExport(flashcards.completo), { wrapper: flashcards.wrapper });
    const b = renderHook(() => useExport(tutorial.completo), { wrapper: tutorial.wrapper });
    expect(a.result.current.csvDisponivel).toBe(true);
    expect(b.result.current.csvDisponivel).toBe(false);
  });
});
```

> O teste termina em `expect(clique).toHaveBeenCalled();`.

`src/components/views/ResultadoView.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ResultadoView } from './ResultadoView';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { AdaptacaoPacote } from '@/types/novamente';

const pacote: AdaptacaoPacote = {
  adaptacao_id: '01JAVCNFLCARD00000000001',
  status: 'sucesso',
  criado_em: '2026-10-21T14:02:11Z',
  documento: { titulo: 'Introdução à VCN', origem: 'texto' },
  metadados: {
    perfil_aplicado: 'Iniciante',
    formato_gerado: 'Flashcards',
    nivel_detalhe_aplicado: 'Didatico',
    nicho_setor_aplicado: 'Geral',
    tempo_estimado_estudo_minutos: 5,
    conceitos_chave: ['VCN'],
  },
  conteudo_adaptado: {
    tipo: 'flashcards',
    titulo: 'Dominando Redes na Nuvem',
    introducao_contextualizada: 'Intro',
    itens: [
      { frente: 'O que é VCN?', verso: 'Rede privada.' },
      { frente: 'O que é subnet?', verso: 'Divisão da rede.' },
      { frente: 'O que é IGW?', verso: 'Porta para a internet.' },
    ],
  },
  avaliacao_qualidade: { ancoragem_fonte_score: 0.98, clareza_pedagogica: 'Alta' },
  armazenamento_oci: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'concluido' },
};

function renderizar(obter: NovaMenteApi['obter']) {
  const api = {
    obter,
    statusOci: vi.fn().mockResolvedValue({
      configurado: true,
      bucket: 'novamente',
      verificado_em: '2026-10-21T14:00:00Z',
    }),
    exportar: vi.fn().mockResolvedValue(new Blob(['x'])),
    baixarJson: vi.fn().mockResolvedValue(new Blob(['{}'])),
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <ResultadoView adaptacaoId={pacote.adaptacao_id} />
      </QueryClientProvider>
    </ApiProvider>,
  );
}

describe('ResultadoView', () => {
  it('renderiza título, deck e painel OCI', async () => {
    renderizar(vi.fn().mockResolvedValue(pacote));
    expect(await screen.findByRole('heading', { name: 'Dominando Redes na Nuvem' })).toBeInTheDocument();
    expect(await screen.findByText('O que é VCN?')).toBeInTheDocument();
    expect(screen.getByText('98%')).toBeInTheDocument();
  });

  it('trata 404 com mensagem específica', async () => {
    renderizar(
      vi.fn().mockRejectedValue(
        new ErroApi({ erro: { codigo: 'ADAPTACAO_NAO_ENCONTRADA', mensagem: 'Material não encontrado.' } }, 404),
      ),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Material não encontrado.');
  });

  it('trata pacote fora do contrato sem tela branca', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        ...pacote,
        metadados: { ...pacote.metadados, formato_gerado: 'Quiz' },
      }),
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(/formato inesperado/i);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/views/ResultadoView.test.tsx src/features/adaptations/useExport.test.tsx src/services/api/download.test.ts`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar download, leitura e exportação**

`src/services/api/download.ts`:

```ts
export function baixarBlob(blob: Blob, nomeArquivo: string) {
  const url = URL.createObjectURL(blob);
  const ancora = document.createElement('a');
  ancora.href = url;
  ancora.download = nomeArquivo;
  document.body.appendChild(ancora);
  ancora.click();
  ancora.remove();
  URL.revokeObjectURL(url);
}
```

`src/features/adaptations/useAdaptation.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { AdaptacaoPacoteSchema } from '@/types/schemas';

export function useAdaptation(adaptacaoId: string) {
  const api = useApi();

  return useQuery({
    queryKey: ['adaptacao', adaptacaoId],
    queryFn: async () => {
      const bruto = await api.obter(adaptacaoId);
      const analisado = AdaptacaoPacoteSchema.safeParse(bruto);
      if (!analisado.success) {
        throw new ErroContrato(analisado.error.issues.map((i) => i.message).join('; '));
      }
      return analisado.data;
    },
    staleTime: Infinity,
    retry: false,
  });
}
```

`src/features/adaptations/useExport.ts`:

```ts
'use client';

import { useCallback, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { mensagemDoErro } from '@/services/api/erros';
import { baixarBlob } from '@/services/api/download';
import { nomeArquivoExportacao, nomeArquivoPacote } from '@/lib/formatadores';
import type { AdaptacaoPacote, FormatoExportacao } from '@/types/novamente';

export function useExport(pacote: AdaptacaoPacote | null) {
  const api = useApi();
  const [baixando, setBaixando] = useState<FormatoExportacao | 'json' | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const exportar = useCallback(
    async (formato: FormatoExportacao) => {
      if (!pacote) return;
      setErro(null);
      setBaixando(formato);
      try {
        const blob = await api.exportar(pacote.adaptacao_id, formato);
        baixarBlob(blob, nomeArquivoExportacao(pacote, formato));
      } catch (e) {
        setErro(mensagemDoErro(e));
      } finally {
        setBaixando(null);
      }
    },
    [api, pacote],
  );

  const baixarJson = useCallback(async () => {
    if (!pacote) return;
    setErro(null);
    setBaixando('json');
    try {
      const blob = await api.baixarJson(pacote.adaptacao_id);
      baixarBlob(blob, nomeArquivoPacote(pacote));
    } catch (e) {
      setErro(mensagemDoErro(e));
    } finally {
      setBaixando(null);
    }
  }, [api, pacote]);

  return {
    exportar,
    baixarJson,
    baixando,
    erro,
    csvDisponivel: pacote?.conteudo_adaptado.tipo === 'flashcards',
  };
}
```

- [ ] **Step 4: Implementar cabeçalho e menu de exportação**

`src/lib/mensagens.ts` — adicionar em `resultado`:

```ts
    naoEncontrado: 'Material não encontrado.',
    csvIndisponivel: 'CSV está disponível apenas para Flashcards.',
```

`src/components/views/ExportMenu.tsx`:

```tsx
'use client';

import { Download, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useExport } from '@/features/adaptations/useExport';
import { M } from '@/lib/mensagens';
import type { AdaptacaoPacote } from '@/types/novamente';

export function ExportMenu({ pacote }: { pacote: AdaptacaoPacote }) {
  const { exportar, csvDisponivel, baixando, erro } = useExport(pacote);

  return (
    <div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" disabled={Boolean(baixando)}>
            {baixando ? <Loader2 aria-hidden className="mr-2 h-4 w-4 animate-spin" /> : <Download aria-hidden className="mr-2 h-4 w-4" />}
            {M.resultado.exportar}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => exportar('md')}>Markdown</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => exportar('pdf')}>PDF</DropdownMenuItem>
          <DropdownMenuItem
            disabled={!csvDisponivel}
            title={csvDisponivel ? undefined : M.resultado.csvIndisponivel}
            onSelect={() => exportar('csv')}
          >
            CSV (Anki)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {erro && (
        <p role="alert" className="mt-2 text-sm text-[var(--danger)]">
          {erro}
        </p>
      )}
    </div>
  );
}
```

`src/components/views/ResultadoHeader.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { FileJson } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExportMenu } from './ExportMenu';
import { useExport } from '@/features/adaptations/useExport';
import { FORMATOS, NIVEIS, PERFIS, NICHOS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import type { AdaptacaoPacote } from '@/types/novamente';

export function ResultadoHeader({ pacote }: { pacote: AdaptacaoPacote }) {
  const { baixarJson, baixando } = useExport(pacote);
  const perfil = PERFIS.find((p) => p.valor === pacote.metadados.perfil_aplicado)?.rotulo;
  const formato = FORMATOS.find((f) => f.valor === pacote.metadados.formato_gerado)?.rotulo;
  const nivel = NIVEIS.find((n) => n.valor === pacote.metadados.nivel_detalhe_aplicado)?.rotulo;
  const nicho = NICHOS.find((n) => n.valor === pacote.metadados.nicho_setor_aplicado)?.rotulo;

  return (
    <header className="mb-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{pacote.conteudo_adaptado.titulo}</h1>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">
            {pacote.documento.titulo} · {M.resultado.tempoEstimado(pacote.metadados.tempo_estimado_estudo_minutos)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ExportMenu pacote={pacote} />
          <Button variant="outline" onClick={baixarJson} disabled={baixando === 'json'}>
            <FileJson aria-hidden className="mr-2 h-4 w-4" />
            {M.resultado.baixarJson}
          </Button>
          <Button asChild variant="ghost">
            <Link href="/">{M.resultado.novaGeracao}</Link>
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {perfil && <Badge variant="secondary">{perfil}</Badge>}
        {formato && <Badge>{formato}</Badge>}
        {nivel && <Badge variant="outline">{nivel}</Badge>}
        {nicho && <Badge variant="outline">{nicho}</Badge>}
        {pacote.metadados.conceitos_chave.slice(0, 4).map((conceito) => (
          <Badge key={conceito} variant="outline">
            {conceito}
          </Badge>
        ))}
      </div>
    </header>
  );
}
```

`src/components/views/ResultadoView.tsx`:

```tsx
'use client';

import { AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { ContentRenderer } from './ContentRenderer';
import { OCIPanel } from './OCIPanel';
import { ResultadoHeader } from './ResultadoHeader';
import { useAdaptation } from '@/features/adaptations/useAdaptation';
import { useOciStatus } from '@/features/oci/useOciStatus';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';

export function ResultadoView({ adaptacaoId }: { adaptacaoId: string }) {
  const { data: pacote, isLoading, error, refetch } = useAdaptation(adaptacaoId);
  const { data: oci } = useOciStatus();

  if (isLoading) {
    return (
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]" aria-busy="true" aria-label={M.comum.carregando}>
        <div className="space-y-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-[360px] w-full" />
        </div>
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  if (error) {
    const naoEncontrado = error instanceof ErroApi && error.status === 404;
    return (
      <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
        <h2 className="flex items-center gap-2 font-semibold text-[var(--danger)]">
          <AlertTriangle aria-hidden className="h-5 w-5" />
          {naoEncontrado ? M.resultado.naoEncontrado : mensagemDoErro(error)}
        </h2>
        <div className="mt-4 flex gap-3">
          {!naoEncontrado && (
            <Button onClick={() => refetch()}>{M.comum.tentarNovamente}</Button>
          )}
          <Button asChild variant="outline">
            <a href="/historico">Ir para o histórico</a>
          </Button>
        </div>
      </div>
    );
  }

  if (!pacote) return null;

  return (
    <div>
      <ResultadoHeader pacote={pacote} />
      <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0">
          <p className="mb-6 text-[var(--fg-muted)]">{pacote.conteudo_adaptado.introducao_contextualizada}</p>
          <ContentRenderer conteudo={pacote.conteudo_adaptado} />
        </div>
        <OCIPanel
          armazenamento={pacote.armazenamento_oci}
          avaliacao={pacote.avaliacao_qualidade}
          oci={oci}
        />
      </div>
    </div>
  );
}
```

`src/app/resultado/[id]/page.tsx`:

```tsx
import { AppShell } from '@/components/layout/AppShell';
import { ResultadoView } from '@/components/views/ResultadoView';

export default async function ResultadoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <ResultadoView adaptacaoId={id} />
    </AppShell>
  );
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npm test -- src/components/views/ResultadoView.test.tsx src/features/adaptations src/services/api/download.test.ts`
Expected: PASS (3 + 2 + 1 testes).

- [ ] **Step 6: Verificar no navegador**

Run: `$env:NEXT_PUBLIC_API_MOCK=1; npm run dev`

Gere um material pelo cenário "Iniciante + Flashcards", confirme a página `/resultado/<id>`, recarregue (o pacote deve continuar aparecendo, pois o mock semeia a fixture) e teste Exportar → Markdown e Baixar JSON.

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat(frontend): página de resultado com exportação md/pdf/csv e download json"
```

---

### Task 12: Histórico com filtros e paginação na URL

**Files:**
- Create: `src/features/adaptations/useAdaptationHistory.ts`, `src/components/views/HistoricoView.tsx`, `src/app/historico/page.tsx`
- Test: `src/components/views/HistoricoView.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `PaginaAdaptacoesSchema`, `formatarDataRelativa`, `Badge`, `Button`, `Skeleton`, `M`, `FORMATOS`, `PERFIS`.
- Produces: `useAdaptationHistory()` → `{ data, isLoading, error, refetch, filtros, busca, setBusca, atualizar }`; `HistoricoView`.

- [ ] **Step 1: Escrever o teste que falha**

`src/components/views/HistoricoView.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoricoView } from './HistoricoView';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  useSearchParams: () => mocks.params,
}));

const resumo = (i: number) => ({
  adaptacao_id: `id-${i}`,
  criado_em: '2026-10-21T14:00:00Z',
  documento: { titulo: `Documento ${i}`, origem: 'texto' as const },
  perfil_aplicado: 'Iniciante' as const,
  formato_gerado: 'Flashcards' as const,
  nivel_detalhe_aplicado: 'Didatico' as const,
  tempo_estimado_estudo_minutos: 5,
  ancoragem_fonte_score: 0.95,
  status_upload: 'concluido' as const,
  conceitos_chave: ['VCN'],
});

function renderizar(listar: NovaMenteApi['listar']) {
  const api = { listar } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <HistoricoView />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { listar };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.params = new URLSearchParams();
});

describe('HistoricoView', () => {
  it('lista os materiais da página', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        itens: [resumo(1), resumo(2)],
        pagina: 1,
        tamanho_pagina: 12,
        total: 2,
        total_paginas: 1,
      }),
    );
    expect(await screen.findByText('Documento 1')).toBeInTheDocument();
    expect(screen.getByText('Documento 2')).toBeInTheDocument();
  });

  it('mostra estado vazio com CTA', async () => {
    renderizar(vi.fn().mockResolvedValue({ itens: [], pagina: 1, tamanho_pagina: 12, total: 0, total_paginas: 0 }));
    expect(await screen.findByText(/nenhum material gerado ainda/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /gerar o primeiro material/i })).toHaveAttribute('href', '/');
  });

  it('pagina pela URL', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        itens: Array.from({ length: 12 }, (_, i) => resumo(i)),
        pagina: 1,
        tamanho_pagina: 12,
        total: 14,
        total_paginas: 2,
      }),
    );
    await screen.findByText('Documento 0');
    await userEvent.click(screen.getByRole('button', { name: /próxima/i }));
    expect(mocks.replace).toHaveBeenCalledWith('/historico?pagina=2');
  });

  it('filtra por formato na URL', async () => {
    renderizar(
      vi.fn().mockResolvedValue({ itens: [resumo(1)], pagina: 1, tamanho_pagina: 12, total: 1, total_paginas: 1 }),
    );
    await screen.findByText('Documento 1');
    await userEvent.selectOptions(screen.getByLabelText(/todos os formatos/i), 'Quiz');
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/historico?formato=Quiz'));
  });

  it('mostra erro com retry', async () => {
    renderizar(vi.fn().mockRejectedValue(new Error('falhou')));
    expect(await screen.findByRole('alert')).toHaveTextContent(/inesperado/i);
    expect(screen.getByRole('button', { name: /tentar novamente/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/views/HistoricoView.test.tsx`
Expected: FAIL — módulo ausente.

- [ ] **Step 3: Implementar hook e view**

`src/features/adaptations/useAdaptationHistory.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { PaginaAdaptacoesSchema, LIMITES } from '@/types/schemas';

export interface FiltrosHistorico {
  pagina: number;
  formato?: string;
  perfil?: string;
  q: string;
}

export function useAdaptationHistory() {
  const api = useApi();
  const router = useRouter();
  const params = useSearchParams();

  const filtros = useMemo<FiltrosHistorico>(
    () => ({
      pagina: Math.max(1, Number(params.get('pagina') ?? 1)),
      formato: params.get('formato') ?? undefined,
      perfil: params.get('perfil') ?? undefined,
      q: params.get('q') ?? '',
    }),
    [params],
  );

  const atualizar = useCallback(
    (mudanca: Partial<FiltrosHistorico>) => {
      const proximos: FiltrosHistorico = { ...filtros, ...mudanca };
      const busca = new URLSearchParams();
      if (proximos.pagina > 1) busca.set('pagina', String(proximos.pagina));
      if (proximos.formato) busca.set('formato', proximos.formato);
      if (proximos.perfil) busca.set('perfil', proximos.perfil);
      if (proximos.q.trim()) busca.set('q', proximos.q.trim());
      const query = busca.toString();
      router.replace(query ? `/historico?${query}` : '/historico');
    },
    [filtros, router],
  );

  const [busca, setBusca] = useState(filtros.q);

  useEffect(() => {
    setBusca(filtros.q);
  }, [filtros.q]);

  useEffect(() => {
    if (busca === filtros.q) return;
    const timer = setTimeout(() => atualizar({ q: busca, pagina: 1 }), 300);
    return () => clearTimeout(timer);
  }, [busca, filtros.q, atualizar]);

  const consulta = useQuery({
    queryKey: ['adaptacoes', filtros],
    queryFn: async () =>
      PaginaAdaptacoesSchema.parse(
        await api.listar({
          pagina: filtros.pagina,
          tamanho_pagina: LIMITES.paginaPadrao,
          formato: filtros.formato,
          perfil: filtros.perfil,
          q: filtros.q,
        }),
      ),
    staleTime: 30_000,
  });

  return {
    data: consulta.data,
    isLoading: consulta.isLoading,
    error: consulta.error,
    refetch: consulta.refetch,
    filtros,
    busca,
    setBusca,
    atualizar,
  };
}
```

`src/components/views/HistoricoView.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAdaptationHistory } from '@/features/adaptations/useAdaptationHistory';
import { FORMATOS, PERFIS } from '@/lib/constants';
import { formatarDataRelativa, formatarPercentual } from '@/lib/formatadores';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';

export function HistoricoView() {
  const { data, isLoading, error, refetch, filtros, busca, setBusca, atualizar } = useAdaptationHistory();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{M.historico.titulo}</h1>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="busca">
          {M.historico.busca}
        </label>
        <input
          id="busca"
          type="search"
          value={busca}
          placeholder={M.historico.busca}
          onChange={(e) => setBusca(e.target.value)}
          className="h-10 min-w-[240px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="filtro-formato">
          {M.historico.todosFormatos}
        </label>
        <select
          id="filtro-formato"
          value={filtros.formato ?? ''}
          onChange={(e) => atualizar({ formato: e.target.value || undefined, pagina: 1 })}
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.historico.todosFormatos}</option>
          {FORMATOS.map((f) => (
            <option key={f.valor} value={f.valor}>
              {f.rotulo}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="filtro-perfil">
          {M.historico.todosPerfis}
        </label>
        <select
          id="filtro-perfil"
          value={filtros.perfil ?? ''}
          onChange={(e) => atualizar({ perfil: e.target.value || undefined, pagina: 1 })}
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.historico.todosPerfis}</option>
          {PERFIS.map((p) => (
            <option key={p.valor} value={p.valor}>
              {p.rotulo}
            </option>
          ))}
        </select>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label={M.comum.carregando}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[180px] w-full" />
          ))}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(error)}
          </p>
          <Button className="mt-4" onClick={() => refetch()}>
            {M.comum.tentarNovamente}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.historico.vazio}</p>
          <Button asChild className="mt-4">
            <Link href="/">{M.historico.vazioCta}</Link>
          </Button>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <>
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {data.itens.map((item) => (
              <li key={item.adaptacao_id}>
                <Link
                  href={`/resultado/${item.adaptacao_id}`}
                  className="block h-full rounded-xl border p-5 transition-colors hover:border-[var(--accent)]"
                >
                  <p className="font-medium">{item.documento.titulo}</p>
                  <p className="mt-1 text-xs text-[var(--fg-muted)]">
                    {formatarDataRelativa(item.criado_em)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Badge>{item.formato_gerado}</Badge>
                    <Badge variant="secondary">{item.perfil_aplicado}</Badge>
                    {item.status_upload === 'falha' && <Badge variant="destructive">{M.oci.falhaUpload}</Badge>}
                  </div>
                  <p className="mt-3 text-sm text-[var(--fg-muted)]">
                    {M.resultado.ancoragem}: {formatarPercentual(item.ancoragem_fonte_score)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>

          {data.total_paginas > 1 && (
            <nav aria-label="Paginação" className="flex items-center justify-center gap-3">
              <Button
                variant="outline"
                disabled={data.pagina <= 1}
                onClick={() => atualizar({ pagina: data.pagina - 1 })}
              >
                {M.historico.anterior}
              </Button>
              <span className="text-sm text-[var(--fg-muted)]">
                {M.historico.pagina(data.pagina, data.total_paginas)}
              </span>
              <Button
                variant="outline"
                disabled={data.pagina >= data.total_paginas}
                onClick={() => atualizar({ pagina: data.pagina + 1 })}
              >
                {M.historico.proxima}
              </Button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
```

`src/app/historico/page.tsx`:

```tsx
import { AppShell } from '@/components/layout/AppShell';
import { HistoricoView } from '@/components/views/HistoricoView';
import { Suspense } from 'react';

export default function HistoricoPage() {
  return (
    <AppShell>
      <Suspense>
        <HistoricoView />
      </Suspense>
    </AppShell>
  );
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm test -- src/components/views/HistoricoView.test.tsx`
Expected: PASS (5 testes).

O `<Suspense>` em volta de `HistoricoView` é obrigatório porque `useSearchParams` suspende durante o build/prerender do App Router.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(frontend): histórico paginado com filtros refletidos na URL"
```

---

### Task 13: Cenários de demonstração e banner de saúde

**Files:**
- Create: `src/components/forms/Cenarios.tsx`, `src/features/health/useHealth.ts`, `src/components/layout/HealthBanner.tsx`
- Modify: `src/lib/constants.ts` (CENARIOS), `src/lib/mensagens.ts` (banner), `src/components/forms/IngestionForm.tsx`, `src/components/layout/AppShell.tsx`
- Test: `src/components/forms/Cenarios.test.tsx`, `src/components/layout/HealthBanner.test.tsx`

**Interfaces:**
- Consumes: `useApi`, `HealthRespostaSchema`, `DOCUMENTO_DEMO`, `Cenario`, `M`.
- Produces: `CENARIOS`, `Cenarios({ aoDisparar, desabilitado })`, `useHealth()`, `HealthBanner`.

- [ ] **Step 1: Escrever os testes que falham**

`src/components/forms/Cenarios.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Cenarios } from './Cenarios';

describe('Cenarios', () => {
  it('oferece os três cenários do edital', () => {
    render(<Cenarios aoDisparar={vi.fn()} />);
    expect(screen.getByRole('button', { name: /iniciante \+ flashcards/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /desenvolvedor \+ quiz/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /gestor \+ resumo executivo/i })).toBeInTheDocument();
  });

  it('dispara o cenário escolhido', async () => {
    const aoDisparar = vi.fn();
    render(<Cenarios aoDisparar={aoDisparar} />);
    await userEvent.click(screen.getByRole('button', { name: /gestor \+ resumo executivo/i }));
    expect(aoDisparar).toHaveBeenCalledWith(
      expect.objectContaining({ perfil: 'Gestor', formato: 'ResumoExecutivo', nivel: 'Executivo' }),
    );
  });

  it('desabilita os chips durante uma geração', () => {
    render(<Cenarios aoDisparar={vi.fn()} desabilitado />);
    expect(screen.getByRole('button', { name: /iniciante \+ flashcards/i })).toBeDisabled();
  });
});
```

`src/components/layout/HealthBanner.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HealthBanner } from './HealthBanner';
import { ApiProvider } from '@/services/api/ApiProvider';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';

function renderizar(health: NovaMenteApi['health']) {
  const api = { health } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={api}>
      <QueryClientProvider client={client}>
        <HealthBanner />
      </QueryClientProvider>
    </ApiProvider>,
  );
}

describe('HealthBanner', () => {
  it('não renderiza nada quando está tudo ok', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        status: 'ok',
        versao: '0.1.0-mock',
        oci: 'ok',
        llm: 'ok',
        verificado_em: '2026-10-21T14:00:00Z',
      }),
    );
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('mostra banner quando a API está degradada', async () => {
    renderizar(
      vi.fn().mockResolvedValue({
        status: 'degraded',
        versao: '0.1.0-mock',
        oci: 'indisponivel',
        llm: 'ok',
        verificado_em: '2026-10-21T14:00:00Z',
      }),
    );
    expect(await screen.findByRole('status')).toHaveTextContent(/oci: indisponivel/i);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm test -- src/components/forms/Cenarios.test.tsx src/components/layout/HealthBanner.test.tsx`
Expected: FAIL — módulos ausentes.

- [ ] **Step 3: Implementar cenários, health e integração**

`src/lib/constants.ts` — acrescentar:

```ts
export const CENARIOS = [
  {
    id: 'iniciante-flashcards',
    rotulo: 'Iniciante + Flashcards',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Iniciante',
    formato: 'Flashcards',
    nivel: 'Didatico',
  },
  {
    id: 'desenvolvedor-quiz',
    rotulo: 'Desenvolvedor + Quiz',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Desenvolvedor',
    formato: 'Quiz',
    nivel: 'Tecnico',
  },
  {
    id: 'gestor-resumo',
    rotulo: 'Gestor + Resumo Executivo',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Gestor',
    formato: 'ResumoExecutivo',
    nivel: 'Executivo',
  },
] as const;
```

`src/lib/mensagens.ts` — adicionar em `app`:

```ts
    degradado: (oci: string, llm: string) => `Serviço parcialmente indisponível — OCI: ${oci}, LLM: ${llm}`,
```

`src/components/forms/Cenarios.tsx`:

```tsx
'use client';

import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CENARIOS } from '@/lib/constants';
import type { Cenario } from '@/features/adaptations/useAdaptationForm';
import { M } from '@/lib/mensagens';

export function Cenarios({
  aoDisparar,
  desabilitado,
}: {
  aoDisparar: (cenario: Cenario) => void;
  desabilitado?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-xs uppercase tracking-wide text-[var(--fg-muted)]">{M.formulario.cenarios}</p>
      <div className="flex flex-wrap gap-2">
        {CENARIOS.map((cenario) => (
          <Button
            key={cenario.id}
            type="button"
            variant="outline"
            size="sm"
            disabled={desabilitado}
            onClick={() =>
              aoDisparar({
                titulo: cenario.titulo,
                perfil: cenario.perfil,
                formato: cenario.formato,
                nivel: cenario.nivel,
              })
            }
          >
            <Sparkles aria-hidden className="mr-2 h-3.5 w-3.5 text-[var(--accent)]" />
            {cenario.rotulo}
          </Button>
        ))}
      </div>
    </div>
  );
}
```

`src/components/forms/IngestionForm.tsx` — importar e renderizar antes do campo de título, usando `dispararCenario`:

```tsx
import { Cenarios } from './Cenarios';
import { DOCUMENTO_DEMO } from '@/lib/constants';

// no destructuring do hook:
const { form, aba, trocarAba, enviar, enviando, erroGeral, dispararCenario } = useAdaptationForm(onCriado);

// antes do bloco do título:
<Cenarios aoDisparar={(cenario) => dispararCenario(cenario, DOCUMENTO_DEMO)} desabilitado={desabilitado || enviando} />
```

`src/features/health/useHealth.ts`:

```ts
'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { HealthRespostaSchema } from '@/types/schemas';

export function useHealth() {
  const api = useApi();
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => HealthRespostaSchema.parse(await api.health()),
    refetchInterval: 60_000,
    staleTime: 60_000,
    retry: false,
  });
}
```

`src/components/layout/HealthBanner.tsx`:

```tsx
'use client';

import { AlertTriangle } from 'lucide-react';
import { useHealth } from '@/features/health/useHealth';
import { M } from '@/lib/mensagens';

export function HealthBanner() {
  const { data } = useHealth();
  if (!data || data.status === 'ok') return null;

  return (
    <p role="status" className="border-b border-[var(--warning)] bg-[var(--surface)] px-4 py-2 text-center text-sm text-[var(--warning)]">
      <AlertTriangle aria-hidden className="mr-2 inline h-4 w-4" />
      {M.app.degradado(data.oci, data.llm)}
    </p>
  );
}
```

`src/components/layout/AppShell.tsx` — importar e renderizar entre `<Header />` e `<main>`:

```tsx
import { HealthBanner } from './HealthBanner';

// ...
<Header />
<HealthBanner />
<main id="conteudo" ...>
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npm test -- src/components/forms src/components/layout`
Expected: PASS — 3 testes de cenários, 2 de banner e os testes anteriores de formulário/skin.

- [ ] **Step 5: Verificar a demo manualmente**

Run: `$env:NEXT_PUBLIC_API_MOCK=1; npm run dev`

Clique em cada um dos três chips e confirme que o job parte direto, sem preencher nada, e que os três caem em `/resultado/<id>` com formatos diferentes.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(frontend): cenários de demonstração e banner de saúde da API"
```

---

### Task 14: E2E dos três cenários e axe

**Files:**
- Create: `playwright.config.ts`, `e2e/1-gerar-flashcards.spec.ts`, `e2e/2-upload-quiz.spec.ts`, `e2e/3-historico-exportacao.spec.ts`, `e2e/4-acessibilidade.spec.ts`
- Modify: `package.json` (script `e2e`)

**Interfaces:**
- Consumes: app completo das Tasks 1–13.
- Produces: três fluxos verdes e axe sem violação crítica.

- [ ] **Step 1: Configurar o Playwright**

`playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    acceptDownloads: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { NEXT_PUBLIC_API_MOCK: '1' },
  },
});
```

- [ ] **Step 2: Escrever os testes e ver falhar**

`e2e/1-gerar-flashcards.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('cenário Iniciante + Flashcards gera, vira o cartão e exporta Markdown', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /iniciante \+ flashcards/i }).click();

  await expect(page).toHaveURL(/\/resultado\/01J/, { timeout: 25_000 });
  await expect(page.getByRole('heading', { name: /dominando redes na nuvem/i })).toBeVisible();
  await expect(page.getByText('O que é uma VCN na Oracle Cloud?')).toBeVisible();

  await page.getByRole('button', { name: /mostrar verso/i }).click();
  await expect(page.getByRole('button', { name: /mostrar frente/i })).toHaveAttribute('aria-pressed', 'true');

  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Exportar' }).click();
  await page.getByRole('menuitem', { name: 'Markdown' }).click();
  expect((await download).suggestedFilename()).toMatch(/^novamente-.*\.md$/);
});
```

`e2e/2-upload-quiz.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('upload de Markdown gera quiz, responde tudo e mostra placar', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de VCN para devs');
  await page.getByRole('tab', { name: /enviar arquivo/i }).click();
  await page.setInputFiles('input[type="file"]', {
    name: 'vcn.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# VCN\n\nA VCN é uma rede privada e personalizável na OCI.'),
  });
  await page.getByRole('radio', { name: /quiz interativo/i }).check();
  await page.getByRole('button', { name: /gerar material/i }).click();

  await expect(page).toHaveURL(/\/resultado\//, { timeout: 25_000 });
  await expect(page.getByRole('heading', { name: /vcn na prática/i })).toBeVisible();

  for (let i = 0; i < 6; i += 1) {
    await page.getByRole('radio').first().check();
    await page.getByRole('button', { name: 'Confirmar' }).click();
    await page.getByRole('button', { name: 'Próxima' }).click();
  }

  await expect(page.getByRole('heading', { name: 'Placar' })).toBeVisible();
  await expect(page.getByText(/\d+ \/ 6/)).toBeVisible();
});
```

`e2e/3-historico-exportacao.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('histórico reabre pacote, baixa JSON e desabilita CSV para não-Flashcards', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/título do documento/i).fill('Manual de operações VCN');
  await page.getByLabel(/conteúdo técnico/i).fill('A Virtual Cloud Network é uma rede privada. '.repeat(8));
  await page.getByRole('radio', { name: /^tutorial/i }).check();
  await page.getByRole('button', { name: /gerar material/i }).click();

  await expect(page).toHaveURL(/\/resultado\//, { timeout: 25_000 });

  await page.getByRole('link', { name: 'Histórico' }).click();
  await expect(page.getByText('Manual de operações VCN').first()).toBeVisible();
  await page.getByText('Manual de operações VCN').first().click();

  await expect(page).toHaveURL(/\/resultado\//);
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: /baixar json/i }).click();
  expect((await download).suggestedFilename()).toMatch(/\.json$/);

  await page.getByRole('button', { name: 'Exportar' }).click();
  await expect(page.getByRole('menuitem', { name: /csv/i })).toHaveAttribute('aria-disabled', 'true');
});
```

`e2e/4-acessibilidade.spec.ts`:

```ts
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const ROTAS = ['/', '/historico', '/resultado/01JAVCNFLCARD00000000001'];

for (const rota of ROTAS) {
  test(`sem violação crítica de acessibilidade em ${rota}`, async ({ page }) => {
    await page.goto(rota);
    await page.waitForLoadState('networkidle');

    const resultado = await new AxeBuilder({ page }).analyze();
    const criticas = resultado.violations.filter((v) => v.impact === 'critical');
    expect(criticas, JSON.stringify(criticas, null, 2)).toEqual([]);
  });
}
```

- [ ] **Step 3: Rodar a suíte e ajustar seletores**

Run: `npx playwright test`
Expected: os 6 testes executam. Falhas de seletor, tempo de espera ou texto são corrigidas no teste; falha de comportamento é corrigida no app.

- [ ] **Step 4: Rodar até ficar verde**

Run: `npx playwright test`
Expected: 6 testes verdes (3 fluxos + 3 rotas no axe).

Se o axe reprovar algo, corrija o componente — não relaxe o filtro de `critical`.

- [ ] **Step 5: Rodar contra build de produção**

Run: `npm run build && npx playwright test`
Expected: mesmos 6 testes verdes com `webServer` reaproveitando o servidor.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "test(frontend): e2e dos três cenários do edital e axe nas rotas"
```

---

### Task 15: Performance, README e verificação final

**Files:**
- Create: `frontend/README.md`
- Modify: `package.json` (script `verificar`)
- Test: execução completa da suíte

**Interfaces:**
- Consumes: tudo.
- Produces: build dentro das metas, README e evidência de DoD.

- [ ] **Step 1: Medir o bundle**

Run: `npm run build`
Expected: build verde. Na tabela de rotas, a linha `/` deve ter First Load JS **abaixo de 180 kB**. Se passar:

1. confirme que `FlashcardDeck`, `InteractiveQuiz` e `MarkdownView` estão em `next/dynamic` no `ContentRenderer`;
2. rode `npx @next/bundle-analyzer` ou inspecione `.next/analyze` se configurado;
3. mova qualquer import pesado novo para `dynamic`.

Registre no README o número final medido.

- [ ] **Step 2: Medir CLS e LCP**

O `NEXT_PUBLIC_API_MOCK` é embutido no build, então o build de medição precisa dele:

Run: `$env:NEXT_PUBLIC_API_MOCK=1; npm run build; npm run start`

No Chrome DevTools → Lighthouse (desktop, cache desligado), rode em `/`, `/historico` e `/resultado/01JAVCNFLCARD00000000001`.

Expected: CLS = 0 e LCP < 2,5 s nas três. Se o CLS for maior que zero, o culpado é um bloco assíncrono sem altura reservada: aplique `min-h`/`Skeleton` com a mesma altura do conteúdo final.

- [ ] **Step 3: Rodar a cobertura**

Run: `npm run test:coverage`
Expected: verde, com `lines` e `functions` ≥ 80% em `src/features/**` e `src/services/**`. Se algum hook ficar abaixo, adicione o teste do caminho de erro que falta (não baixe o limite).

- [ ] **Step 4: Criar o script de verificação e o README**

`package.json` — adicionar em `scripts`:

```json
"verificar": "npm run typecheck && npm run lint && npm run test:coverage && npm run build && npm run e2e"
```

`frontend/README.md`:

```md
# NovaMente — Frontend

Interface Next.js do NovaMente: transforma documentação técnica em flashcards, quizzes, tutoriais e resumos executivos ancorados na fonte, com persistência no OCI Object Storage.

## Como rodar com mocks

```bash
npm install
$env:NEXT_PUBLIC_API_MOCK=1   # PowerShell
npm run dev
```

Abra http://localhost:3000. O MSW intercepta `/api/v1/*` e simula todo o pipeline, incluindo erros.

## Como apontar para o backend real

Sem `NEXT_PUBLIC_API_MOCK`, o Next faz rewrite de `/api/v1/*` para `API_BASE_URL` (padrão `http://localhost:8000`):

```bash
$env:API_BASE_URL='http://localhost:8000'
npm run dev
```

O contrato consumido está em `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md` (seções 5 e 6). O backend deve implementá-lo à risca: os handlers do MSW são o contrato executável.

## Scripts

| Comando | Função |
|---|---|
| `npm run dev` | Servidor de desenvolvimento |
| `npm run build` | Build de produção |
| `npm run typecheck` | TypeScript sem emitir |
| `npm run lint` | ESLint |
| `npm test` | Vitest |
| `npm run test:coverage` | Vitest com cobertura |
| `npm run storybook` | Catálogo de componentes |
| `npm run e2e` | Playwright |
| `npm run verificar` | Pipeline completo do DoD |

## Estrutura

- `src/components/ui` — átomos e primitivos (shadcn)
- `src/components/views` — visualizadores e páginas client
- `src/components/forms` — formulário de ingestão e cenários
- `src/features` — hooks de fluxo (formulário, job, histórico, exportação, OCI, saúde)
- `src/services/api` — `NovaMenteApi`, cliente HTTP e normalização de erros
- `src/mocks` — handlers MSW e fixtures validadas por zod
- `src/types` — schemas zod e tipos do contrato
- `src/themes` — tokens e skins `violeta` e `ciano`

## Decisões que valem saber

- Base HTTP é sempre relativa (`/api/v1`). Não existe `NEXT_PUBLIC_API_URL`.
- O mock é de rede (MSW), não de serviço: o mesmo `httpApiClient` roda em dev, teste, Storybook e produção.
- Toda resposta de pacote passa por `AdaptacaoPacoteSchema.parse`; contrato divergente vira `ErrorState`, nunca tela branca.
- Jobs são assíncronos com polling de 1,5 s (3 s após 60 s) e timeout de 5 min.
```

- [ ] **Step 5: Rodar o pipeline completo**

Run: `npm run verificar`
Expected: typecheck, lint, cobertura, build e 6 E2E verdes, em sequência, sem intervenção.

- [ ] **Step 6: Revisar o contrato contra a spec**

Abra `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md` nas seções 5 e 6 e confira, item por item:

- [ ] os 10 endpoints existem nos handlers;
- [ ] os códigos da tabela 6.12 estão todos em `CodigoErroSchema`, e os erros com gatilho de rede (`413`, `415`, `409`, `404`, `422`) têm handler no MSW;
- [ ] `LIMITES` (3/150/200/50.000/10.485.760/12/50) coincidem nos schemas e nos handlers;
- [ ] `ETAPAS` e as faixas de progresso estão na ordem da spec;
- [ ] o nome de arquivo usa documento + perfil + formato + id8.

Corrija qualquer divergência no código, não na spec — a spec foi aprovada.

- [ ] **Step 7: Commit final**

```bash
git add frontend
git add docs/superpowers/plans
git commit -m "docs(frontend): readme, script de verificação e fechamento do MVP"
```

---

## Self-Review

**Cobertura da spec:**

| Seção da spec | Task |
|---|---|
| 2 — escopo (formulário, 4 formatos, job, OCI, histórico, exportação, skins, demo) | 2, 6–13 |
| 4 — camadas, estrutura, registry, `NovaMenteApi`, estado | 2–12 |
| 5 — contrato de dados, zod, limites, job, envelopes | 3, 5 |
| 6 — 10 endpoints, erros, nomes de arquivo | 4, 5, 11 |
| 7 — rotas, formulário, job, deck, quiz, markdown, OCI, histórico | 6–13 |
| 8 — duas skins | 2 |
| 9 — performance (dynamic, CLS, bundle) | 7–10, 15 |
| 10 — acessibilidade (teclado, reduced motion, aria-live) | 8, 9, 14 |
| 11 — MSW, fixtures, camadas de teste, 3 E2E | 5, 8, 9, 14 |
| 12 — ordem de entrega | 1–15 |
| 13 — DoD | 15 |
| 14 — divergências | refletidas em 1, 3, 6 |
| 15 — riscos | 5 (contrato), 7 (timeout), 11 (csv), 8 (reduced motion) |

**Review Focus e onde cada um é testado:**

1. Slug e nome de arquivo — Task 3 (`slugify`, `nomeArquivoExportacao`), Task 11 (download).
2. Arquivo ilegível — Task 5 (`415`), Task 6 (erro no campo).
3. Progresso regressivo — Task 7 (`JobProgress` monotônico).
4. `tipo` inconsistente — Task 3 (`superRefine`), Task 11 (`ErroContrato` → `ErrorState`).
5. Texto no limite com emoji — Task 3 (contagem por caractere), Task 6 (contador da UI).

