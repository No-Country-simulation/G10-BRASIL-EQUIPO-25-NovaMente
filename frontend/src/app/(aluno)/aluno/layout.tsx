import type { Metadata } from 'next';
import { AlunoShell } from '@/components/layout/AlunoShell';

export const metadata: Metadata = {
  title: 'Área do aluno',
  robots: { index: false },
};

export default function AlunoLayout({ children }: { children: React.ReactNode }) {
  return <AlunoShell>{children}</AlunoShell>;
}
