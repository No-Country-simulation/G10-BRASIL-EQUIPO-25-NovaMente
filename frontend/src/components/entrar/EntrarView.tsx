'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { CampoSenha, CLASSE_CAMPO } from './CampoSenha';
import { Erro, PassoCodigo, useEsperaReenvio } from './PassoCodigo';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Logo } from '@/components/layout/Logo';
import { SkinSwitcher } from '@/components/layout/SkinSwitcher';
import {
  destinoSeguro,
  useConfigAuth,
  useDefinirSenhaAluno,
  useEntrarDemo,
  useLoginAluno,
  useLoginEmpresa,
  useSair,
  useSessao,
  useSolicitarCodigoPrimeiroAcesso,
  useVerificarAluno,
  useVerificarEmpresa,
} from '@/features/auth/useSessao';
import { mensagemComEspera } from '@/services/api/erros';
import { M } from '@/lib/mensagens';
import { senhaValida } from '@/lib/senha';
import { ROTAS } from '@/lib/rotas';
import type { PerfilDemo, Sessao } from '@/types/novamente';

function perfilDaUrl(valor: string | null): PerfilDemo {
  return valor === 'aluno' ? 'aluno' : 'empresa';
}

/** Tela única de acesso: empresa (e-mail e senha), aluno (código por e-mail) e demonstração. */
export function EntrarView() {
  const router = useRouter();
  const parametros = useSearchParams();
  const proximo = parametros.get('proximo');
  const config = useConfigAuth();
  const autenticacaoLigada = config.data?.auth_habilitada === true;
  const sessao = useSessao(autenticacaoLigada);
  const [perfil, setPerfil] = useState<PerfilDemo>(perfilDaUrl(parametros.get('perfil')));

  // Login desligado no servidor: não há o que preencher, segue direto para a área.
  const aberto = config.data !== undefined && !autenticacaoLigada;
  useEffect(() => {
    if (aberto) router.replace(perfil === 'empresa' ? ROTAS.empresaGerar : ROTAS.aluno);
  }, [aberto, perfil, router]);

  function concluir(entrou: Sessao) {
    router.replace(destinoSeguro(proximo, entrou.tipo));
  }

  let conteudo: React.ReactNode;
  if (config.isLoading || aberto || (autenticacaoLigada && sessao.isLoading)) {
    conteudo = (
      <div className="space-y-3" aria-busy="true" aria-label={M.entrar.carregando}>
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  } else if (config.error) {
    conteudo = (
      <div role="alert" className="space-y-3 text-center">
        <p className="text-sm text-[var(--danger)]">{M.entrar.erroConfig}</p>
        <Button variant="outline" onClick={() => config.refetch()}>
          {M.entrar.tentarNovamente}
        </Button>
      </div>
    );
  } else if (sessao.data) {
    conteudo = <JaLogado sessao={sessao.data} proximo={proximo} />;
  } else {
    conteudo = (
      <>
        <header className="space-y-1">
          <h1 className="text-2xl font-semibold">{M.entrar.titulo}</h1>
          <p className="text-sm text-[var(--fg-muted)]">{M.entrar.subtitulo}</p>
        </header>

        <Tabs value={perfil} onValueChange={(valor) => setPerfil(perfilDaUrl(valor))} className="gap-4">
          <TabsList aria-label={M.entrar.abas} className="h-11 w-full">
            <TabsTrigger value="empresa" className="h-9 text-[var(--fg)]">
              {M.entrar.abaEmpresa}
            </TabsTrigger>
            <TabsTrigger value="aluno" className="h-9 text-[var(--fg)]">
              {M.entrar.abaAluno}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="empresa">
            <FormLogin perfil="empresa" onEntrou={concluir} />
          </TabsContent>
          <TabsContent value="aluno">
            <AcessoAluno onEntrou={concluir} />
          </TabsContent>
        </Tabs>

        {config.data?.demo_habilitado && <Demonstracao perfil={perfil} onEntrou={concluir} />}
      </>
    );
  }

  return (
    <div className="min-h-dvh bg-[var(--bg-pagina)] text-[var(--fg)]">
      <header className="border-b border-[var(--border)] bg-[var(--bg)]">
        <div className="mx-auto flex min-h-16 w-full max-w-[1120px] items-center justify-between gap-2 px-4 py-2 sm:px-6">
          <Logo />
          <div className="flex items-center gap-2">
            <SkinSwitcher />
            <Link
              href={ROTAS.landing}
              className="inline-flex h-11 items-center gap-1.5 text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
            >
              <ArrowLeft aria-hidden className="h-4 w-4" />
              {M.entrar.voltarInicio}
            </Link>
          </div>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-md space-y-6 px-4 py-10">
        {conteudo}
      </main>
    </div>
  );
}

function JaLogado({ sessao, proximo }: { sessao: Sessao; proximo: string | null }) {
  const router = useRouter();
  const sair = useSair();
  const descricao =
    sessao.tipo === 'empresa' ? M.entrar.jaLogado.comoEmpresa(sessao.email) : M.entrar.jaLogado.comoAluno(sessao.nome);

  return (
    <section className="space-y-4 rounded-xl border bg-[var(--surface)] p-6">
      <h1 className="text-xl font-semibold">{M.entrar.jaLogado.titulo}</h1>
      <p className="text-sm text-[var(--fg-muted)]">{descricao}</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button className="h-11 flex-1" onClick={() => router.replace(destinoSeguro(proximo, sessao.tipo))}>
          {M.entrar.jaLogado.continuar}
        </Button>
        <Button variant="outline" className="h-11 flex-1" disabled={sair.isPending} onClick={() => sair.mutate()}>
          {sair.isPending ? M.app.saindo : M.entrar.jaLogado.trocar}
        </Button>
      </div>
    </section>
  );
}

function CampoEmail({
  id,
  rotulo,
  valor,
  onChange,
}: {
  id: string;
  rotulo: string;
  valor: string;
  onChange: (valor: string) => void;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {rotulo}
      </label>
      <input
        id={id}
        type="email"
        autoComplete="username"
        required
        value={valor}
        onChange={(evento) => onChange(evento.target.value)}
        aria-describedby={`${id}-ajuda`}
        className={CLASSE_CAMPO}
      />
      <p id={`${id}-ajuda`} className="text-xs text-[var(--fg-muted)]">
        {M.entrar.email.dica}
      </p>
    </div>
  );
}

/**
 * Login em duas etapas, igual para empresa e aluno: 1) e-mail e senha;
 * 2) código de 6 dígitos enviado por e-mail.
 */
function FormLogin({
  perfil,
  onEntrou,
  onPrimeiroAcesso,
}: {
  perfil: 'empresa' | 'aluno';
  onEntrou: (sessao: Sessao) => void;
  onPrimeiroAcesso?: () => void;
}) {
  const textos = perfil === 'empresa' ? M.entrar.empresa : M.entrar.aluno;
  const loginEmpresa = useLoginEmpresa();
  const loginAluno = useLoginAluno();
  const verificarEmpresa = useVerificarEmpresa();
  const verificarAluno = useVerificarAluno();
  const login = perfil === 'empresa' ? loginEmpresa : loginAluno;
  const verificar = perfil === 'empresa' ? verificarEmpresa : verificarAluno;

  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [etapaCodigo, setEtapaCodigo] = useState(false);
  const { espera, iniciar, zerar } = useEsperaReenvio();

  function enviarSenha() {
    login.mutate(
      { email, senha },
      {
        onSuccess: () => {
          setEtapaCodigo(true);
          iniciar();
          verificar.reset();
        },
      },
    );
  }

  if (etapaCodigo) {
    return (
      <PassoCodigo
        email={email.trim().toLowerCase()}
        rotuloEnviar={textos.verificar}
        rotuloEnviando={textos.verificando}
        pendente={verificar.isPending}
        erro={
          verificar.error ? mensagemComEspera(verificar.error) : login.error ? mensagemComEspera(login.error) : null
        }
        espera={espera}
        reenviando={login.isPending}
        onEnviar={(codigo) => verificar.mutate({ email, codigo }, { onSuccess: onEntrou })}
        onReenviar={enviarSenha}
        onVoltar={() => {
          setEtapaCodigo(false);
          setSenha('');
          zerar();
          login.reset();
          verificar.reset();
        }}
      />
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(evento) => {
        evento.preventDefault();
        enviarSenha();
      }}
    >
      <p className="text-sm text-[var(--fg-muted)]">{textos.descricao}</p>
      <CampoEmail id={`${perfil}-email`} rotulo={textos.email} valor={email} onChange={setEmail} />
      <CampoSenha
        id={`${perfil}-senha`}
        rotulo={textos.senha}
        valor={senha}
        onChange={setSenha}
        autoComplete="current-password"
      />
      <Erro mensagem={login.error ? mensagemComEspera(login.error) : null} />
      <Button type="submit" className="h-11 w-full" disabled={login.isPending}>
        {login.isPending ? textos.enviando : textos.continuar}
      </Button>
      {onPrimeiroAcesso && (
        <button
          type="button"
          onClick={onPrimeiroAcesso}
          className="inline-flex h-11 w-full items-center justify-center text-sm text-[var(--accent)] hover:underline"
        >
          {M.entrar.aluno.primeiroAcesso}
        </button>
      )}
    </form>
  );
}

/** Primeiro acesso ou "esqueci a senha": confirma o e-mail por código e cria a senha. */
function FormPrimeiroAcesso({
  onEntrou,
  onVoltar,
}: {
  onEntrou: (sessao: Sessao) => void;
  onVoltar: () => void;
}) {
  const solicitar = useSolicitarCodigoPrimeiroAcesso();
  const definir = useDefinirSenhaAluno();
  const [email, setEmail] = useState('');
  const [enviadoPara, setEnviadoPara] = useState<string | null>(null);
  const [senha, setSenha] = useState('');
  const [repeticao, setRepeticao] = useState('');
  const { espera, iniciar, zerar } = useEsperaReenvio();

  function pedirCodigo(destino: string) {
    solicitar.mutate(
      { email: destino },
      {
        onSuccess: () => {
          setEnviadoPara(destino.trim().toLowerCase());
          iniciar();
          definir.reset();
        },
      },
    );
  }

  const iguais = senha === repeticao;

  if (enviadoPara === null) {
    return (
      <form
        className="space-y-4"
        onSubmit={(evento) => {
          evento.preventDefault();
          pedirCodigo(email);
        }}
      >
        <div className="space-y-1">
          <h2 className="text-base font-semibold">{M.entrar.aluno.primeiro.titulo}</h2>
          <p className="text-sm text-[var(--fg-muted)]">{M.entrar.aluno.primeiro.descricao}</p>
        </div>
        <CampoEmail id="primeiro-email" rotulo={M.entrar.aluno.email} valor={email} onChange={setEmail} />
        <Erro mensagem={solicitar.error ? mensagemComEspera(solicitar.error) : null} />
        <Button type="submit" className="h-11 w-full" disabled={solicitar.isPending}>
          {solicitar.isPending ? M.entrar.aluno.primeiro.enviando : M.entrar.aluno.primeiro.enviarCodigo}
        </Button>
        <button
          type="button"
          onClick={onVoltar}
          className="inline-flex h-11 w-full items-center justify-center text-sm text-[var(--fg-muted)] hover:text-[var(--fg)]"
        >
          {M.entrar.aluno.jaTenhoSenha}
        </button>
      </form>
    );
  }

  return (
    <PassoCodigo
      email={enviadoPara}
      rotuloEnviar={M.entrar.aluno.primeiro.criarSenha}
      rotuloEnviando={M.entrar.aluno.primeiro.criando}
      pendente={definir.isPending}
      erro={
        definir.error ? mensagemComEspera(definir.error) : solicitar.error ? mensagemComEspera(solicitar.error) : null
      }
      espera={espera}
      reenviando={solicitar.isPending}
      extraValido={senhaValida(senha) && iguais}
      onEnviar={(codigo) =>
        definir.mutate({ email: enviadoPara, codigo, senha }, { onSuccess: onEntrou })
      }
      onReenviar={() => pedirCodigo(enviadoPara)}
      onVoltar={() => {
        setEnviadoPara(null);
        setSenha('');
        setRepeticao('');
        zerar();
        definir.reset();
        solicitar.reset();
      }}
    >
      <CampoSenha
        id="senha-nova"
        rotulo={M.entrar.senha.criar}
        valor={senha}
        onChange={setSenha}
        autoComplete="new-password"
        criacao
      />
      <CampoSenha
        id="senha-repeticao"
        rotulo={M.entrar.senha.repetir}
        valor={repeticao}
        onChange={setRepeticao}
        autoComplete="new-password"
        invalido={repeticao.length > 0 && !iguais}
        erro={repeticao.length > 0 && !iguais ? M.entrar.senha.diferentes : null}
      />
    </PassoCodigo>
  );
}

function AcessoAluno({ onEntrou }: { onEntrou: (sessao: Sessao) => void }) {
  const [primeiroAcesso, setPrimeiroAcesso] = useState(false);

  if (primeiroAcesso) {
    return <FormPrimeiroAcesso onEntrou={onEntrou} onVoltar={() => setPrimeiroAcesso(false)} />;
  }
  return (
    <FormLogin perfil="aluno" onEntrou={onEntrou} onPrimeiroAcesso={() => setPrimeiroAcesso(true)} />
  );
}

function Demonstracao({ perfil, onEntrou }: { perfil: PerfilDemo; onEntrou: (sessao: Sessao) => void }) {
  const demo = useEntrarDemo();

  return (
    <section className="space-y-3 border-t border-[var(--border)] pt-6">
      <div className="space-y-1">
        <h2 className="text-base font-semibold">{M.entrar.demo.titulo}</h2>
        <p className="text-sm text-[var(--fg-muted)]">{M.entrar.demo.descricao}</p>
      </div>
      <Erro mensagem={demo.error ? mensagemComEspera(demo.error) : null} />
      <Button
        variant="outline"
        className="h-11 w-full"
        disabled={demo.isPending}
        onClick={() => demo.mutate(perfil, { onSuccess: onEntrou })}
      >
        {demo.isPending ? M.entrar.demo.entrando : perfil === 'empresa' ? M.entrar.demo.empresa : M.entrar.demo.aluno}
      </Button>
    </section>
  );
}
