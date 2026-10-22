import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { IngestionForm } from './IngestionForm';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { JobResposta } from '@/types/novamente';

const job: JobResposta = {
  job_id: 'j1',
  status: 'queued',
  etapa_atual: null,
  etapas_concluidas: [],
  progresso_percentual: 0,
  iniciado_em: '2026-10-21T14:02:11Z',
  atualizado_em: '2026-10-21T14:02:11Z',
};

function renderizar(criarPorTexto = vi.fn().mockResolvedValue(job), criarPorArquivo = vi.fn().mockResolvedValue(job)) {
  const api = { criarPorTexto, criarPorArquivo } as unknown as NovaMenteApi;
  const onCriado = vi.fn();
  render(
    <ApiProvider client={api}>
      <IngestionForm onCriado={onCriado} />
    </ApiProvider>,
  );
  return { criarPorTexto, criarPorArquivo, onCriado };
}

const titulo = () => screen.getByLabelText(/título do documento/i);
const texto = () => screen.getByLabelText(/conteúdo técnico/i);

describe('IngestionForm', () => {
  it('bloqueia envio com título curto e texto curto', async () => {
    const { criarPorTexto } = renderizar();
    await userEvent.type(titulo(), 'VC');
    fireEvent.change(texto(), { target: { value: 'curto' } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Informe um título de 3 a 150 caracteres.')).toBeInTheDocument();
    expect(screen.getByText('Mínimo de 200 caracteres.')).toBeInTheDocument();
    expect(criarPorTexto).not.toHaveBeenCalled();
  });

  it('envia o payload de texto com os parâmetros escolhidos', async () => {
    const { criarPorTexto, onCriado } = renderizar();
    await userEvent.type(titulo(), 'Introdução à VCN');
    fireEvent.change(texto(), { target: { value: 'a'.repeat(200) } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    await waitFor(() => expect(criarPorTexto).toHaveBeenCalledTimes(1));
    expect(criarPorTexto.mock.calls[0][0]).toMatchObject({
      documento_titulo: 'Introdução à VCN',
      documento_conteudo: 'a'.repeat(200),
      perfil_destinatario: 'Iniciante',
      formato_saida: 'Flashcards',
      nicho_setor: 'Geral',
      nivel_detalhe: 'Didatico',
    });
    expect(onCriado).toHaveBeenCalledWith(job, expect.any(Function));
  });

  it('preserva o título ao trocar de aba', async () => {
    renderizar();
    await userEvent.type(titulo(), 'Documento técnico');
    await userEvent.click(screen.getByRole('tab', { name: /enviar arquivo/i }));
    expect(titulo()).toHaveValue('Documento técnico');
  });

  it('rejeita extensão não suportada no upload', async () => {
    const { criarPorArquivo } = renderizar();
    const user = userEvent.setup({ applyAccept: false });
    await userEvent.type(titulo(), 'Manual interno');
    await userEvent.click(screen.getByRole('tab', { name: /enviar arquivo/i }));
    await user.upload(
      screen.getByLabelText(/arraste o arquivo/i),
      new File(['x'], 'manual.docx'),
    );
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Use um arquivo .pdf, .md ou .txt.')).toBeInTheDocument();
    expect(criarPorArquivo).not.toHaveBeenCalled();
  });

  it('devolve erro por campo vindo do servidor', async () => {
    const criarPorTexto = vi.fn().mockRejectedValue(
      new ErroApi(
        { erro: { codigo: 'VALIDACAO', mensagem: 'Dados inválidos', campos: { documento_titulo: 'Título já usado.' } } },
        422,
      ),
    );
    renderizar(criarPorTexto);
    await userEvent.type(titulo(), 'Introdução à VCN');
    fireEvent.change(texto(), { target: { value: 'a'.repeat(200) } });
    await userEvent.click(screen.getByRole('button', { name: /gerar material/i }));

    expect(await screen.findByText('Título já usado.')).toBeInTheDocument();
  });

  it('conta caracteres, não bytes, no contador', async () => {
    renderizar();
    fireEvent.change(texto(), { target: { value: '😀'.repeat(50) } });
    expect(await screen.findByText('50 / 50.000')).toBeInTheDocument();
  });
});
