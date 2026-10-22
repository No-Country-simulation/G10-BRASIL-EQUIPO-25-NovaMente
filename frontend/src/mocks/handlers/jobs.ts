import { http, HttpResponse } from 'msw';
import { cancelarJob, obterJob } from '../estadoJobs';

function jobNaoEncontrado() {
  return HttpResponse.json(
    { erro: { codigo: 'JOB_NAO_ENCONTRADO', mensagem: 'Geração não encontrada.' } },
    { status: 404 },
  );
}

export const handlersJobs = [
  http.get('*/api/v1/jobs/:id', ({ params }) => {
    const job = obterJob(String(params.id));
    if (!job) return jobNaoEncontrado();
    return HttpResponse.json(job);
  }),

  http.delete('*/api/v1/jobs/:id', ({ params }) => {
    const resultado = cancelarJob(String(params.id));
    if (!resultado) return jobNaoEncontrado();
    if (resultado === 'finalizado') {
      return HttpResponse.json(
        { erro: { codigo: 'JOB_FINALIZADO', mensagem: 'Esta geração já terminou.' } },
        { status: 409 },
      );
    }
    return HttpResponse.json(resultado);
  }),
];
