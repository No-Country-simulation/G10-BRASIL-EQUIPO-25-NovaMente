import { AppShell } from '@/components/layout/AppShell';
import { ResultadoView } from '@/components/views/ResultadoView';

export default async function ResultadoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <AppShell>
      <ResultadoView adaptacaoId={id} />
    </AppShell>
  );
}
