import Link from 'next/link';
import { Logo } from '@/components/layout/Logo';
import { SkinSwitcher } from '@/components/layout/SkinSwitcher';
import {
  ARMAZENAMENTOS,
  ATUALIZADA_EM,
  DADOS_TRATADOS,
  DESTINATARIOS,
  DIREITOS,
  EMAIL_PRIVACIDADE,
  REFERENCIAS,
  REPOSITORIO,
  VERSAO_POLITICA,
} from '@/lib/privacidade';
import { M } from '@/lib/mensagens';
import { ROTAS } from '@/lib/rotas';
import { BotaoPreferenciasCookies } from './BotaoPreferenciasCookies';

const SECOES = [
  { id: 'resumo', titulo: 'Resumo' },
  { id: 'responsavel', titulo: 'Quem é o responsável' },
  { id: 'dados', titulo: 'Quais dados tratamos e por quê' },
  { id: 'cookies', titulo: 'Cookies e armazenamento no navegador' },
  { id: 'compartilhamento', titulo: 'Com quem compartilhamos' },
  { id: 'retencao', titulo: 'Por quanto tempo guardamos' },
  { id: 'seguranca', titulo: 'Como protegemos os dados' },
  { id: 'direitos', titulo: 'Seus direitos' },
  { id: 'criancas', titulo: 'Crianças e adolescentes' },
  { id: 'alteracoes', titulo: 'Alterações desta política' },
  { id: 'contato', titulo: 'Contato e reclamações' },
  { id: 'legislacao', titulo: 'Legislação de referência' },
] as const;

const RESUMO = [
  'Coletamos só o necessário para você entrar, gerar materiais e estudar com eles.',
  'Não usamos cookies de publicidade, de análise ou de rastreamento, e não vendemos dados.',
  'Senhas são guardadas só como hash, e os códigos de verificação, também como hash, valem 10 minutos.',
  'Documentos e perguntas do chat são enviados a provedores de IA para gerar o conteúdo. Evite dados pessoais ou sigilosos neles.',
  'Os cookies de preferências só são guardados com a sua permissão, e você muda de ideia quando quiser.',
  'Você tem os direitos do art. 18 da LGPD e pode exercê-los pelo canal de contato desta página.',
];

const CLASSE_LINK =
  'font-medium text-[var(--fg)] underline underline-offset-4 hover:text-[var(--accent-hover)]';

function Secao({
  id,
  titulo,
  children,
}: {
  id: (typeof SECOES)[number]['id'];
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-24 space-y-4">
      <h2 id={`${id}-titulo`} className="text-xl font-semibold tracking-tight">
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Paragrafo({ children }: { children: React.ReactNode }) {
  return <p className="leading-relaxed text-[var(--fg-muted)]">{children}</p>;
}

function Cartao({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      {children}
    </div>
  );
}

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">
        {rotulo}
      </dt>
      <dd className="mt-1 text-sm leading-relaxed">{children}</dd>
    </div>
  );
}

export function PoliticaPrivacidade() {
  return (
    <div className="min-h-dvh bg-[var(--bg-pagina)] text-[var(--fg)]">
      <a
        href="#conteudo"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--accent-fg)]"
      >
        {M.comum.irParaConteudo}
      </a>
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg)]/90 backdrop-blur">
        <div className="mx-auto flex min-h-16 w-full max-w-[1120px] flex-wrap items-center justify-between gap-2 px-4 py-2 sm:px-6">
          <Logo />
          <div className="flex items-center gap-3">
            <SkinSwitcher />
            <Link
              href={ROTAS.landing}
              className="inline-flex h-11 items-center px-1 text-sm text-[var(--fg-muted)] underline underline-offset-4 hover:text-[var(--fg)]"
            >
              {M.privacidade.pagina.voltar}
            </Link>
          </div>
        </div>
      </header>

      <main id="conteudo" className="mx-auto w-full max-w-[860px] px-4 py-10 sm:px-6 sm:py-14">
        <article className="space-y-12">
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Política de Privacidade e Cookies
            </h1>
            <p className="text-sm text-[var(--fg-muted)]">
              Versão {VERSAO_POLITICA} · Atualizada em {ATUALIZADA_EM}
            </p>
            <Paragrafo>
              Este documento explica, de forma simples, como o NovaMente trata dados pessoais e
              usa cookies, de acordo com a Lei Geral de Proteção de Dados Pessoais (LGPD, Lei nº
              13.709/2018). Se algo não ficar claro, fale com a gente pelo canal indicado no fim.
            </Paragrafo>
          </div>

          <nav
            aria-label={M.privacidade.pagina.sumario}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
          >
            <p className="text-sm font-semibold">{M.privacidade.pagina.sumario}</p>
            <ol className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
              {SECOES.map((secao, indice) => (
                <li key={secao.id}>
                  <a
                    href={`#${secao.id}`}
                    className="inline-flex min-h-8 items-center text-[var(--fg-muted)] underline-offset-4 hover:text-[var(--fg)] hover:underline"
                  >
                    {indice + 1}. {secao.titulo}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <Secao id="resumo" titulo="1. Resumo">
            <ul className="list-disc space-y-2 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-muted)]">
              {RESUMO.map((item) => (
                <li key={item} className="leading-relaxed">
                  {item}
                </li>
              ))}
            </ul>
          </Secao>

          <Secao id="responsavel" titulo="2. Quem é o responsável">
            <Paragrafo>
              O NovaMente é um projeto da equipe G10 BRASIL EQUIPO 25, desenvolvido no Hackathon
              ONE (Oracle Next Education e Alura, com a No Country). Para a LGPD, o controlador dos
              dados tratados nesta instância é a equipe responsável pela sua operação.
            </Paragrafo>
            <Paragrafo>
              Quando uma empresa cadastra alunos, é ela quem decide para que esses dados servem e,
              por isso, é a controladora dos dados dos seus alunos. Nesse caso, o NovaMente atua
              como operador e trata os dados em nome da empresa.
            </Paragrafo>
          </Secao>

          <Secao id="dados" titulo="3. Quais dados tratamos e por quê">
            <Paragrafo>
              Só tratamos os dados que a plataforma precisa para funcionar. Cada item tem uma
              finalidade e uma base legal da LGPD (art. 7º).
            </Paragrafo>
            <div className="grid gap-4">
              {DADOS_TRATADOS.map((item) => (
                <Cartao key={item.titular}>
                  <h3 className="text-base font-semibold">{item.titular}</h3>
                  <dl className="mt-3 grid gap-3">
                    <Campo rotulo="Dados">{item.dados}</Campo>
                    <Campo rotulo="Finalidade">{item.finalidade}</Campo>
                    <Campo rotulo="Base legal">{item.base}</Campo>
                    <Campo rotulo="Por quanto tempo">{item.retencao}</Campo>
                  </dl>
                </Cartao>
              ))}
            </div>
            <Paragrafo>
              Não pedimos dados sensíveis (art. 5º, II) e não tomamos decisões automatizadas sobre
              você. A inteligência artificial só gera materiais a partir dos documentos que a
              empresa envia.
            </Paragrafo>
          </Secao>

          <Secao id="cookies" titulo="4. Cookies e armazenamento no navegador">
            <Paragrafo>
              Cookies e itens de armazenamento local são pequenos arquivos que o site guarda no seu
              navegador. Usamos duas categorias:
            </Paragrafo>
            <ul className="list-disc space-y-2 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-muted)]">
              <li className="leading-relaxed">
                <strong className="text-[var(--fg)]">Necessários:</strong> mantêm o login, protegem
                o acesso e registram a sua escolha. Sem eles a plataforma não funciona, por isso
                não dependem de consentimento.
              </li>
              <li className="leading-relaxed">
                <strong className="text-[var(--fg)]">Preferências:</strong> lembram o tema e se
                você já viu o tour guiado. Só são guardados entre visitas se você permitir (art.
                7º, I). Sem a permissão, valem apenas até você fechar o navegador.
              </li>
            </ul>
            <div className="grid gap-4">
              {ARMAZENAMENTOS.map((item) => (
                <Cartao key={item.nome}>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-mono text-sm font-semibold break-all">{item.nome}</h3>
                    <span className="rounded-full border border-[var(--border-strong)] px-2.5 py-0.5 text-xs font-medium">
                      {item.categoria}
                    </span>
                  </div>
                  <dl className="mt-3 grid gap-3">
                    <Campo rotulo="Tipo">{item.tipo}</Campo>
                    <Campo rotulo="Para que serve">{item.finalidade}</Campo>
                    <Campo rotulo="Duração">{item.duracao}</Campo>
                  </dl>
                </Cartao>
              ))}
            </div>
            <Paragrafo>
              <strong className="text-[var(--fg)]">O que não usamos:</strong> cookies de
              publicidade, de análise de audiência, de redes sociais ou de rastreamento entre
              sites. As fontes de texto são servidas pelo próprio site, sem chamadas a terceiros.
            </Paragrafo>
            <Paragrafo>
              <strong className="text-[var(--fg)]">Como mudar a sua escolha:</strong> use o botão
              abaixo, ou &quot;{M.privacidade.rodape.preferencias}&quot; no rodapé de qualquer tela.
              Ao recusar, apagamos as preferências que estavam guardadas no navegador. Você também
              pode apagar os dados do site nas configurações do navegador.
            </Paragrafo>
            <BotaoPreferenciasCookies className="min-h-11 rounded-lg border border-[var(--border-strong)] bg-[var(--surface)] px-4 text-sm font-medium no-underline hover:bg-[var(--surface-elevated)]" />
          </Secao>

          <Secao id="compartilhamento" titulo="5. Com quem compartilhamos">
            <Paragrafo>
              Não vendemos nem cedemos dados para publicidade. Compartilhamos o mínimo necessário
              com quem ajuda a operar o serviço:
            </Paragrafo>
            <div className="grid gap-4">
              {DESTINATARIOS.map((item) => (
                <Cartao key={item.nome}>
                  <h3 className="text-base font-semibold">{item.nome}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-[var(--fg-muted)]">{item.papel}</p>
                </Cartao>
              ))}
            </div>
            <Paragrafo>
              Alguns desses fornecedores podem tratar dados em servidores fora do Brasil. Nesses
              casos, a transferência internacional segue o art. 33 da LGPD, com as garantias
              previstas na lei.
            </Paragrafo>
          </Secao>

          <Secao id="retencao" titulo="6. Por quanto tempo guardamos">
            <ul className="list-disc space-y-2 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-muted)]">
              <li className="leading-relaxed">Códigos de verificação: valem 10 minutos e são apagados depois de usados ou vencidos.</li>
              <li className="leading-relaxed">Sessão de login: até vencer (2, 8 ou 12 horas, conforme o perfil) ou até você sair.</li>
              <li className="leading-relaxed">Cadastro de alunos, documentos e materiais: até a empresa excluí-los.</li>
              <li className="leading-relaxed">Cópias de segurança: podem conservar dados por um período adicional, até serem substituídas.</li>
              <li className="leading-relaxed">Dados técnicos de acesso: pelo tempo mínimo necessário à segurança.</li>
            </ul>
          </Secao>

          <Secao id="seguranca" titulo="7. Como protegemos os dados">
            <ul className="list-disc space-y-2 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-muted)]">
              <li className="leading-relaxed">Senhas protegidas com função de hash lenta (scrypt) e salt individual. Nem a equipe vê a sua senha.</li>
              <li className="leading-relaxed">Login em duas etapas: senha e código enviado ao seu e-mail, com limite de tentativas.</li>
              <li className="leading-relaxed">Cookie de sessão HttpOnly, SameSite e assinado; Secure na instância publicada, que usa HTTPS.</li>
              <li className="leading-relaxed">Acesso separado por perfil: o aluno só vê os materiais liberados para ele.</li>
              <li className="leading-relaxed">Respostas de login que não revelam se um e-mail está ou não cadastrado.</li>
            </ul>
            <Paragrafo>
              Nenhum sistema é totalmente imune a falhas. Se houver um incidente de segurança que
              possa trazer risco ou dano relevante, comunicaremos a ANPD e as pessoas afetadas, como
              pede o art. 48 da LGPD.
            </Paragrafo>
          </Secao>

          <Secao id="direitos" titulo="8. Seus direitos">
            <Paragrafo>
              A LGPD (art. 18) garante a você, como titular dos dados, o direito de pedir:
            </Paragrafo>
            <ul className="list-disc space-y-2 pl-5 text-[var(--fg-muted)] marker:text-[var(--fg-muted)]">
              {DIREITOS.map((direito) => (
                <li key={direito} className="leading-relaxed">
                  {direito}
                </li>
              ))}
            </ul>
            <Paragrafo>
              Os pedidos são gratuitos. Confirmação e acesso são respondidos de imediato, em
              formato simplificado, ou em até 15 dias, por declaração completa (art. 19). Para
              dados de alunos cadastrados por uma empresa, o pedido também pode ser feito à própria
              empresa.
            </Paragrafo>
          </Secao>

          <Secao id="criancas" titulo="9. Crianças e adolescentes">
            <Paragrafo>
              O NovaMente é voltado ao uso profissional e educacional e não é direcionado a menores
              de 18 anos. Quem cadastrar alunos menores de idade deve garantir a base legal e o
              consentimento de um responsável, como exige o art. 14 da LGPD.
            </Paragrafo>
          </Secao>

          <Secao id="alteracoes" titulo="10. Alterações desta política">
            <Paragrafo>
              Quando algo relevante mudar, atualizamos a versão e a data no topo desta página e
              pedimos novamente a sua escolha sobre cookies.
            </Paragrafo>
          </Secao>

          <Secao id="contato" titulo="11. Contato e reclamações">
            {EMAIL_PRIVACIDADE ? (
              <Paragrafo>
                Para exercer os seus direitos ou tirar dúvidas sobre privacidade, escreva para{' '}
                <a href={`mailto:${EMAIL_PRIVACIDADE}`} className={CLASSE_LINK}>
                  {EMAIL_PRIVACIDADE}
                </a>
                .
              </Paragrafo>
            ) : (
              <Paragrafo>
                Para exercer os seus direitos ou tirar dúvidas sobre privacidade, use o canal de
                contato informado pela equipe responsável por esta instância. Informações sobre o
                projeto estão no{' '}
                <a href={REPOSITORIO} target="_blank" rel="noopener noreferrer" className={CLASSE_LINK}>
                  repositório do NovaMente
                </a>
                .
              </Paragrafo>
            )}
            <Paragrafo>
              Se achar que o tratamento dos seus dados não respeita a lei, você também pode
              reclamar à Autoridade Nacional de Proteção de Dados (ANPD).
            </Paragrafo>
          </Secao>

          <Secao id="legislacao" titulo="12. Legislação de referência">
            <ul className="space-y-2">
              {REFERENCIAS.map((referencia) => (
                <li key={referencia.url}>
                  <a
                    href={referencia.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={CLASSE_LINK}
                  >
                    {referencia.titulo}
                  </a>
                </li>
              ))}
            </ul>
          </Secao>
        </article>
      </main>

      <footer className="mx-auto w-full max-w-[860px] border-t border-[var(--border)] px-4 py-6 sm:px-6">
        <p className="text-xs text-[var(--fg-muted)]">{M.landing.footer.creditos}</p>
      </footer>
    </div>
  );
}
