import { http, HttpResponse } from 'msw';

export const handlersHealth = [
  http.get('*/api/v1/health', () =>
    HttpResponse.json({
      status: 'ok',
      versao: '0.1.0-mock',
      oci: 'ok',
      llm: 'ok',
      banco: 'ok',
      verificado_em: new Date().toISOString(),
    }),
  ),
];
