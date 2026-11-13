'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MaterialCard } from './MaterialCard';
import { MaterialDeleteDialog } from './MaterialDeleteDialog';
import { MaterialEditDialog } from './MaterialEditDialog';
import {
  ORDENACOES_MATERIAIS,
  useAtualizarMaterial,
  useExcluirMaterial,
  useMateriais,
} from '@/features/materiais/useMateriais';
import { FORMATOS, PERFIS } from '@/lib/constants';
import { mensagemDoErro } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type {
  FormatoSaida,
  MaterialAtualizacao,
  MaterialResumo,
  PerfilDestinatario,
  VisibilidadeMaterial,
} from '@/types/novamente';
import type { OrdenacaoMateriais } from '@/features/materiais/useMateriais';

const ROTULOS_ORDENACAO: Record<OrdenacaoMateriais, string> = {
  'criado_em:desc': M.materiais.ordenarRecentes,
  'criado_em:asc': M.materiais.ordenarAntigos,
  'ancoragem:desc': M.materiais.ordenarAncoragem,
  'titulo:asc': M.materiais.ordenarTitulo,
};

interface Aviso {
  tipo: 'sucesso' | 'erro';
  texto: string;
  aviso?: string;
}

export function MateriaisSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      aria-busy="true"
      aria-label={M.comum.carregando}
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[230px] w-full" />
      ))}
    </div>
  );
}

export function MateriaisView() {
  const { data, isLoading, error, refetch, filtros, busca, setBusca, atualizar } = useMateriais();
  const atualizarMaterial = useAtualizarMaterial();
  const excluirMaterial = useExcluirMaterial();
  const campoBusca = useRef<HTMLInputElement>(null);
  const [editando, setEditando] = useState<MaterialResumo | null>(null);
  const [excluindo, setExcluindo] = useState<MaterialResumo | null>(null);
  const [alternandoId, setAlternandoId] = useState<string | null>(null);
  const [aviso, setAviso] = useState<Aviso | null>(null);

  const temFiltros = Boolean(filtros.q || filtros.formato || filtros.perfil || filtros.visibilidade);

  // O input é não-controlado para preservar o cursor e o foco enquanto o
  // debounce não confirma a busca na URL.
  useEffect(() => {
    const campo = campoBusca.current;
    if (campo && campo.value !== busca) campo.value = busca;
  }, [busca]);

  const alternarVisibilidade = async (material: MaterialResumo) => {
    const proxima: VisibilidadeMaterial =
      material.visibilidade === 'publicado' ? 'rascunho' : 'publicado';
    setAviso(null);
    setAlternandoId(material.material_id);
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
      setAlternandoId(null);
    }
  };

  const salvarEdicao = async (dados: MaterialAtualizacao) => {
    if (!editando) return;
    await atualizarMaterial.mutateAsync({ materialId: editando.material_id, dados });
    setAviso({ tipo: 'sucesso', texto: M.materiais.toastEditado });
    setEditando(null);
  };

  const excluir = async () => {
    if (!excluindo) return;
    const remocao = await excluirMaterial.mutateAsync(excluindo.material_id);
    setAviso({
      tipo: 'sucesso',
      texto: M.materiais.toastExcluido,
      aviso: remocao.oci_removido ? undefined : (remocao.aviso ?? M.materiais.remocao.avisoOciPadrao),
    });
    setExcluindo(null);
  };

  return (
    <div className="space-y-6" data-tour="empresa-materiais-lista">
      <h1 className="text-2xl font-semibold">{M.materiais.titulo}</h1>

      <div className="flex flex-wrap gap-3">
        <label className="sr-only" htmlFor="materiais-busca">
          {M.materiais.busca}
        </label>
        <input
          ref={campoBusca}
          id="materiais-busca"
          type="search"
          defaultValue={busca}
          placeholder={M.materiais.busca}
          onChange={(evento) => setBusca(evento.target.value)}
          className="h-10 min-w-[240px] flex-1 rounded-md border bg-[var(--surface)] px-3 text-sm"
        />

        <label className="sr-only" htmlFor="materiais-formato">
          {M.materiais.todosFormatos}
        </label>
        <select
          id="materiais-formato"
          value={filtros.formato ?? ''}
          onChange={(evento) =>
            atualizar({
              formato: (evento.target.value || undefined) as FormatoSaida | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.materiais.todosFormatos}</option>
          {FORMATOS.map((formato) => (
            <option key={formato.valor} value={formato.valor}>
              {formato.rotulo}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="materiais-perfil">
          {M.materiais.todosPerfis}
        </label>
        <select
          id="materiais-perfil"
          value={filtros.perfil ?? ''}
          onChange={(evento) =>
            atualizar({
              perfil: (evento.target.value || undefined) as PerfilDestinatario | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.materiais.todosPerfis}</option>
          {PERFIS.map((perfil) => (
            <option key={perfil.valor} value={perfil.valor}>
              {perfil.rotulo}
            </option>
          ))}
        </select>

        <label className="sr-only" htmlFor="materiais-visibilidade">
          {M.materiais.todasVisibilidades}
        </label>
        <select
          id="materiais-visibilidade"
          value={filtros.visibilidade ?? ''}
          onChange={(evento) =>
            atualizar({
              visibilidade: (evento.target.value || undefined) as
                | VisibilidadeMaterial
                | undefined,
              pagina: 1,
            })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          <option value="">{M.materiais.todasVisibilidades}</option>
          <option value="rascunho">{M.materiais.somenteRascunhos}</option>
          <option value="publicado">{M.materiais.somentePublicados}</option>
        </select>

        <label className="sr-only" htmlFor="materiais-ordenar">
          {M.materiais.ordenar}
        </label>
        <select
          id="materiais-ordenar"
          value={filtros.ordenar}
          onChange={(evento) =>
            atualizar({ ordenar: evento.target.value as OrdenacaoMateriais, pagina: 1 })
          }
          className="h-10 rounded-md border bg-[var(--surface)] px-3 text-sm"
        >
          {ORDENACOES_MATERIAIS.map((ordenacao) => (
            <option key={ordenacao} value={ordenacao}>
              {ROTULOS_ORDENACAO[ordenacao]}
            </option>
          ))}
        </select>
      </div>

      {aviso && (
        <div
          role={aviso.tipo === 'sucesso' ? 'status' : 'alert'}
          aria-live="polite"
          className={
            aviso.tipo === 'sucesso'
              ? 'rounded-lg border border-[var(--accent)] px-4 py-3 text-sm'
              : 'rounded-lg border border-[var(--danger)] px-4 py-3 text-sm text-[var(--danger)]'
          }
        >
          <p>{aviso.texto}</p>
          {aviso.aviso && <p className="mt-1 text-[var(--fg-muted)]">{aviso.aviso}</p>}
        </div>
      )}

      {isLoading && <MateriaisSkeleton />}

      {error && (
        <div role="alert" className="rounded-xl border border-[var(--danger)] p-6">
          <p className="flex items-center gap-2 text-[var(--danger)]">
            <AlertTriangle aria-hidden className="h-5 w-5" />
            {mensagemDoErro(error)}
          </p>
          <Button className="mt-4" onClick={() => refetch()}>
            {M.comum.tentarNovamente}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && data.total === 0 && temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.materiais.vazioFiltros}</p>
          <Button
            variant="outline"
            className="mt-4"
            onClick={() =>
              atualizar({
                q: '',
                formato: undefined,
                perfil: undefined,
                visibilidade: undefined,
                pagina: 1,
              })
            }
          >
            {M.materiais.limparFiltros}
          </Button>
        </div>
      )}

      {data && data.itens.length === 0 && !error && data.total === 0 && !temFiltros && (
        <div className="rounded-xl border border-dashed p-10 text-center">
          <p className="text-[var(--fg-muted)]">{M.materiais.vazio}</p>
          <Button asChild className="mt-4">
            <Link href={ROTAS.empresaGerar}>{M.materiais.vazioCta}</Link>
          </Button>
        </div>
      )}

      {data && data.itens.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.itens.map((material) => (
            <li key={material.material_id}>
              <MaterialCard
                material={material}
                alternando={alternandoId === material.material_id}
                onEditar={setEditando}
                onExcluir={setExcluindo}
                onAlternarVisibilidade={alternarVisibilidade}
              />
            </li>
          ))}
        </ul>
      )}

      {data && data.total > 0 && (
        <nav aria-label={M.materiais.paginacao} className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            disabled={data.pagina <= 1}
            onClick={() => atualizar({ pagina: data.pagina - 1 })}
          >
            {M.materiais.anterior}
          </Button>
          <span className="text-sm text-[var(--fg-muted)]">
            {M.materiais.pagina(data.pagina, data.total_paginas)}
          </span>
          <Button
            variant="outline"
            disabled={data.pagina >= data.total_paginas}
            onClick={() => atualizar({ pagina: data.pagina + 1 })}
          >
            {M.materiais.proxima}
          </Button>
        </nav>
      )}

      {editando && (
        <MaterialEditDialog
          material={editando}
          open
          onOpenChange={(aberto) => {
            if (!aberto) setEditando(null);
          }}
          salvar={salvarEdicao}
        />
      )}

      {excluindo && (
        <MaterialDeleteDialog
          material={excluindo}
          open
          onOpenChange={(aberto) => {
            if (!aberto) setExcluindo(null);
          }}
          excluir={excluir}
        />
      )}
    </div>
  );
}
