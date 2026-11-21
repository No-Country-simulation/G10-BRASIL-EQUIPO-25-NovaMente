import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { RequerSessao } from './RequerSessao';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { Sessao } from '@/types/novamente';

const mocks = vi.hoisted(() => ({ replace: vi.fn(), caminho: '/empresa/materiais' }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: vi.fn() }),
  usePathname: () => mocks.caminho,
  useSearchParams: () => new URLSearchParams(),
}));

const naoAutenticado = () =>
  new ErroApi({ erro: { codigo: 'NAO_AUTENTICADO', mensagem: 'Entre para continuar.' } }, 401);

function renderGuarda(
  perfil: Sessao['tipo'],
  api: Partial<NovaMenteApi> = {},
) {
  const cliente = {
    configAuth: vi.fn().mockResolvedValue({ auth_habilitada: true, demo_habilitado: false }),
    obterSessao: vi.fn().mockRejectedValue(naoAutenticado()),
    sair: vi.fn().mockResolvedValue(undefined),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <ApiProvider client={cliente}>
      <QueryClientProvider client={client}>
        <RequerSessao perfil={perfil}>
          <p>Conteúdo protegido</p>
        </RequerSessao>
      </QueryClientProvider>
    </ApiProvider>,
  );
  return { api: cliente, client };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.caminho = '/empresa/materiais';
  window.localStorage.clear();
});

describe('RequerSessao', () => {
  it('com login desligado, mostra o conteúdo sem consultar a sessão', async () => {
    const { api } = renderGuarda('empresa', {
      configAuth: vi.fn().mockResolvedValue({ auth_habilitada: false, demo_habilitado: false }),
    });

    expect(await screen.findByText('Conteúdo protegido')).toBeInTheDocument();
    expect(api.obterSessao).not.toHaveBeenCalled();
  });

  it('sem sessão, leva para a entrada guardando a página pedida', async () => {
    renderGuarda('empresa');

    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith(
        '/entrar?perfil=empresa&proximo=%2Fempresa%2Fmateriais',
      ),
    );
    expect(screen.queryByText('Conteúdo protegido')).not.toBeInTheDocument();
  });

  it('empresa logada vê o conteúdo', async () => {
    renderGuarda('empresa', {
      obterSessao: vi.fn().mockResolvedValue({ tipo: 'empresa', email: 'empresa@demo.com' }),
    });

    expect(await screen.findByText('Conteúdo protegido')).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it('aluno logado na área do aluno recebe a identidade da sessão antes do conteúdo', async () => {
    mocks.caminho = '/aluno';
    renderGuarda('aluno', {
      obterSessao: vi.fn().mockResolvedValue({ tipo: 'aluno', aluno_id: 'A1', nome: 'Ana Beatriz' }),
    });

    expect(await screen.findByText('Conteúdo protegido')).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(CHAVE_IDENTIDADE_ALUNO) ?? '{}')).toEqual({
      aluno_id: 'A1',
      nome: 'Ana Beatriz',
    });
  });

  it('aluno na área da empresa vê o aviso e pode sair para trocar de conta', async () => {
    const { api } = renderGuarda('empresa', {
      obterSessao: vi.fn().mockResolvedValue({ tipo: 'aluno', aluno_id: 'A1', nome: 'Ana Beatriz' }),
    });

    expect(await screen.findByText(M.entrar.perfilErrado.tituloEmpresa)).toBeInTheDocument();
    expect(screen.queryByText('Conteúdo protegido')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: M.entrar.perfilErrado.sair }));
    await waitFor(() => expect(api.sair).toHaveBeenCalled());
    await waitFor(() =>
      expect(mocks.replace).toHaveBeenCalledWith(
        '/entrar?perfil=empresa&proximo=%2Fempresa%2Fmateriais',
      ),
    );
  });

  it('sessão derrubada no meio do uso volta para a entrada', async () => {
    const { client } = renderGuarda('empresa', {
      obterSessao: vi.fn().mockResolvedValue({ tipo: 'empresa', email: 'empresa@demo.com' }),
    });
    await screen.findByText('Conteúdo protegido');

    client.setQueryData(['sessao'], null);

    await waitFor(() => expect(mocks.replace).toHaveBeenCalled());
    expect(screen.queryByText('Conteúdo protegido')).not.toBeInTheDocument();
  });
});
