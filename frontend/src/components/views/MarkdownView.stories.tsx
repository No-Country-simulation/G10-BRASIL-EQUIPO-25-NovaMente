import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { MarkdownView } from './MarkdownView';
import tutorial from '@/mocks/fixtures/tutorial-vcn-lider.json';

const conteudo = (tutorial as unknown as { conteudo_adaptado: never }).conteudo_adaptado;

const meta: Meta<typeof MarkdownView> = {
  title: 'Views/MarkdownView',
  component: MarkdownView,
  args: { conteudo },
};

export default meta;
type Story = StoryObj<typeof MarkdownView>;

export const Tutorial: Story = {};
