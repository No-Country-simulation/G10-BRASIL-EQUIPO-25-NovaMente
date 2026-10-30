'use client';

import { createContext, useContext } from 'react';
import { httpApiClient } from './httpApiClient';
import type { NovaMenteApi } from './NovaMenteApi';

const ApiContext = createContext<NovaMenteApi | null>(null);

export function ApiProvider({
  client = httpApiClient,
  children,
}: {
  client?: NovaMenteApi;
  children: React.ReactNode;
}) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): NovaMenteApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error('useApi exige ApiProvider');
  return api;
}
