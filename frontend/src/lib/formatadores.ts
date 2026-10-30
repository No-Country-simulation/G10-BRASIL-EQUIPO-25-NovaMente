import type { AdaptacaoPacote, FormatoExportacao, PerfilDestinatario, FormatoSaida } from '@/types/novamente';

const SLUG_PERFIL: Record<PerfilDestinatario, string> = {
  Iniciante: 'iniciante',
  Desenvolvedor: 'desenvolvedor',
  LiderTecnico: 'lider-tecnico',
  Gestor: 'gestor',
};

const SLUG_FORMATO: Record<FormatoSaida, string> = {
  Flashcards: 'flashcards',
  Quiz: 'quiz',
  Tutorial: 'tutorial',
  ResumoExecutivo: 'resumo-executivo',
};

export function slugify(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
    .replace(/-+$/g, '');
}

export function formatarBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(bytes / (1024 * 1024))} MB`;
}

export function formatarPercentual(valor: number): string {
  return new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 }).format(valor);
}

export function faixaAncoragem(valor: number): 'alta' | 'media' | 'baixa' {
  if (valor >= 0.9) return 'alta';
  if (valor >= 0.7) return 'media';
  return 'baixa';
}

export function formatarDataRelativa(iso: string, agora = Date.now()): string {
  const diferenca = new Date(iso).getTime() - agora;
  const minutos = Math.round(diferenca / 60_000);
  const formato = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });
  if (Math.abs(minutos) < 60) return formato.format(minutos, 'minute');
  const horas = Math.round(minutos / 60);
  if (Math.abs(horas) < 24) return formato.format(horas, 'hour');
  return formato.format(Math.round(horas / 24), 'day');
}

function baseNome(pacote: AdaptacaoPacote): string {
  const id8 = pacote.adaptacao_id.slice(0, 8).toLowerCase();
  return `novamente-${slugify(pacote.documento.titulo)}-${SLUG_PERFIL[pacote.metadados.perfil_aplicado]}-${SLUG_FORMATO[pacote.metadados.formato_gerado]}-${id8}`;
}

export function nomeArquivoPacote(pacote: AdaptacaoPacote): string {
  return `${baseNome(pacote)}.json`;
}

export function nomeArquivoExportacao(pacote: AdaptacaoPacote, formato: FormatoExportacao): string {
  return `${baseNome(pacote)}.${formato}`;
}
