import { AppShell } from '@/components/layout/AppShell';
import { M } from '@/lib/mensagens';

export default function Home() {
  return <AppShell>{M.app.emConstrucao}</AppShell>;
}
