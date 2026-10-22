'use client';

import { AlertTriangle } from 'lucide-react';
import { useHealth } from '@/features/health/useHealth';
import { M } from '@/lib/mensagens';

export function HealthBanner() {
  const { data } = useHealth();
  // Falha de rede ou de contrato deixa `data` indefinido: a página segue sem banner.
  if (data?.status !== 'degraded') return null;

  return (
    <p
      role="status"
      className="border-b border-[var(--warning)] bg-[var(--surface)] px-4 py-2 text-center text-sm text-[var(--warning)]"
    >
      <AlertTriangle aria-hidden className="mr-2 inline h-4 w-4" />
      {M.app.degradado(data.oci, data.llm)}
    </p>
  );
}
