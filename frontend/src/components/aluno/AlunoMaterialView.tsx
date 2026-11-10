'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ContentRenderer } from '@/components/views/ContentRenderer';
import { useIdentidadeAluno } from '@/features/aluno/useIdentidadeAluno';
import { useMaterialAluno } from '@/features/aluno/useMaterialAluno';
import { FORMATOS, NIVEIS, PERFIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';

const ROTULO_FORMATO = Object.fromEntries(FORMATOS.map((f) => [f.valor, f.rotulo]));
const ROTULO_PERFIL = Object.fromEntries(PERFIS.map((p) => [p.valor, p.rotulo]));
const ROTULO_NIVEL = Object.fromEntries(NIVEIS.map((n) => [n.valor, n.rotulo]));

export function AlunoMaterialSkeleton() {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">{M.aluno.material.carregando}</span>
      <Skeleton className="h-5 w-40" />
      <Skeleton className="h-9 w-2/3" />
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-[400px] w-full" />
    </div>
  );
}

export interface AlunoMaterialViewProps {
  materialId: string;
}

export function AlunoMaterialView({ materialId }: AlunoMaterialViewProps) {
  const router = useRouter();
  const { aluno, limpar } = useIdentidadeAluno();
  const { data, isPending, error, refetch } = useMaterialAluno(materialId);

  const erroSessao = error instanceof ErroApi && error.status === 403;

  useEffect(() => {
    if (erroSessao) {
      limpar();
      router.replace(ROTAS.aluno);
    }
  }, [erroSessao, limpar, router]);

  if (!aluno) {
    return (
      <div className="space-y-4">
        <div role="alert" className="rounded-xl border p-6">
          <p className="font-medium">{M.aluno.material.identifiqueSe}</p>
          <Button asChild className="mt-4">
            <Link href={ROTAS.aluno}>{M.aluno.material.irParaIdentificacao}</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (isPending || erroSessao) return <AlunoMaterialSkeleton />;

  if (error) {
    const indisponivel = error instanceof ErroApi && error.status === 404;
    return (
      <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
        <h2 className="flex items-center gap-2 font-semibold text-[var(--danger)]">
          <AlertTriangle aria-hidden className="h-5 w-5" />
          {indisponivel ? M.aluno.material.indisponivel : mensagemDoErro(error)}
        </h2>
        {indisponivel && (
          <p className="mt-2 text-sm text-[var(--fg-muted)]">
            {M.aluno.material.indisponivelDetalhe}
          </p>
        )}
        <div className="mt-4 flex gap-3">
          {!indisponivel && (
            <Button onClick={() => refetch()}>{M.comum.tentarNovamente}</Button>
          )}
          <Button asChild variant="outline">
            <Link href={ROTAS.aluno}>{M.aluno.material.voltarCatalogo}</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (!data) return <AlunoMaterialSkeleton />;

  const { material, pacote } = data;

  return (
    <div className="space-y-6">
      <Link
        href={ROTAS.aluno}
        className="text-sm text-[var(--fg-muted)] underline-offset-4 hover:underline"
      >
        {M.aluno.material.voltarCatalogo}
      </Link>

      <header className="space-y-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{material.titulo}</h1>
          <p className="text-sm text-[var(--fg-muted)]">{material.documento_titulo}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{ROTULO_FORMATO[material.formato]}</Badge>
          <Badge variant="secondary">{ROTULO_PERFIL[material.perfil]}</Badge>
          <Badge variant="outline">{ROTULO_NIVEL[material.nivel]}</Badge>
          <span className="text-sm text-[var(--fg-muted)]">
            {M.resultado.tempoEstimado(material.tempo_estimado_estudo_minutos)}
          </span>
        </div>
      </header>

      <div className="space-y-6">
        <p className="text-[var(--fg-muted)]">
          {pacote.conteudo_adaptado.introducao_contextualizada}
        </p>
        <ContentRenderer conteudo={pacote.conteudo_adaptado} />
      </div>
    </div>
  );
}
