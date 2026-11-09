import { handlersAdaptacoes } from './adaptacoes';
import { handlersAlunos } from './alunos';
import { handlersJobs } from './jobs';
import { handlersMateriais } from './materiais';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [
  ...handlersAdaptacoes,
  ...handlersAlunos,
  ...handlersMateriais,
  ...handlersJobs,
  ...handlersOci,
  ...handlersHealth,
];
