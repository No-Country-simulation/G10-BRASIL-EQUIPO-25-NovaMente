'use client';

import Link from 'next/link';
import { FileJson } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExportMenu } from './ExportMenu';
import { FORMATOS, NICHOS, NIVEIS, PERFIS } from '@/lib/constants';
import { M } from '@/lib/mensagens';
import type { Exportacao } from '@/features/adaptations/useExport';
import type { AdaptacaoPacote } from '@/types/novamente';

export function ResultadoHeader({ pacote, exportacao }: { pacote: AdaptacaoPacote; exportacao: Exportacao }) {
  const { baixarJson, baixando, erro } = exportacao;
  const perfil = PERFIS.find((p) => p.valor === pacote.metadados.perfil_aplicado)?.rotulo;
  const formato = FORMATOS.find((f) => f.valor === pacote.metadados.formato_gerado)?.rotulo;
  const nivel = NIVEIS.find((n) => n.valor === pacote.metadados.nivel_detalhe_aplicado)?.rotulo;
  const nicho = NICHOS.find((n) => n.valor === pacote.metadados.nicho_setor_aplicado)?.rotulo;

  return (
    <header className="mb-8 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{pacote.conteudo_adaptado.titulo}</h1>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">
            {pacote.documento.titulo} · {M.resultado.tempoEstimado(pacote.metadados.tempo_estimado_estudo_minutos)}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <ExportMenu exportacao={exportacao} />
            <Button variant="outline" onClick={baixarJson} disabled={baixando === 'json'}>
              <FileJson aria-hidden className="mr-2 h-4 w-4" />
              {M.resultado.baixarJson}
            </Button>
            <Button asChild variant="ghost">
              <Link href="/">{M.resultado.novaGeracao}</Link>
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
