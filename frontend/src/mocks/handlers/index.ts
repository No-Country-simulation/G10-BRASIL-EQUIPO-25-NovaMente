import { handlersAdaptacoes } from './adaptacoes';
import { handlersAlunos } from './alunos';
import { handlersJobs } from './jobs';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [
  ...handlersAdaptacoes,
  ...handlersAlunos,
  ...handlersJobs,
  ...handlersOci,
  ...handlersHealth,
];
