import { handlersAdaptacoes } from './adaptacoes';
import { handlersAluno } from './aluno';
import { handlersAlunos } from './alunos';
import { handlersAuth } from './auth';
import { handlersChat } from './chat';
import { handlersJobs } from './jobs';
import { handlersMateriais } from './materiais';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [
  ...handlersAdaptacoes,
  ...handlersAluno,
  ...handlersAlunos,
  ...handlersAuth,
  ...handlersChat,
  ...handlersMateriais,
  ...handlersJobs,
  ...handlersOci,
  ...handlersHealth,
];
