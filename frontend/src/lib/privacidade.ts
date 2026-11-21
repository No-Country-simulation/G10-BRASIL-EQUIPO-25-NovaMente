/**
 * Conteúdo da página /privacidade (Política de Privacidade e Cookies).
 *
 * Os dados abaixo descrevem o que o NovaMente realmente guarda. Se uma
 * funcionalidade passar a tratar um dado novo (ou um cookie novo for criado),
 * atualize esta lista, suba `VERSAO_POLITICA` e `VERSAO_CONSENTIMENTO`
 * (features/privacidade/armazenamento.ts) para que o aviso volte a aparecer.
 */

export const VERSAO_POLITICA = '1.0';
export const ATUALIZADA_EM = '21 de novembro de 2026';

/**
 * Canal do titular para pedidos da LGPD. Definido na implantação
 * (NEXT_PUBLIC_EMAIL_PRIVACIDADE, lido na hora do build); vazio, a página
 * indica o canal da equipe responsável pela instância.
 */
export const EMAIL_PRIVACIDADE = (process.env.NEXT_PUBLIC_EMAIL_PRIVACIDADE ?? '').trim();

export const REPOSITORIO = 'https://github.com/No-Country-simulation/G10-BRASIL-EQUIPO-25-NovaMente';

export interface ArmazenamentoNavegador {
  nome: string;
  tipo: string;
  categoria: 'Necessário' | 'Preferências';
  finalidade: string;
  duracao: string;
}

export const ARMAZENAMENTOS: ArmazenamentoNavegador[] = [
  {
    nome: 'nm_sessao',
    tipo: 'Cookie (HttpOnly, SameSite=Lax e Secure em HTTPS)',
    categoria: 'Necessário',
    finalidade:
      'Mantém você conectado depois do login. Guarda o perfil (empresa ou aluno), o identificador da conta (e-mail da empresa ou código do aluno), o nome do aluno e a validade, assinados contra adulteração. Nunca guarda a senha. Só existe quando o login está ligado.',
    duracao: 'Empresa: 8 horas. Aluno: 12 horas. Demonstração: 2 horas. Ou até você sair.',
  },
  {
    nome: 'novamente.consentimento',
    tipo: 'Armazenamento local',
    categoria: 'Necessário',
    finalidade:
      'Registra a sua escolha sobre cookies (aceitou ou recusou as preferências, com data e versão do texto), para o aviso não aparecer de novo.',
    duracao: 'Até você mudar a escolha ou esta política mudar.',
  },
  {
    nome: 'novamente.aluno',
    tipo: 'Armazenamento local',
    categoria: 'Necessário',
    finalidade:
      'Na área do aluno, guarda o código e o nome do aluno conectado para abrir o catálogo dele. Não é uma credencial: o acesso é validado pela sessão.',
    duracao: 'Até você sair da conta.',
  },
  {
    nome: 'novamente.skin',
    tipo: 'Armazenamento local (se permitido) ou da sessão',
    categoria: 'Preferências',
    finalidade: 'Lembra o tema que você escolheu: cor e modo claro ou escuro.',
    duracao:
      'Com a sua permissão, até você apagar ou revogar. Sem ela, só até fechar o navegador.',
  },
  {
    nome: 'novamente.tour e novamente.tour:<conta>',
    tipo: 'Armazenamento local (se permitido) ou da sessão',
    categoria: 'Preferências',
    finalidade:
      'Lembra que você já concluiu ou pulou o tour guiado, para ele não abrir sozinho de novo. Com login, o registro é separado por conta.',
    duracao:
      'Com a sua permissão, até você apagar ou revogar. Sem ela, só até fechar o navegador.',
  },
];

export interface DadoTratado {
  titular: string;
  dados: string;
  finalidade: string;
  base: string;
  retencao: string;
}

export const DADOS_TRATADOS: DadoTratado[] = [
  {
    titular: 'Conta da empresa',
    dados:
      'E-mail da conta e código de verificação de 6 dígitos, guardado apenas como hash e válido por 10 minutos. A senha é configurada pelo administrador e fica só como hash.',
    finalidade: 'Autenticar a empresa em duas etapas e proteger o acesso.',
    base: 'Execução do serviço solicitado (art. 7º, V) e legítimo interesse em segurança (art. 7º, IX).',
    retencao: 'Enquanto a conta existir. Os códigos são apagados depois de usados ou vencidos.',
  },
  {
    titular: 'Alunos',
    dados:
      'Nome, e-mail, situação do cadastro (ativo ou inativo), materiais vinculados e o hash da senha. A senha em si nunca é guardada.',
    finalidade:
      'Identificar o aluno, autenticá-lo em duas etapas e entregar só os materiais liberados para ele.',
    base: 'Execução do serviço (art. 7º, V) e legítimo interesse em segurança (art. 7º, IX). Quem cadastra o aluno é a empresa, que é a controladora desses dados.',
    retencao: 'Até a empresa excluir o cadastro do aluno.',
  },
  {
    titular: 'Documentos e materiais',
    dados:
      'Conteúdo dos documentos enviados (PDF, Markdown ou texto), materiais gerados (resumos, flashcards, quizzes e tutoriais) e seus dados de contexto: título, perfil, formato, nível, nicho e data.',
    finalidade: 'Gerar, guardar, publicar para os alunos e exportar os materiais.',
    base: 'Execução do serviço solicitado (art. 7º, V).',
    retencao:
      'Até a empresa excluir o material. A exclusão o remove da plataforma; cópias de segurança e arquivos no armazenamento em nuvem podem permanecer por um período até serem eliminados.',
  },
  {
    titular: 'Perguntas ao chat do material',
    dados: 'A pergunta, o histórico da conversa e trechos do material usados para responder.',
    finalidade: 'Responder perguntas ancoradas no conteúdo do material.',
    base: 'Execução do serviço solicitado (art. 7º, V).',
    retencao:
      'Usados só para gerar a resposta. O texto das perguntas não é gravado nos registros (logs) do servidor.',
  },
  {
    titular: 'Dados técnicos de acesso',
    dados: 'Endereço IP e dados da requisição, como data, hora e rota acessada.',
    finalidade:
      'Segurança e prevenção de abuso, como limitar tentativas de login e de envio de códigos.',
    base: 'Legítimo interesse em segurança (art. 7º, IX).',
    retencao:
      'Os contadores de limite ficam só na memória do servidor, por minutos. Registros do servidor podem ser mantidos pelo tempo mínimo necessário à segurança.',
  },
];

export interface Destinatario {
  nome: string;
  papel: string;
}

export const DESTINATARIOS: Destinatario[] = [
  {
    nome: 'Provedores de inteligência artificial (Google Gemini e NVIDIA)',
    papel:
      'Recebem trechos dos documentos e as perguntas do chat para gerar os materiais, os índices de busca e as respostas. Evite enviar dados pessoais ou sigilosos nos documentos.',
  },
  {
    nome: 'Oracle Cloud Infrastructure (OCI)',
    papel:
      'Hospeda a aplicação e guarda, no armazenamento de objetos, os documentos originais e os resultados gerados.',
  },
  {
    nome: 'Serviço de envio de e-mail',
    papel: 'Recebe o e-mail do destinatário e o código de 6 dígitos para entregar a mensagem de verificação.',
  },
];

export const DIREITOS: string[] = [
  'Confirmação de que tratamos dados seus.',
  'Acesso aos dados.',
  'Correção de dados incompletos, inexatos ou desatualizados.',
  'Anonimização, bloqueio ou eliminação de dados desnecessários, excessivos ou tratados em desconformidade com a lei.',
  'Portabilidade dos dados a outro fornecedor, conforme a regulamentação da ANPD.',
  'Eliminação dos dados tratados com o seu consentimento.',
  'Informação sobre as entidades com as quais compartilhamos dados.',
  'Informação sobre a possibilidade de não fornecer consentimento e sobre as consequências da recusa.',
  'Revogação do consentimento, a qualquer momento e de forma tão fácil quanto concedê-lo.',
  'Oposição a tratamento feito com base em hipótese diferente do consentimento, quando houver descumprimento da lei.',
];

export interface Referencia {
  titulo: string;
  url: string;
}

export const REFERENCIAS: Referencia[] = [
  {
    titulo: 'Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD)',
    url: 'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm',
  },
  {
    titulo: 'Lei nº 12.965/2014 — Marco Civil da Internet',
    url: 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l12965.htm',
  },
  {
    titulo: 'Autoridade Nacional de Proteção de Dados (ANPD), com o Guia Orientativo sobre Cookies e Proteção de Dados Pessoais',
    url: 'https://www.gov.br/anpd/pt-br',
  },
];
