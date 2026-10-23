import { faixaAncoragem, formatarPercentual } from '@/lib/formatadores';

const CORES = {
  alta: 'bg-[var(--success)]',
  media: 'bg-[var(--warning)]',
  baixa: 'bg-[var(--danger)]',
} as const;

interface Props {
  valor: number;
  rotulo?: string;
}

export function ScoreGauge({ valor, rotulo }: Props) {
  const faixa = faixaAncoragem(valor);
  // O valor vem de um contrato 0..1; clampa só para a largura nunca estourar a barra.
  const largura = Math.min(100, Math.max(0, Math.round(valor * 100)));

  return (
    <div data-testid="score-gauge" data-faixa={faixa}>
      <div className="flex items-baseline justify-between">
        {rotulo && <span className="text-sm text-[var(--fg-muted)]">{rotulo}</span>}
        <span className="text-2xl font-semibold">{formatarPercentual(valor)}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-elevated)]" aria-hidden>
        <div className={`h-full ${CORES[faixa]}`} style={{ width: `${largura}%` }} />
      </div>
    </div>
  );
}
