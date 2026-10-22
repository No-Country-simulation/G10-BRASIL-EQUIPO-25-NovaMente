'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { OciStatusSchema } from '@/types/schemas';

export function useOciStatus() {
  const api = useApi();
  return useQuery({
    queryKey: ['oci-status'],
    queryFn: async () => OciStatusSchema.parse(await api.statusOci()),
    staleTime: 30_000,
  });
}
