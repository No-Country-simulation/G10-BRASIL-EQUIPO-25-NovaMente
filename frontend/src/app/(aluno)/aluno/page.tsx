import { Suspense } from 'react';
import { AreaAluno } from '@/components/aluno/AreaAluno';
import { IdentificacaoSkeleton } from '@/components/aluno/IdentificacaoAluno';

export default function AlunoPage() {
  return (
    <Suspense fallback={<IdentificacaoSkeleton />}>
      <AreaAluno />
    </Suspense>
  );
}
