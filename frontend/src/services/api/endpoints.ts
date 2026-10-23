const BASE = '/api/v1';

export const urls = {
  adaptacoes: `${BASE}/adaptacoes`,
  upload: `${BASE}/adaptacoes/upload`,
  job: (jobId: string) => `${BASE}/jobs/${encodeURIComponent(jobId)}`,
  adaptacao: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}`,
  download: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}/download`,
  exportacao: (id: string) => `${BASE}/adaptacoes/${encodeURIComponent(id)}/exportacao`,
  ociStatus: `${BASE}/oci/status`,
  health: `${BASE}/health`,
};

export function montarQuery(params: Record<string, string | number | undefined>): string {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === '') continue;
    busca.set(chave, String(valor));
  }
  const texto = busca.toString();
  return texto ? `?${texto}` : '';
}
