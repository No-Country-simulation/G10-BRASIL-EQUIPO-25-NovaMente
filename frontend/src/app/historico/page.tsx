import { AppShell } from '@/components/layout/AppShell';
import { HistoricoSkeleton, HistoricoView } from '@/components/views/HistoricoView';
import { Suspense } from 'react';

export default function HistoricoPage() {
  return (
    <AppShell>
      <Suspense fallback={<HistoricoSkeleton />}>
        <HistoricoView />
      </Suspense>
    </AppShell>
  );
}
