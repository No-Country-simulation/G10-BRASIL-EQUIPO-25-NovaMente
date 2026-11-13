import { Suspense } from 'react';
import { HistoricoSkeleton, HistoricoView } from '@/components/views/HistoricoView';

export default function HistoricoPage() {
  return (
    <Suspense fallback={<HistoricoSkeleton />}>
      <HistoricoView />
    </Suspense>
  );
}
