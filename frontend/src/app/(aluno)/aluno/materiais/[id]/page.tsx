import { Suspense } from 'react';
import {
  AlunoMaterialSkeleton,
  AlunoMaterialView,
} from '@/components/aluno/AlunoMaterialView';

export default async function AlunoMaterialPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense fallback={<AlunoMaterialSkeleton />}>
      <AlunoMaterialView materialId={id} />
    </Suspense>
  );
}
