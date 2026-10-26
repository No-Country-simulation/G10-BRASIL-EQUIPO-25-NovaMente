import { http, HttpResponse } from 'msw';

export const handlersOci = [
  http.get('*/api/v1/oci/status', () =>
    HttpResponse.json({
      configurado: true,
      bucket: 'novamente-conteudos-educativos',
      regiao: 'sa-saopaulo-1',
      total_objetos: 4,
      bytes_armazenados: 412_000,
      ultimo_upload_em: new Date().toISOString(),
      verificado_em: new Date().toISOString(),
    }),
  ),
];
