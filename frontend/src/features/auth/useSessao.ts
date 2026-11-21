'use client';

import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroApi } from '@/services/api/erros';
import { CHAVE_IDENTIDADE_ALUNO } from '@/features/aluno/useIdentidadeAluno';
import type {
  ConfigAuth,
  DefinirSenhaAlunoInput,
  LoginAlunoInput,
  LoginEmpresaInput,
  PerfilDemo,
  Sessao,
  SolicitarCodigoInput,
  VerificarCodigoInput,
} from '@/types/novamente';

export const CHAVE_SESSAO = ['sessao'] as const;
export const CHAVE_CONFIG_AUTH = ['auth-config'] as const;

/** Sem login ligado no servidor (ou servidor antigo sem a rota): telas abertas, como antes. */
export const CONFIG_AUTH_PADRAO: ConfigAuth = { auth_habilitada: false, demo_habilitado: false };

/** Configuração pública do login: se está ligado e se a demonstração está disponível. */
export function useConfigAuth() {
  const api = useApi();

  return useQuery({
    queryKey: CHAVE_CONFIG_AUTH,
    queryFn: async (): Promise<ConfigAuth> => {
      try {
        return await api.configAuth();
      } catch (erro) {
        // Servidor sem a rota de login: trata como login desligado.
        if (erro instanceof ErroApi && erro.status >= 400 && erro.status < 500) {
          return CONFIG_AUTH_PADRAO;
        }
        throw erro;
      }
    },
    staleTime: 5 * 60_000,
  });
}

/**
 * Sessão atual. `null` = ninguém logado (401). Só consulta quando o login está
 * ligado, para não gerar chamadas inúteis no modo aberto.
 */
export function useSessao(habilitado = true) {
  const api = useApi();

  return useQuery({
    queryKey: CHAVE_SESSAO,
    enabled: habilitado,
    queryFn: async (): Promise<Sessao | null> => {
      try {
        return await api.obterSessao();
      } catch (erro) {
        if (erro instanceof ErroApi && erro.status === 401) return null;
        throw erro;
      }
    },
    staleTime: 60_000,
    retry: false,
  });
}

/** Limpa o que pertence à pessoa que saiu: identidade do aluno e dados em cache. */
function limparDadosDaSessao(client: QueryClient) {
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.removeItem(CHAVE_IDENTIDADE_ALUNO);
      window.dispatchEvent(new StorageEvent('storage', { key: CHAVE_IDENTIDADE_ALUNO }));
    } catch {
      // Sem armazenamento disponível: nada a limpar.
    }
  }
  client.removeQueries({
    predicate: (consulta) => {
      const raiz = consulta.queryKey[0];
      return raiz !== CHAVE_SESSAO[0] && raiz !== CHAVE_CONFIG_AUTH[0];
    },
  });
}

/** Grava a sessão recém-aberta e descarta dados da sessão anterior. */
function useAbrirSessao() {
  const client = useQueryClient();
  return (sessao: Sessao) => {
    limparDadosDaSessao(client);
    client.setQueryData(CHAVE_SESSAO, sessao);
  };
}

// Etapa 1 (senha): se estiver certa, o servidor envia o código por e-mail.
export function useLoginEmpresa() {
  const api = useApi();
  return useMutation({ mutationFn: (input: LoginEmpresaInput) => api.loginEmpresa(input) });
}

export function useLoginAluno() {
  const api = useApi();
  return useMutation({ mutationFn: (input: LoginAlunoInput) => api.loginAluno(input) });
}

// Etapa 2 (código do e-mail): abre a sessão.
export function useVerificarEmpresa() {
  const api = useApi();
  const abrir = useAbrirSessao();
  return useMutation({
    mutationFn: (input: VerificarCodigoInput) => api.verificarEmpresa(input),
    onSuccess: abrir,
  });
}

export function useVerificarAluno() {
  const api = useApi();
  const abrir = useAbrirSessao();
  return useMutation({
    mutationFn: (input: VerificarCodigoInput) => api.verificarAluno(input),
    onSuccess: abrir,
  });
}

// Primeiro acesso / esqueci a senha do aluno.
export function useSolicitarCodigoPrimeiroAcesso() {
  const api = useApi();
  return useMutation({
    mutationFn: (input: SolicitarCodigoInput) => api.solicitarCodigoPrimeiroAcesso(input),
  });
}

export function useDefinirSenhaAluno() {
  const api = useApi();
  const abrir = useAbrirSessao();
  return useMutation({
    mutationFn: (input: DefinirSenhaAlunoInput) => api.definirSenhaAluno(input),
    onSuccess: abrir,
  });
}

export function useEntrarDemo() {
  const api = useApi();
  const client = useQueryClient();

  return useMutation({
    mutationFn: (perfil: PerfilDemo) => api.entrarDemo(perfil),
    onSuccess: (sessao) => {
      limparDadosDaSessao(client);
      client.setQueryData(CHAVE_SESSAO, sessao);
    },
  });
}

export function useSair() {
  const api = useApi();
  const client = useQueryClient();

  return useMutation({
    mutationFn: () => api.sair(),
    // Mesmo que a chamada falhe (rede), a tela local sai: o cookie expira sozinho.
    onSettled: () => {
      limparDadosDaSessao(client);
      client.setQueryData(CHAVE_SESSAO, null);
    },
  });
}

/** Destino padrão de cada perfil depois de entrar. */
export function destinoPadrao(tipo: Sessao['tipo']): string {
  return tipo === 'empresa' ? '/empresa/gerar' : '/aluno';
}

/**
 * Aceita só caminhos internos do próprio perfil (evita redirecionamento aberto
 * e levar um aluno para a área da empresa).
 */
export function destinoSeguro(proximo: string | null | undefined, tipo: Sessao['tipo']): string {
  if (!proximo || !proximo.startsWith('/') || proximo.startsWith('//') || proximo.includes('\\')) {
    return destinoPadrao(tipo);
  }
  const prefixo = tipo === 'empresa' ? '/empresa' : '/aluno';
  if (proximo === prefixo || proximo.startsWith(`${prefixo}/`) || proximo.startsWith(`${prefixo}?`)) {
    return proximo;
  }
  return destinoPadrao(tipo);
}

/** `true` só quando o servidor confirma que o login está ligado. */
export function useAuthAtiva(): boolean {
  const config = useConfigAuth();
  return config.data?.auth_habilitada === true;
}
