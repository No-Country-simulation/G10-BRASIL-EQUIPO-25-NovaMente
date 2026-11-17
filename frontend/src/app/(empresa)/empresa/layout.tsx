import type { Metadata } from 'next';
import { EmpresaShell } from '@/components/layout/EmpresaShell';

export const metadata: Metadata = {
  title: 'Área da empresa',
  robots: { index: false },
};

export default function EmpresaLayout({ children }: { children: React.ReactNode }) {
  return <EmpresaShell>{children}</EmpresaShell>;
}
