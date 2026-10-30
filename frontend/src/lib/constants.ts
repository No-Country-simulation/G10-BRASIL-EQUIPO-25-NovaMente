import type { EtapaJob, FormatoSaida, NivelDetalhe, PerfilDestinatario } from '@/types/novamente';

export const PERFIS: { valor: PerfilDestinatario; rotulo: string; descricao: string }[] = [
  { valor: 'Iniciante', rotulo: 'Iniciante / Transição de Carreira', descricao: 'Sem jargão, com analogias' },
  { valor: 'Desenvolvedor', rotulo: 'Desenvolvedor Júnior / Pleno', descricao: 'Precisão técnica e exemplos de código' },
  { valor: 'LiderTecnico', rotulo: 'Líder Técnico / Arquiteto', descricao: 'Decisões, trade-offs e padrões' },
  { valor: 'Gestor', rotulo: 'Gestor / Executivo (Não Técnico)', descricao: 'Impacto, custo e risco' },
];

export const FORMATOS: { valor: FormatoSaida; rotulo: string; descricao: string }[] = [
  { valor: 'Flashcards', rotulo: 'Flashcards', descricao: 'Memorização por repetição' },
  { valor: 'Quiz', rotulo: 'Quiz interativo', descricao: 'Perguntas com justificativa' },
  { valor: 'Tutorial', rotulo: 'Tutorial', descricao: 'Guia passo a passo' },
  { valor: 'ResumoExecutivo', rotulo: 'Resumo Executivo (TL;DR)', descricao: 'Essência em poucos minutos' },
];

export const NICHOS = [
  { valor: 'Fintech', rotulo: 'Fintech' },
  { valor: 'Saude', rotulo: 'Saúde' },
  { valor: 'Ecommerce', rotulo: 'E-commerce' },
  { valor: 'Geral', rotulo: 'Geral' },
] as const;

export const NIVEIS: { valor: NivelDetalhe; rotulo: string }[] = [
  { valor: 'Didatico', rotulo: 'Didático' },
  { valor: 'Tecnico', rotulo: 'Técnico' },
  { valor: 'Executivo', rotulo: 'Executivo' },
];

export const ETAPAS: EtapaJob[] = ['extraindo', 'chunking', 'embeddings', 'gerando', 'revisando', 'armazenando'];

export const ROTULOS_ETAPA: Record<EtapaJob, string> = {
  extraindo: 'Extraindo texto',
  chunking: 'Segmentando conteúdo',
  embeddings: 'Gerando embeddings',
  gerando: 'Redigindo material',
  revisando: 'Revisando fidelidade',
  armazenando: 'Salvando no OCI',
};

export const INTERVALO_POLL_MS = 1_500;
export const INTERVALO_POLL_LONGO_MS = 3_000;
export const LIMITE_TEMPO_JOB_MS = 5 * 60 * 1_000;
export const JANELA_POLL_RAPIDO_MS = 60_000;

export const CENARIOS = [
  {
    id: 'iniciante-flashcards',
    rotulo: 'Iniciante + Flashcards',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Iniciante',
    formato: 'Flashcards',
    nivel: 'Didatico',
  },
  {
    id: 'desenvolvedor-quiz',
    rotulo: 'Desenvolvedor + Quiz',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Desenvolvedor',
    formato: 'Quiz',
    nivel: 'Tecnico',
  },
  {
    id: 'gestor-resumo',
    rotulo: 'Gestor + Resumo Executivo',
    titulo: 'Introdução à Arquitetura de Redes VCN na OCI',
    perfil: 'Gestor',
    formato: 'ResumoExecutivo',
    nivel: 'Executivo',
  },
] as const;

export const DOCUMENTO_DEMO = `A Virtual Cloud Network (VCN) é uma rede privada e personalizável configurada na Oracle Cloud Infrastructure. Semelhante a uma rede de data center tradicional, a VCN oferece controle total sobre o ambiente de rede, incluindo sub-redes públicas e privadas, tabelas de roteamento, Internet Gateways, NAT Gateways e Security Lists para controle de tráfego via regras de entrada (ingress) e saída (egress). Cada sub-rede pode ser pública ou privada, e o roteamento decide para onde o tráfego segue.`;
