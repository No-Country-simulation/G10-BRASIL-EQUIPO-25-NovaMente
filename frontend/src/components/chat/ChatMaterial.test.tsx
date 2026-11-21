import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ChatMaterial, mensagemErroChat } from './ChatMaterial';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { RespostaChat } from '@/types/novamente';

const MODELOS = {
  padrao: 'google/gemma-4-31b-it',
  modelos: ['google/gemma-4-31b-it', 'nvidia/nemotron-3.5-bolt-e4b'],
};

const fundamentada: RespostaChat = {
  resposta: 'Uma VCN é uma rede virtual privada. [F1]',
  citacoes: [
    { id: 'F1', origem: 'documento', excerto: 'A VCN é uma rede virtual privada na OCI.' },
    { id: 'P2', origem: 'pacote', excerto: 'VCN: rede privada.' },
  ],
  base: 'documento_e_pacote',
  recusou: false,
  fundamentada: true,
  ancoragem: 0.93,
  modelo: 'google/gemma-4-31b-it',
  trechos_usados: 2,
};

function renderizar(api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    listarModelosChat: vi.fn().mockResolvedValue(MODELOS),
    perguntarAluno: vi.fn().mockResolvedValue(fundamentada),
    perguntarEmpresa: vi.fn().mockResolvedValue(fundamentada),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>
        <ChatMaterial alvo={{ tipo: 'aluno', alunoId: 'A1', materialId: 'M1' }} />
      </QueryClientProvider>
    </ApiProvider>,
  );
  return cliente;
}

const campo = () => screen.getByLabelText(M.chat.campo);

describe('ChatMaterial', () => {
  it('marca o chat como experimental no título e ao lado do seletor de modelo', async () => {
    renderizar();

    expect(screen.getByRole('heading', { name: new RegExp(M.chat.experimental) })).toBeInTheDocument();
    expect(screen.getByText(M.chat.avisoExperimental)).toBeInTheDocument();
    await screen.findByLabelText(M.chat.modelo);
    expect(screen.getAllByText(M.chat.experimental)).toHaveLength(2);
  });

  it('começa vazio, com o botão desabilitado', () => {
    renderizar();

    expect(screen.getByText(M.chat.vazio)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: M.chat.enviar })).toBeDisabled();
  });

  it('envia a pergunta, mostra resposta com fontes e limpa o campo', async () => {
    const api = renderizar();
    const usuario = userEvent.setup();

    await usuario.type(campo(), 'O que é VCN?');
    await usuario.click(screen.getByRole('button', { name: M.chat.enviar }));

    const log = screen.getByRole('log', { name: M.chat.historico });
    expect(await within(log).findByText(/Uma VCN é uma rede virtual privada/)).toBeInTheDocument();
    expect(within(log).getByText('O que é VCN?')).toBeInTheDocument();
    expect(within(log).getByText(M.chat.fontes(2))).toBeInTheDocument();
    expect(within(log).getByText(/\[F1\] · Documento/)).toBeInTheDocument();
    expect(within(log).getByText(/\[P2\] · Material/)).toBeInTheDocument();
    expect(campo()).toHaveValue('');
    expect(api.perguntarAluno).toHaveBeenCalledWith('A1', 'M1', {
      pergunta: 'O que é VCN?',
      historico: [],
      modelo: 'google/gemma-4-31b-it',
    });
  });

  it('Enter envia e Shift+Enter quebra a linha', async () => {
    const api = renderizar();
    const usuario = userEvent.setup();

    await usuario.type(campo(), 'Linha 1{Shift>}{Enter}{/Shift}Linha 2');
    expect(campo()).toHaveValue('Linha 1\nLinha 2');
    expect(api.perguntarAluno).not.toHaveBeenCalled();

    await usuario.type(campo(), '{Enter}');
    await waitFor(() => expect(api.perguntarAluno).toHaveBeenCalledOnce());
  });

  it('envia o modelo escolhido no seletor', async () => {
    const api = renderizar();
    const usuario = userEvent.setup();

    const seletor = await screen.findByLabelText(M.chat.modelo);
    await usuario.selectOptions(seletor, 'nvidia/nemotron-3.5-bolt-e4b');
    await usuario.type(campo(), 'Pergunta');
    await usuario.click(screen.getByRole('button', { name: M.chat.enviar }));

    await waitFor(() =>
      expect(api.perguntarAluno).toHaveBeenCalledWith(
        'A1',
        'M1',
        expect.objectContaining({ modelo: 'nvidia/nemotron-3.5-bolt-e4b' }),
      ),
    );
  });

  it('sem lista de modelos esconde o seletor e pergunta sem o campo `modelo`', async () => {
    const usuario = userEvent.setup();
    const listarModelosChat = vi.fn().mockRejectedValue(new Error('indisponível'));
    const api = renderizar({ listarModelosChat });

    await waitFor(() => expect(listarModelosChat).toHaveBeenCalled());
    expect(screen.queryByLabelText(M.chat.modelo)).not.toBeInTheDocument();

    await usuario.type(campo(), 'Pergunta{Enter}');
    await waitFor(() => expect(api.perguntarAluno).toHaveBeenCalledOnce());
    expect(vi.mocked(api.perguntarAluno).mock.calls[0][2]).not.toHaveProperty('modelo');
  });

  it('sinaliza recusa e resposta pouco ancorada', async () => {
    const usuario = userEvent.setup();
    renderizar({
      perguntarAluno: vi
        .fn()
        .mockResolvedValueOnce({
          ...fundamentada,
          resposta: 'Não encontrei isso no material.',
          citacoes: [],
          recusou: true,
          fundamentada: false,
          ancoragem: null,
        })
        .mockResolvedValueOnce({ ...fundamentada, fundamentada: false, ancoragem: 0.4 }),
    });

    await usuario.type(campo(), 'Pergunta fora{Enter}');
    expect(await screen.findByText(M.chat.semBase)).toBeInTheDocument();
    expect(screen.queryByText(M.chat.baixaAncoragem)).not.toBeInTheDocument();

    await usuario.type(campo(), 'Pergunta fraca{Enter}');
    expect(await screen.findByText(M.chat.baixaAncoragem)).toBeInTheDocument();
  });

  it('mostra o erro, mantém o texto e bloqueia o envio durante a espera do 429', async () => {
    const usuario = userEvent.setup();
    renderizar({
      perguntarAluno: vi.fn().mockRejectedValue(
        new ErroApi(
          { erro: { codigo: 'CHAT_LIMITE_EXCEDIDO', mensagem: 'x' } },
          429,
          30,
        ),
      ),
    });

    await usuario.type(campo(), 'Pergunta{Enter}');

    const alerta = await screen.findByRole('alert');
    expect(alerta).toHaveTextContent(M.chat.erros.CHAT_LIMITE_EXCEDIDO);
    expect(alerta).toHaveTextContent(M.chat.espera(30));
    expect(campo()).toHaveValue('Pergunta');
    expect(screen.getByRole('button', { name: M.chat.enviar })).toBeDisabled();
  });

  it('bloqueia pergunta acima do limite e mostra o contador', async () => {
    const api = renderizar();
    const usuario = userEvent.setup();

    await usuario.click(campo());
    await usuario.paste('a'.repeat(1001));

    expect(campo()).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByText(new RegExp(M.chat.contador(1001, 1000)))).toBeInTheDocument();
    expect(screen.getByRole('button', { name: M.chat.enviar })).toBeDisabled();
    expect(api.perguntarAluno).not.toHaveBeenCalled();
  });

  it('limpa a conversa', async () => {
    const usuario = userEvent.setup();
    renderizar();

    await usuario.type(campo(), 'Pergunta{Enter}');
    await screen.findByText(/Uma VCN é uma rede/);
    await usuario.click(screen.getByRole('button', { name: M.chat.limpar }));

    expect(screen.getByText(M.chat.vazio)).toBeInTheDocument();
  });
});

describe('mensagemErroChat', () => {
  it('usa o texto próprio do código e cai no genérico quando não há', () => {
    const tempo = new ErroApi({ erro: { codigo: 'CHAT_TEMPO_ESGOTADO', mensagem: 'x' } }, 504);
    const aluno = new ErroApi(
      { erro: { codigo: 'ALUNO_INATIVO', mensagem: 'Aluno inativo.' } },
      403,
    );

    expect(mensagemErroChat(tempo)).toBe(M.chat.erros.CHAT_TEMPO_ESGOTADO);
    expect(mensagemErroChat(aluno)).toBe('Aluno inativo.');
    expect(mensagemErroChat(new Error('?'))).toBe(M.erro.generico);
  });
});
