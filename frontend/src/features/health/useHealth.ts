'use client';

import { useQuery } from '@tanstack/react-query';
import { useApi } from '@/services/api/ApiProvider';
import { HealthRespostaSchema } from '@/types/schemas';

export function useHealth() {
  const api = useApi();
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => HealthRespostaSchema.parse(await api.health()),
    refetchInterval: 60_000,
    staleTime: 60_000,
    retry: false,
  });
}
