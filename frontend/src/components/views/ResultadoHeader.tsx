'use client';

import Link from 'next/link';
import { FileJson } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExportMenu } from './ExportMenu';
import { FORMATOS, NICHOS, NIVEIS, PERFIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import type { Exportacao } from '@/features/adaptations/useExport';
import type { AdaptacaoPacote, MaterialResumo } from '@/types/novamente';

export interface ResultadoHeaderProps {
  material: MaterialResumo;
  pacote: AdaptacaoPacote;
  exportacao: Exportacao;
  alternando: boolean;
  onEditar: () => void;
  onAlternarVisibilidade: () => void;
}

export function ResultadoHeader({
  material,
  pacote,
  exportacao,
  alternando,
  onEditar,
  onAlternarVisibilidade,
}: ResultadoHeaderProps) {
  const { baixarJson, baixando, erro } = exportacao;
  const perfil = PERFIS.find((p) => p.valor === material.perfil)?.rotulo;
  const formato = FORMATOS.find((f) => f.valor === material.formato)?.rotulo;
  const nivel = NIVEIS.find((n) => n.valor === material.nivel)?.rotulo;
  const nicho = NICHOS.find((n) => n.valor === material.nicho)?.rotulo;
  const publicado = material.visibilidade === 'publicado';

  return (
    <header className="mb-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold">{material.titulo}</h1>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">
            {material.documento_titulo} ·{' '}
            {M.resultado.tempoEstimado(material.tempo_estimado_estudo_minutos)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ExportMenu exportacao={exportacao} />
            <Button variant="outline" onClick={baixarJson} disabled={baixando === 'json'}>
              <FileJson aria-hidden className="mr-2 h-4 w-4" />
              {M.resultado.baixarJson}
            </Button>
            <Button variant="outline" onClick={onEditar}>
              {M.materiais.editar}
            </Button>
            <Button variant="outline" disabled={alternando} onClick={onAlternarVisibilidade}>
              {publicado ? M.materiais.despublicar : M.materiais.publicar}
            </Button>
            <Button asChild variant="ghost">
              <Link href={ROTAS.empresaGerar}>{M.resultado.novaGeracao}</Link>
            </Button>
          </div>
          {erro && (
            <p role="alert" className="text-sm text-[var(--danger)]">
              {erro}
            </p>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Badge variant={publicado ? 'default' : 'outline'}>
          {publicado ? M.materiais.publicado : M.materiais.rascunho}
        </Badge>
        {perfil && <Badge variant="secondary">{perfil}</Badge>}
        {formato && <Badge>{formato}</Badge>}
        {nivel && <Badge variant="outline">{nivel}</Badge>}
        {nicho && <Badge variant="outline">{nicho}</Badge>}
        {pacote.metadados.conceitos_chave.slice(0, 4).map((conceito) => (
          <Badge key={conceito} variant="outline">
            {conceito}
          </Badge>
        ))}
      </div>
    </header>
  );
}
