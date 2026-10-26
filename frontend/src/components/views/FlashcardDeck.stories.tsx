import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { FlashcardDeck } from './FlashcardDeck';
import flashcards from '@/mocks/fixtures/flashcards-vcn-iniciante.json';
import type { FlashcardItem } from '@/types/novamente';

const itens = (flashcards as unknown as { conteudo_adaptado: { itens: FlashcardItem[] } }).conteudo_adaptado.itens;

const meta: Meta<typeof FlashcardDeck> = {
  title: 'Views/FlashcardDeck',
  component: FlashcardDeck,
  args: { itens },
};

export default meta;
type Story = StoryObj<typeof FlashcardDeck>;

export const Padrao: Story = {};
