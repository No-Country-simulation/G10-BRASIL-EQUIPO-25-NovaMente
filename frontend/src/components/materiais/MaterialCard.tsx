'use client';

import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FORMATOS, NIVEIS, PERFIS } from '@/lib/constants';
import { formatarDataRelativa, formatarPercentual } from '@/lib/formatadores';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { MaterialResumo } from '@/types/novamente';

export interface MaterialCardProps {
  material: MaterialResumo;
  alternando?: boolean;
  onEditar: (material: MaterialResumo) => void;
  onExcluir: (material: MaterialResumo) => void;
  onAlternarVisibilidade: (material: MaterialResumo) => void;
}

export function MaterialCard({
  material,
  alternando = false,
  onEditar,
  onExcluir,
  onAlternarVisibilidade,
}: MaterialCardProps) {
  const href = ROTAS.empresaResultado(material.material_id);
  const perfil = PERFIS.find((p) => p.valor === material.perfil)?.rotulo;
  const formato = FORMATOS.find((f) => f.valor === material.formato)?.rotulo;
  const nivel = NIVEIS.find((n) => n.valor === material.nivel)?.rotulo;
  const publicado = material.visibilidade === 'publicado';

  return (
    <article className="flex h-full flex-col rounded-xl border p-5 transition-colors hover:border-[var(--accent)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={href} className="font-medium hover:underline">
            {material.titulo}
          </Link>
          <p className="mt-1 truncate text-sm text-[var(--fg-muted)]">{material.documento_titulo}</p>
        </div>
        <Badge variant={publicado ? 'default' : 'outline'}>
          {publicado ? M.materiais.publicado : M.materiais.rascunho}
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {formato && <Badge>{formato}</Badge>}
        {perfil && <Badge variant="secondary">{perfil}</Badge>}
        {nivel && <Badge variant="outline">{nivel}</Badge>}
        {material.status_upload === 'falha' && (
          <Badge variant="destructive">{M.oci.falhaUpload}</Badge>
        )}
      </div>

      <p className="mt-3 text-sm text-[var(--fg-muted)]">
        {formatarDataRelativa(material.criado_em)} · {M.resultado.ancoragem}:{' '}
        {formatarPercentual(material.ancoragem_fonte_score)}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button asChild variant="outline" size="sm">
          <Link href={href}>{M.materiais.abrir}</Link>
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onEditar(material)}>
          {M.materiais.editar}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={alternando}
          onClick={() => onAlternarVisibilidade(material)}
        >
          {publicado ? M.materiais.despublicar : M.materiais.publicar}
        </Button>
        <Button variant="destructive" size="sm" onClick={() => onExcluir(material)}>
          {M.materiais.excluir}
        </Button>
      </div>
    </article>
  );
}
