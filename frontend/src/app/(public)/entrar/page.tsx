import { Suspense } from 'react';
import type { Metadata } from 'next';
import { EntrarView } from '@/components/entrar/EntrarView';

export const metadata: Metadata = {
  title: 'Entrar — NovaMente',
  description: 'Acesse o NovaMente como empresa ou como aluno.',
  robots: { index: false },
};

export default function EntrarPage() {
  return (
    <Suspense fallback={null}>
      <EntrarView />
    </Suspense>
  );
}
