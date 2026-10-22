import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContentRenderer } from './ContentRenderer';
import type { ConteudoAdaptado } from '@/types/novamente';

// O primeiro carregamento de cada chunk dinâmico paga a transformação do módulo
// pelo Vite; em máquina fria isso passa do timeout padrão de 1s do findBy e dos
// 5s do teste.
const ESPERA_CHUNK_MS = 20_000;

const flashcards: ConteudoAdaptado = {
  tipo: 'flashcards',
  titulo: 'Deck',
  introducao_contextualizada: 'Intro',
  itens: [
    { frente: 'Frente A', verso: 'Verso A' },
    { frente: 'Frente B', verso: 'Verso B' },
    { frente: 'Frente C', verso: 'Verso C' },
  ],
};

describe('ContentRenderer', () => {
  it(
    'despacha flashcards para o deck',
    async () => {
      render(<ContentRenderer conteudo={flashcards} />);
      expect(await screen.findByText('Frente A', undefined, { timeout: ESPERA_CHUNK_MS })).toBeInTheDocument();
      expect(screen.getByText('1 / 3')).toBeInTheDocument();
    },
    ESPERA_CHUNK_MS,
  );

  it(
    'despacha quiz para o quiz interativo',
    async () => {
      render(
        <ContentRenderer
          conteudo={{
            tipo: 'quiz',
            titulo: 'Quiz',
            introducao_contextualizada: 'Intro',
            itens: [{ pergunta: 'Pergunta X?', opcoes: ['a', 'b'], resposta_correta: 0, explicacao: 'porque' }],
          }}
        />,
      );
      expect(await screen.findByText('Pergunta X?', undefined, { timeout: ESPERA_CHUNK_MS })).toBeInTheDocument();
    },
    ESPERA_CHUNK_MS,
  );

  it(
    'renderiza markdown e remove script malicioso',
    async () => {
      render(
        <ContentRenderer
          conteudo={{
            tipo: 'markdown',
            titulo: 'Tutorial',
            introducao_contextualizada: 'Intro',
            itens: '## Passo 1\n\nTexto seguro.\n\n<script>alert(1)</script>',
          }}
        />,
      );
      expect(
        await screen.findByRole('heading', { name: 'Passo 1' }, { timeout: ESPERA_CHUNK_MS }),
      ).toBeInTheDocument();
      expect(document.querySelector('script')).toBeNull();
    },
    ESPERA_CHUNK_MS,
  );

  it('cai em ErrorState quando o tipo não está no registry', () => {
    const invalido = { tipo: 'desconhecido', titulo: 'x', introducao_contextualizada: 'y', itens: 'z' } as never;
    render(<ContentRenderer conteudo={invalido} />);
    expect(screen.getByRole('alert')).toHaveTextContent('formato inesperado');
  });
});
