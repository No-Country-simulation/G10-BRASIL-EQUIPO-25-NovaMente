import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => cleanup());

// Testes de serviço podem rodar em ambiente node (sem DOM); os de UI, em jsdom.
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverMock);

// Node não resolve URL relativa; o app sempre chama caminho relativo.
const fetchOriginal = globalThis.fetch;
globalThis.fetch = ((entrada: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof entrada === 'string' && entrada.startsWith('/') ? `http://localhost${entrada}` : entrada;
  return fetchOriginal(url as RequestInfo, init);
}) as typeof fetch;
