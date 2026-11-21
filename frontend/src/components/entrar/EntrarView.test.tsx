import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { EntrarView } from './EntrarView';
import { SkinProvider } from '@/features/theme/SkinProvider';
import { M } from '@/lib/mensagens';
import { ApiProvider } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import type { NovaMenteApi } from '@/services/api/NovaMenteApi';
import type { ConfigAuth, Sessao } from '@/types/novamente';

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  params: new URLSearchParams(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mocks.replace, push: mocks.push }),
  useSearchParams: () => mocks.params,
  usePathname: () => '/entrar',
}));

const ligado: ConfigAuth = { auth_habilitada: true, demo_habilitado: true };
const empresa: Sessao = { tipo: 'empresa', email: 'empresa@demo.com' };
const aluno: Sessao = { tipo: 'aluno', aluno_id: 'A1', nome: 'Ana Beatriz' };

const erroApi = (status: number, codigo: string, mensagem: string, retryAfter?: number) =>
  new ErroApi({ erro: { codigo: codigo as never, mensagem } }, status, retryAfter);

const CODIGO_ENVIADO = { mensagem: 'ok', expira_em_segundos: 600 };
const SENHA_FORTE = 'Aluno@1234';

function renderEntrar(api: Partial<NovaMenteApi> = {}) {
  const cliente = {
    configAuth: vi.fn().mockResolvedValue(ligado),
    obterSessao: vi.fn().mockRejectedValue(erroApi(401, 'NAO_AUTENTICADO', 'Entre para continuar.')),
    loginEmpresa: vi.fn().mockResolvedValue(CODIGO_ENVIADO),
    verificarEmpresa: vi.fn().mockResolvedValue(empresa),
    loginAluno: vi.fn().mockResolvedValue(CODIGO_ENVIADO),
    verificarAluno: vi.fn().mockResolvedValue(aluno),
    solicitarCodigoPrimeiroAcesso: vi.fn().mockResolvedValue(CODIGO_ENVIADO),
    definirSenhaAluno: vi.fn().mockResolvedValue(aluno),
    entrarDemo: vi.fn().mockResolvedValue(empresa),
    sair: vi.fn().mockResolvedValue(undefined),
    ...api,
  } as unknown as NovaMenteApi;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <SkinProvider>
      <ApiProvider client={cliente}>
        <QueryClientProvider client={client}>
          <EntrarView />
        </QueryClientProvider>
      </ApiProvider>
    </SkinProvider>,
  );
  return { api: cliente };
}

beforeEach(() => {
  mocks.replace.mockReset();
  mocks.push.mockReset();
  mocks.params = new URLSearchParams();
  window.localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

async function preencherEmpresa(email = 'Empresa@Demo.com', senha = SENHA_FORTE) {
  await userEvent.type(await screen.findByLabelText(M.entrar.empresa.email), email);
  await userEvent.type(screen.getByLabelText(M.entrar.empresa.senha), senha);
  await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.continuar }));
}

async function digitarCodigo(codigo: string) {
  await userEvent.type(await screen.findByLabelText(M.entrar.codigo.campo), codigo);
}

describe('EntrarView / empresa (senha + código)', () => {
  it('orienta o e-mail válido e descreve a senha exigida', async () => {
    renderEntrar();

    await screen.findByLabelText(M.entrar.empresa.email);
    expect(screen.getByText(M.entrar.email.dica)).toBeInTheDocument();
    expect(screen.getByText(M.entrar.senha.resumo)).toBeInTheDocument();
    expect(screen.getByLabelText(M.entrar.empresa.senha)).toHaveAccessibleDescription(
      M.entrar.senha.resumo,
    );
  });

  it('só abre a sessão depois da senha e do código do e-mail', async () => {
    const { api } = renderEntrar();

    await preencherEmpresa();

    expect(await screen.findByText(M.entrar.codigo.enviadoPara('empresa@demo.com'))).toBeInTheDocument();
    expect(api.loginEmpresa).toHaveBeenCalledWith({ email: 'Empresa@Demo.com', senha: SENHA_FORTE });
    expect(api.verificarEmpresa).not.toHaveBeenCalled();
    expect(mocks.replace).not.toHaveBeenCalled();
    expect(screen.getByText(M.entrar.codigo.spam)).toBeInTheDocument();

    await digitarCodigo('12a3456');
    expect(screen.getByLabelText(M.entrar.codigo.campo)).toHaveValue('123456');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.verificar }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar'));
    expect(api.verificarEmpresa).toHaveBeenCalledWith({
      email: 'Empresa@Demo.com',
      codigo: '123456',
    });
  });

  it('volta para a página pedida quando o `proximo` é seguro', async () => {
    mocks.params = new URLSearchParams({ perfil: 'empresa', proximo: '/empresa/materiais' });
    renderEntrar();

    await preencherEmpresa('a@b.com');
    await digitarCodigo('123456');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.verificar }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/materiais'));
  });

  it('ignora `proximo` externo', async () => {
    mocks.params = new URLSearchParams({ proximo: 'https://malicioso.com' });
    renderEntrar();

    await preencherEmpresa('a@b.com');
    await digitarCodigo('123456');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.verificar }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar'));
  });

  it('senha errada não avança para o código', async () => {
    renderEntrar({
      loginEmpresa: vi
        .fn()
        .mockRejectedValue(erroApi(401, 'CREDENCIAIS_INVALIDAS', 'E-mail ou senha incorretos.')),
    });

    await preencherEmpresa('a@b.com', 'errada');

    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha incorretos.');
    expect(screen.queryByLabelText(M.entrar.codigo.campo)).not.toBeInTheDocument();
  });

  it('código inválido mostra erro e permite tentar de novo', async () => {
    const verificarEmpresa = vi
      .fn()
      .mockRejectedValueOnce(erroApi(401, 'CODIGO_INVALIDO', 'Código inválido ou vencido.'))
      .mockResolvedValueOnce(empresa);
    renderEntrar({ verificarEmpresa });

    await preencherEmpresa('a@b.com');
    await digitarCodigo('000000');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.verificar }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Código inválido ou vencido.');
    expect(mocks.replace).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText(M.entrar.codigo.campo));
    await userEvent.type(screen.getByLabelText(M.entrar.codigo.campo), '123456');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.empresa.verificar }));
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar'));
  });

  it('informa a espera quando o limite de tentativas é atingido', async () => {
    renderEntrar({
      loginEmpresa: vi
        .fn()
        .mockRejectedValue(erroApi(429, 'AUTH_LIMITE_EXCEDIDO', 'Muitas tentativas.', 30)),
    });

    await preencherEmpresa('a@b.com');

    expect((await screen.findByRole('alert')).textContent).toMatch(/muitas tentativas.*30/i);
  });

  it('bloqueia o reenvio por 60 segundos e depois libera', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { api } = renderEntrar();
    await usuario.type(await screen.findByLabelText(M.entrar.empresa.email), 'a@b.com');
    await usuario.type(screen.getByLabelText(M.entrar.empresa.senha), SENHA_FORTE);
    await usuario.click(screen.getByRole('button', { name: M.entrar.empresa.continuar }));
    await screen.findByLabelText(M.entrar.codigo.campo);

    expect(screen.getByRole('button', { name: M.entrar.codigo.reenviarEm(60) })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    const reenviar = await screen.findByRole('button', { name: M.entrar.codigo.reenviar });
    await usuario.click(reenviar);
    await waitFor(() => expect(api.loginEmpresa).toHaveBeenCalledTimes(2));
  });

  it('voltar do código limpa a senha digitada', async () => {
    renderEntrar();

    await preencherEmpresa('a@b.com');
    await userEvent.click(await screen.findByRole('button', { name: M.entrar.codigo.voltar }));

    expect(screen.getByLabelText(M.entrar.empresa.email)).toHaveValue('a@b.com');
    expect(screen.getByLabelText(M.entrar.empresa.senha)).toHaveValue('');
  });

  it('alterna a visibilidade da senha', async () => {
    renderEntrar();

    const campo = await screen.findByLabelText(M.entrar.empresa.senha);
    expect(campo).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.senha.mostrar }));
    expect(campo).toHaveAttribute('type', 'text');
  });
});

describe('EntrarView / aluno (senha + código)', () => {
  beforeEach(() => {
    mocks.params = new URLSearchParams({ perfil: 'aluno' });
  });

  it('entra com e-mail e senha e depois com o código', async () => {
    const { api } = renderEntrar();

    await userEvent.type(await screen.findByLabelText(M.entrar.aluno.email), 'Ana.Silva@Exemplo.com');
    expect(screen.getByText(M.entrar.email.dica)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(M.entrar.aluno.senha), SENHA_FORTE);
    await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.continuar }));

    expect(await screen.findByText(M.entrar.codigo.enviadoPara('ana.silva@exemplo.com'))).toBeInTheDocument();
    expect(api.loginAluno).toHaveBeenCalledWith({
      email: 'Ana.Silva@Exemplo.com',
      senha: SENHA_FORTE,
    });

    await digitarCodigo('123456');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.verificar }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno'));
    expect(api.verificarAluno).toHaveBeenCalledWith({
      email: 'Ana.Silva@Exemplo.com',
      codigo: '123456',
    });
  });

  it('senha errada mostra o erro e não pede o código', async () => {
    renderEntrar({
      loginAluno: vi
        .fn()
        .mockRejectedValue(erroApi(401, 'CREDENCIAIS_INVALIDAS', 'E-mail ou senha incorretos.')),
    });

    await userEvent.type(await screen.findByLabelText(M.entrar.aluno.email), 'a@b.com');
    await userEvent.type(screen.getByLabelText(M.entrar.aluno.senha), 'errada');
    await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.continuar }));

    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha incorretos.');
    expect(screen.queryByLabelText(M.entrar.codigo.campo)).not.toBeInTheDocument();
  });

  describe('primeiro acesso / esqueci a senha', () => {
    async function abrirPrimeiroAcesso() {
      const retorno = renderEntrar();
      await userEvent.click(
        await screen.findByRole('button', { name: M.entrar.aluno.primeiroAcesso }),
      );
      await userEvent.type(await screen.findByLabelText(M.entrar.aluno.email), 'Bruno@Exemplo.com');
      await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.primeiro.enviarCodigo }));
      await screen.findByLabelText(M.entrar.codigo.campo);
      return retorno;
    }

    it('confirma o e-mail por código, cria a senha e entra', async () => {
      const { api } = await abrirPrimeiroAcesso();

      expect(api.solicitarCodigoPrimeiroAcesso).toHaveBeenCalledWith({ email: 'Bruno@Exemplo.com' });
      expect(screen.getByText(M.entrar.codigo.enviadoPara('bruno@exemplo.com'))).toBeInTheDocument();

      const botao = screen.getByRole('button', { name: M.entrar.aluno.primeiro.criarSenha });
      expect(botao).toBeDisabled();

      await digitarCodigo('123456');
      await userEvent.type(screen.getByLabelText(M.entrar.senha.criar), SENHA_FORTE);
      await userEvent.type(screen.getByLabelText(M.entrar.senha.repetir), SENHA_FORTE);
      expect(botao).toBeEnabled();
      await userEvent.click(botao);

      await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno'));
      expect(api.definirSenhaAluno).toHaveBeenCalledWith({
        email: 'bruno@exemplo.com',
        codigo: '123456',
        senha: SENHA_FORTE,
      });
    });

    it('marca os requisitos da senha enquanto a pessoa digita', async () => {
      await abrirPrimeiroAcesso();

      const campo = screen.getByLabelText(M.entrar.senha.criar);
      expect(campo).toHaveAccessibleDescription(/mínimo de 8 caracteres/i);
      const item = (rotulo: string) => screen.getByText(rotulo).closest('li') as HTMLElement;

      expect(item('Uma letra maiúscula')).toHaveTextContent('(pendente)');
      await userEvent.type(campo, 'Ab1');
      expect(item('Uma letra maiúscula')).toHaveTextContent('(atendido)');
      expect(item('Um número')).toHaveTextContent('(atendido)');
      expect(item('Mínimo de 8 caracteres')).toHaveTextContent('(pendente)');
      expect(item('Um símbolo (por exemplo ! @ # $ %)')).toHaveTextContent('(pendente)');
    });

    it('não libera com senha fraca ou com repetição diferente', async () => {
      await abrirPrimeiroAcesso();
      const botao = screen.getByRole('button', { name: M.entrar.aluno.primeiro.criarSenha });
      await digitarCodigo('123456');

      await userEvent.type(screen.getByLabelText(M.entrar.senha.criar), 'senhafraca');
      await userEvent.type(screen.getByLabelText(M.entrar.senha.repetir), 'senhafraca');
      expect(botao).toBeDisabled();

      await userEvent.clear(screen.getByLabelText(M.entrar.senha.criar));
      await userEvent.clear(screen.getByLabelText(M.entrar.senha.repetir));
      await userEvent.type(screen.getByLabelText(M.entrar.senha.criar), SENHA_FORTE);
      await userEvent.type(screen.getByLabelText(M.entrar.senha.repetir), 'Outra@5678');
      expect(botao).toBeDisabled();
      expect(screen.getByText(M.entrar.senha.diferentes)).toBeInTheDocument();
    });

    it('mostra o erro do servidor quando o código é inválido', async () => {
      mocks.params = new URLSearchParams({ perfil: 'aluno' });
      renderEntrar({
        definirSenhaAluno: vi
          .fn()
          .mockRejectedValue(erroApi(401, 'CODIGO_INVALIDO', 'Código inválido ou vencido.')),
      });
      await userEvent.click(
        await screen.findByRole('button', { name: M.entrar.aluno.primeiroAcesso }),
      );
      await userEvent.type(await screen.findByLabelText(M.entrar.aluno.email), 'a@b.com');
      await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.primeiro.enviarCodigo }));
      await digitarCodigo('000000');
      await userEvent.type(screen.getByLabelText(M.entrar.senha.criar), SENHA_FORTE);
      await userEvent.type(screen.getByLabelText(M.entrar.senha.repetir), SENHA_FORTE);
      await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.primeiro.criarSenha }));

      expect((await screen.findAllByRole('alert'))[0].textContent).toMatch(/código inválido/i);
      expect(mocks.replace).not.toHaveBeenCalled();
    });

    it('permite voltar para o login com senha', async () => {
      renderEntrar();
      await userEvent.click(
        await screen.findByRole('button', { name: M.entrar.aluno.primeiroAcesso }),
      );
      await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.jaTenhoSenha }));

      expect(screen.getByLabelText(M.entrar.aluno.senha)).toBeInTheDocument();
    });

    it('mostra o limite de envios quando o servidor responde 429', async () => {
      renderEntrar({
        solicitarCodigoPrimeiroAcesso: vi
          .fn()
          .mockRejectedValue(erroApi(429, 'AUTH_LIMITE_EXCEDIDO', 'Muitos pedidos de código.', 120)),
      });
      await userEvent.click(
        await screen.findByRole('button', { name: M.entrar.aluno.primeiroAcesso }),
      );
      await userEvent.type(await screen.findByLabelText(M.entrar.aluno.email), 'a@b.com');
      await userEvent.click(screen.getByRole('button', { name: M.entrar.aluno.primeiro.enviarCodigo }));

      expect((await screen.findByRole('alert')).textContent).toMatch(/muitos pedidos de código/i);
    });
  });
});

describe('EntrarView / demonstração e estados gerais', () => {
  it('oferece a demonstração do perfil selecionado', async () => {
    const { api } = renderEntrar();

    await userEvent.click(await screen.findByRole('button', { name: M.entrar.demo.empresa }));

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar'));
    expect(api.entrarDemo).toHaveBeenCalledWith('empresa');
  });

  it('esconde a demonstração quando o servidor não a habilita', async () => {
    renderEntrar({
      configAuth: vi.fn().mockResolvedValue({ auth_habilitada: true, demo_habilitado: false }),
    });

    await screen.findByLabelText(M.entrar.empresa.email);
    expect(screen.queryByText(M.entrar.demo.titulo)).not.toBeInTheDocument();
  });

  it('com login desligado, segue direto para a área do perfil', async () => {
    mocks.params = new URLSearchParams({ perfil: 'aluno' });
    renderEntrar({
      configAuth: vi.fn().mockResolvedValue({ auth_habilitada: false, demo_habilitado: false }),
    });

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/aluno'));
  });

  it('servidor sem a rota de login é tratado como login desligado', async () => {
    renderEntrar({
      configAuth: vi.fn().mockRejectedValue(erroApi(404, 'NAO_ENCONTRADO', 'Rota inexistente.')),
    });

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar'));
  });

  it('quem já tem sessão vê o aviso, continua ou troca de conta', async () => {
    const { api } = renderEntrar({ obterSessao: vi.fn().mockResolvedValue(empresa) });

    expect(await screen.findByText(M.entrar.jaLogado.comoEmpresa('empresa@demo.com'))).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: M.entrar.jaLogado.continuar }));
    expect(mocks.replace).toHaveBeenCalledWith('/empresa/gerar');

    await userEvent.click(screen.getByRole('button', { name: M.entrar.jaLogado.trocar }));
    await waitFor(() => expect(api.sair).toHaveBeenCalled());
    expect(await screen.findByLabelText(M.entrar.empresa.email)).toBeInTheDocument();
  });

  it('mostra erro com nova tentativa quando a configuração falha', async () => {
    const configAuth = vi
      .fn()
      .mockRejectedValueOnce(erroApi(500, 'INTERNO', 'Falha.'))
      .mockResolvedValueOnce(ligado);
    renderEntrar({ configAuth });

    await userEvent.click(await screen.findByRole('button', { name: M.entrar.tentarNovamente }));
    expect(await screen.findByLabelText(M.entrar.empresa.email)).toBeInTheDocument();
  });
});
