import { handlersAdaptacoes } from './adaptacoes';
import { handlersAluno } from './aluno';
import { handlersAlunos } from './alunos';
import { handlersJobs } from './jobs';
import { handlersMateriais } from './materiais';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [
  ...handlersAdaptacoes,
  ...handlersAluno,
  ...handlersAlunos,
  ...handlersMateriais,
  ...handlersJobs,
  ...handlersOci,
  ...handlersHealth,
];
