'use client';

import { useEffect, useState } from 'react';

// Garante uma única inicialização do worker mesmo com o duplo efeito do StrictMode.
let inicioWorker: Promise<void> | null = null;

function iniciarMock() {
  inicioWorker ??= import('./browser').then(async ({ worker }) => {
    await worker.start({ onUnhandledFrame: 'bypass' });
  });
  return inicioWorker;
}

export default function MockGate({ children }: { children: React.ReactNode }) {
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    let cancelado = false;
    iniciarMock().then(() => {
      if (!cancelado) setPronto(true);
    });
    return () => {
      cancelado = true;
    };
  }, []);

  if (!pronto) {
    return (
      <div className="p-8 text-sm text-[var(--fg-muted)]">Preparando ambiente de demonstração…</div>
    );
  }
  return <>{children}</>;
}
