'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ContentRenderer } from './ContentRenderer';
import { OCIPanel } from './OCIPanel';
import { ResultadoHeader } from './ResultadoHeader';
import { MaterialEditDialog } from '@/components/materiais/MaterialEditDialog';
import { useExport } from '@/features/adaptations/useExport';
import { useAtualizarMaterial } from '@/features/materiais/useMateriais';
import { useMaterial } from '@/features/materiais/useMaterial';
import { useOciStatus } from '@/features/oci/useOciStatus';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import type { MaterialAtualizacao, VisibilidadeMaterial } from '@/types/novamente';

interface Aviso {
  tipo: 'sucesso' | 'erro';
  texto: string;
}

export function ResultadoView({
  materialId,
  adaptacaoId,
}: {
  materialId?: string;
  adaptacaoId?: string;
}) {
  const id = materialId ?? adaptacaoId ?? '';
  const { data: detalhe, isPending, error, refetch } = useMaterial(id);
  const { data: oci } = useOciStatus();
  const atualizarMaterial = useAtualizarMaterial();
  const [editando, setEditando] = useState(false);
  const [alternando, setAlternando] = useState(false);
  const [aviso, setAviso] = useState<Aviso | null>(null);
  // Uma única instância para header e menu; o hook aceita null para poder ser
  // chamado antes dos early returns sem quebrar a ordem dos hooks.
  const pacote = detalhe?.pacote ?? null;
  const material = detalhe?.material ?? null;
  const exportacao = useExport(pacote);

  if (isPending) {
    // Espelha tags, classes e alturas do conteúdo final para o React reutilizar
    // os mesmos nós: header de 92 px no desktop (288 px em 390 px, quando o
    // título quebra e as ações empilham), introdução de duas linhas e grid.
    return (
      <div role="status">
        <span className="sr-only">{M.comum.carregando}</span>
        <header className="mb-8 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <Skeleton className="h-8 w-2/3" />
              <Skeleton className="mt-1 h-5 w-1/3" />
            </div>
            {/* Exportar / JSON / Editar / Publicar / Nova geração: no mobile os
                botões quebram em duas linhas; daí para cima cabem em uma (32 px). */}
            <div className="flex flex-col items-end gap-2">
              <div className="flex flex-wrap items-center justify-end gap-2">
                <Skeleton className="h-8 w-40" />
                <Skeleton className="h-8 w-36" />
                <Skeleton className="h-8 w-32" />
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-5 w-16" />
            <Skeleton className="h-5 w-24" />
          </div>
        </header>
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0">
            {/* O parágrafo real tem 48 px (duas linhas de 24 px). */}
            <Skeleton className="mb-6 min-h-12 w-full" />
            <Skeleton className="h-[440px] w-full" />
          </div>
          <Skeleton className="h-[420px] w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    const naoEncontrado = error instanceof ErroApi && error.status === 404;
    return (
      <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
        <h2 className="flex items-center gap-2 font-semibold text-[var(--danger)]">
          <AlertTriangle aria-hidden className="h-5 w-5" />
          {naoEncontrado ? M.resultado.naoEncontrado : mensagemDoErro(error)}
        </h2>
        <div className="mt-4 flex gap-3">
          {!naoEncontrado && <Button onClick={() => refetch()}>{M.comum.tentarNovamente}</Button>}
          <Button asChild variant="outline">
            <Link href={naoEncontrado ? ROTAS.empresaMateriais : ROTAS.empresaHistorico}>
              {naoEncontrado ? M.materiais.irParaMateriais : M.resultado.irParaHistorico}
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  if (!pacote || !material) return null;

  const alternarVisibilidade = async () => {
    const proxima: VisibilidadeMaterial =
      material.visibilidade === 'publicado' ? 'rascunho' : 'publicado';
    setAviso(null);
    setAlternando(true);
    try {
      await atualizarMaterial.mutateAsync({
        materialId: material.material_id,
        dados: { visibilidade: proxima },
      });
      setAviso({
        tipo: 'sucesso',
        texto:
          proxima === 'publicado' ? M.materiais.toastPublicado : M.materiais.toastDespublicado,
      });
    } catch (falha) {
      setAviso({ tipo: 'erro', texto: mensagemDoErro(falha) });
    } finally {
      setAlternando(false);
    }
  };

  const salvarEdicao = async (dados: MaterialAtualizacao) => {
    await atualizarMaterial.mutateAsync({ materialId: material.material_id, dados });
    setAviso({ tipo: 'sucesso', texto: M.materiais.toastEditado });
    setEditando(false);
  };

  return (
    <div>
      <ResultadoHeader
        material={material}
        pacote={pacote}
        exportacao={exportacao}
        alternando={alternando}
        onEditar={() => setEditando(true)}
        onAlternarVisibilidade={alternarVisibilidade}
      />

      {aviso && (
        <div
          role={aviso.tipo === 'sucesso' ? 'status' : 'alert'}
          aria-live="polite"
          className={
            aviso.tipo === 'sucesso'
              ? 'mb-6 rounded-lg border border-[var(--accent)] px-4 py-3 text-sm'
              : 'mb-6 rounded-lg border border-[var(--danger)] px-4 py-3 text-sm text-[var(--danger)]'
          }
        >
          {aviso.texto}
        </div>
      )}

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0">
          <p className="mb-6 text-[var(--fg-muted)]">
            {pacote.conteudo_adaptado.introducao_contextualizada}
          </p>
          <ContentRenderer conteudo={pacote.conteudo_adaptado} />
        </div>
        <OCIPanel armazenamento={pacote.armazenamento_oci} avaliacao={pacote.avaliacao_qualidade} oci={oci} />
      </div>

      {editando && (
        <MaterialEditDialog
          material={material}
          open
          onOpenChange={setEditando}
          salvar={salvarEdicao}
        />
      )}
    </div>
  );
}
