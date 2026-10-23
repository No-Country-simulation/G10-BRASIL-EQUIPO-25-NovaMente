import { handlersAdaptacoes } from './adaptacoes';
import { handlersJobs } from './jobs';
import { handlersOci } from './oci';
import { handlersHealth } from './health';

export const handlers = [...handlersAdaptacoes, ...handlersJobs, ...handlersOci, ...handlersHealth];
