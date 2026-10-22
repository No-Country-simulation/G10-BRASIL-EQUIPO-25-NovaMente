'use client';

import dynamic from 'next/dynamic';

const MOCK_ATIVO = process.env.NEXT_PUBLIC_API_MOCK === '1';

// `ssr: false` mantém `msw/browser` fora do grafo SSR (o MSW exporta
// `./browser` com a condição `node: null`, que o Turbopack não resolve).
const MockGate = dynamic(() => import('./MockGate'), { ssr: false, loading: () => null });

export function MockProvider({ children }: { children: React.ReactNode }) {
  if (!MOCK_ATIVO) return <>{children}</>;
  return <MockGate>{children}</MockGate>;
}
