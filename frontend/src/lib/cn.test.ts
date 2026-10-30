import { describe, expect, it } from 'vitest';
import { cn } from './cn';

describe('cn', () => {
  it('resolve conflito de utilitários do Tailwind mantendo o último', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });

  it('ignora valores falsy', () => {
    expect(cn('text-sm', false, undefined, null)).toBe('text-sm');
  });
});
