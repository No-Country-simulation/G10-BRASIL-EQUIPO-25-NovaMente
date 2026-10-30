'use client';

import dynamic from 'next/dynamic';
import { Skeleton } from '@/components/ui/skeleton';
import { ErroContrato, mensagemDoErro } from '@/services/api/erros';
import type { ConteudoAdaptado } from '@/types/novamente';

const EsqueletoConteudo = () => <Skeleton className="h-[400px] w-full" />;

const FlashcardDeck = dynamic(() => import('./FlashcardDeck').then((m) => m.FlashcardDeck), {
  loading: EsqueletoConteudo,
});
const InteractiveQuiz = dynamic(() => import('./InteractiveQuiz').then((m) => m.InteractiveQuiz), {
  loading: EsqueletoConteudo,
});
const MarkdownView = dynamic(() => import('./MarkdownView').then((m) => m.MarkdownView), {
  loading: EsqueletoConteudo,
});

type Renderizador = (conteudo: ConteudoAdaptado) => React.ReactNode;

// Registry fechado por tipo: incluir um formato novo é adicionar uma entrada aqui,
// sem tocar na página que consome o conteúdo.
const REGISTRY: Record<ConteudoAdaptado['tipo'], Renderizador> = {
  flashcards: (c) => (c.tipo === 'flashcards' ? <FlashcardDeck itens={c.itens} /> : null),
  quiz: (c) => (c.tipo === 'quiz' ? <InteractiveQuiz itens={c.itens} /> : null),
  markdown: (c) => (c.tipo === 'markdown' ? <MarkdownView conteudo={c} /> : null),
};

export function ContentRenderer({ conteudo }: { conteudo: ConteudoAdaptado }) {
  // hasOwn evita que chaves herdadas do protótipo (constructor, toString, …)
  // sejam tratadas como formatos válidos. Em runtime o payload pode vir de fora
  // do contrato, então o fallback precisa existir de verdade.
  if (!Object.hasOwn(REGISTRY, conteudo.tipo)) {
    return (
      <p role="alert" className="rounded-md border border-[var(--danger)] p-4 text-sm text-[var(--danger)]">
        {mensagemDoErro(new ErroContrato('tipo fora do registry'))}
      </p>
    );
  }

  const renderizar = REGISTRY[conteudo.tipo];

  return <>{renderizar(conteudo)}</>;
}
