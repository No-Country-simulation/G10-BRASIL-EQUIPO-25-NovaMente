import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { OCIPanel } from './OCIPanel';
import flashcards from '@/mocks/fixtures/flashcards-vcn-iniciante.json';

const fixture = flashcards as unknown as {
  armazenamento_oci: never;
  avaliacao_qualidade: never;
};

const meta: Meta<typeof OCIPanel> = {
  title: 'Views/OCIPanel',
  component: OCIPanel,
  args: { armazenamento: fixture.armazenamento_oci, avaliacao: fixture.avaliacao_qualidade },
};

export default meta;
type Story = StoryObj<typeof OCIPanel>;

export const Sucesso: Story = {};

export const UploadFalhou: Story = {
  args: { armazenamento: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'falha' } },
};

export const OciNaoConfigurado: Story = {
  args: {
    armazenamento: { bucket: 'novamente', objeto_id: 'a.json', status_upload: 'falha' },
    oci: { configurado: false, mensagem: 'Credenciais ausentes', verificado_em: '2026-10-21T14:00:00Z' },
  },
};
