import { Suspense } from 'react';
import { AlunosSkeleton, AlunosView } from '@/components/alunos/AlunosView';

export default function AlunosPage() {
  return (
    <Suspense fallback={<AlunosSkeleton />}>
      <AlunosView />
    </Suspense>
  );
}
