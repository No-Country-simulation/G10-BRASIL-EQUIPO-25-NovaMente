'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { ErroContrato } from '@/services/api/erros';
import { OciStatusSchema } from '@/types/schemas';

function descreverIssues(issues: readonly { path: PropertyKey[]; message: string }[]): string {
  return issues.map((issue) => `${issue.path.map(String).join('.') || '(raiz)'}: ${issue.message}`).join('; ');
}

export function useOciStatus() {
  const api = useApi();
  return useQuery({
    queryKey: ['oci-status'],
    queryFn: async () => {
      const analisado = OciStatusSchema.safeParse(await api.statusOci());
      if (!analisado.success) throw new ErroContrato(descreverIssues(analisado.error.issues));
      return analisado.data;
    },
    staleTime: 30_000,
  });
}
