import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Dropzone } from './Dropzone';

describe('Dropzone', () => {
  it('mostra nome e tamanho do arquivo selecionado', async () => {
    const aoSelecionar = vi.fn();
    render(<Dropzone arquivo={new File(['abc'], 'manual.pdf')} aoSelecionar={aoSelecionar} />);
    expect(screen.getByText('manual.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remover arquivo/i })).toBeInTheDocument();
  });

  it('entrega o arquivo escolhido pelo input', async () => {
    const aoSelecionar = vi.fn();
    render(<Dropzone arquivo={null} aoSelecionar={aoSelecionar} />);
    const arquivo = new File(['abc'], 'doc.md', { type: 'text/markdown' });
    const input = screen.getByLabelText(/arraste o arquivo/i);
    expect(input).toHaveAttribute('accept', '.pdf,.md,.txt');
    await userEvent.upload(input, arquivo);
    expect(aoSelecionar).toHaveBeenCalledWith(arquivo);
  });

  it('anuncia erro com role alert', () => {
    render(<Dropzone arquivo={null} aoSelecionar={vi.fn()} erro="Extensão inválida." />);
    expect(screen.getByRole('alert')).toHaveTextContent('Extensão inválida.');
  });
});
