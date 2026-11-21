'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useIdentidadeAluno } from '@/features/aluno/useIdentidadeAluno';
import { useConfigAuth, useSair, useSessao } from '@/features/auth/useSessao';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { Sessao } from '@/types/novamente';

export interface RequerSessaoProps {
  perfil: Sessao['tipo'];
  children: React.ReactNode;
}

function Carregando() {
  return (
    <div className="space-y-3" aria-busy="true" aria-label={M.comum.carregando}>
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}

/**
 * Guarda das áreas logadas. Com o login desligado no servidor, deixa passar
 * (modo aberto, como antes). Com ele ligado, exige sessão do perfil certo e
 * leva quem não tem para `/entrar`, guardando a página de destino.
 */
export function RequerSessao({ perfil, children }: RequerSessaoProps) {
  const config = useConfigAuth();

  if (config.isLoading) return <Carregando />;

  if (config.error) {
    return (
      <div role="alert" className="mx-auto max-w-md space-y-3 py-10 text-center">
        <p className="text-sm text-[var(--danger)]">{mensagemDoErro(config.error)}</p>
        <Button variant="outline" onClick={() => config.refetch()}>
          {M.entrar.tentarNovamente}
        </Button>
      </div>
    );
  }

  if (!config.data?.auth_habilitada) return <>{children}</>;

  return <GuardaDeSessao perfil={perfil}>{children}</GuardaDeSessao>;
}

function GuardaDeSessao({ perfil, children }: RequerSessaoProps) {
  const router = useRouter();
  const caminho = usePathname();
  const sessao = useSessao();
  const sair = useSair();

  const semSessao = !sessao.isLoading && !sessao.error && !sessao.data;

  useEffect(() => {
    if (semSessao) router.replace(ROTAS.entrarComo(perfil, caminho));
  }, [semSessao, router, perfil, caminho]);

  if (sessao.isLoading || semSessao) return <Carregando />;

  if (sessao.error) {
    return (
      <div role="alert" className="mx-auto max-w-md space-y-3 py-10 text-center">
        <p className="text-sm text-[var(--danger)]">{mensagemDoErro(sessao.error)}</p>
        <Button variant="outline" onClick={() => sessao.refetch()}>
          {M.entrar.tentarNovamente}
        </Button>
      </div>
    );
  }

  const atual = sessao.data;
  if (!atual) return <Carregando />;

  if (atual.tipo !== perfil) {
    const daEmpresa = perfil === 'empresa';
    return (
      <section className="mx-auto max-w-md space-y-4 py-10 text-center">
        <h1 className="text-xl font-semibold">
          {daEmpresa ? M.entrar.perfilErrado.tituloEmpresa : M.entrar.perfilErrado.tituloAluno}
        </h1>
        <p className="text-sm text-[var(--fg-muted)]">
          {daEmpresa ? M.entrar.perfilErrado.descricaoEmpresa : M.entrar.perfilErrado.descricaoAluno}
        </p>
        <Button
          onClick={() =>
            sair.mutate(undefined, {
              onSettled: () => router.replace(ROTAS.entrarComo(perfil, caminho)),
            })
          }
          disabled={sair.isPending}
        >
          {sair.isPending ? M.app.saindo : M.entrar.perfilErrado.sair}
        </Button>
      </section>
    );
  }

  if (atual.tipo === 'aluno') {
    return (
      <PonteIdentidadeAluno alunoId={atual.aluno_id} nome={atual.nome}>
        {children}
      </PonteIdentidadeAluno>
    );
  }

  return <>{children}</>;
}

/**
 * As telas do aluno leem a identidade de `localStorage['novamente.aluno']`.
 * Com login, a sessão é a fonte da verdade: copia o aluno da sessão para lá
 * antes de mostrar a área, para o resto do app continuar igual.
 */
function PonteIdentidadeAluno({
  alunoId,
  nome,
  children,
}: {
  alunoId: string;
  nome: string;
  children: React.ReactNode;
}) {
  const { aluno, identificar } = useIdentidadeAluno();
  const sincronizado = aluno?.aluno_id === alunoId;

  useEffect(() => {
    if (!sincronizado) identificar({ aluno_id: alunoId, nome });
  }, [sincronizado, identificar, alunoId, nome]);

  if (!sincronizado) return <Carregando />;
  return <>{children}</>;
}
