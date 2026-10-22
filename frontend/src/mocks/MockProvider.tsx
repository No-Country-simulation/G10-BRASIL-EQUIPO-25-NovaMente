'use client';

import { useEffect, useState } from 'react';

const MOCK_ATIVO = process.env.NEXT_PUBLIC_API_MOCK === '1';

// Garante uma única inicialização do worker mesmo com o duplo efeito do StrictMode.
let inicioWorker: Promise<void> | null = null;

function iniciarMock() {
  inicioWorker ??= import('./browser').then(async ({ worker }) => {
    await worker.start({ onUnhandledFrame: 'bypass' });
  });
  return inicioWorker;
}

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [pronto, setPronto] = useState(!MOCK_ATIVO);

  useEffect(() => {
    if (pronto) return;
    let cancelado = false;
    iniciarMock().then(() => {
      if (!cancelado) setPronto(true);
    });
    return () => {
      cancelado = true;
    };
  }, [pronto]);

  if (!pronto) {
    return (
      <div className="p-8 text-sm text-[var(--fg-muted)]">Preparando ambiente de demonstração…</div>
    );
  }
  return <>{children}</>;
}
