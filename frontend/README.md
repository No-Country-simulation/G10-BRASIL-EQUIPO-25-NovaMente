This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.

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
