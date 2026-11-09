import { Suspense } from 'react';
import { MateriaisSkeleton, MateriaisView } from '@/components/materiais/MateriaisView';

export default function MateriaisPage() {
  return (
    <Suspense fallback={<MateriaisSkeleton />}>
      <MateriaisView />
    </Suspense>
  );
}
