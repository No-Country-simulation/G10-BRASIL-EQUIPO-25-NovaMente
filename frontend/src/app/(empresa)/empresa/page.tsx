import { redirect } from 'next/navigation';
import { ROTAS } from '@/lib/rotas';

export default function EmpresaPage() {
  redirect(ROTAS.empresaGerar);
}
