import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { InteractiveQuiz } from './InteractiveQuiz';
import quiz from '@/mocks/fixtures/quiz-vcn-desenvolvedor.json';
import type { QuizItem } from '@/types/novamente';

const itens = (quiz as unknown as { conteudo_adaptado: { itens: QuizItem[] } }).conteudo_adaptado.itens;

const meta: Meta<typeof InteractiveQuiz> = {
  title: 'Views/InteractiveQuiz',
  component: InteractiveQuiz,
  args: { itens },
};

export default meta;
type Story = StoryObj<typeof InteractiveQuiz>;

export const Padrao: Story = {};
