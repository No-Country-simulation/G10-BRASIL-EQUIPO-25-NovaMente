import { Suspense } from 'react';
import {
  AlunoDetalheSkeleton,
  AlunoDetalheView,
} from '@/components/alunos/AlunoDetalheView';

export default async function AlunoDetalhePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense fallback={<AlunoDetalheSkeleton />}>
      <AlunoDetalheView alunoId={id} />
    </Suspense>
  );
}
