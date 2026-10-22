import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { baixarBlob } from './download';

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.restoreAllMocks());

describe('baixarBlob', () => {
  it('dispara o download com o nome informado e revoga a URL', () => {
    const clique = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    baixarBlob(new Blob(['conteudo']), 'arquivo.md');

    expect(URL.createObjectURL).toHaveBeenCalled();
    expect(clique).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock');
    expect(document.querySelector('a[download]')).toBeNull();
  });
});
