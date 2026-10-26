import { describe, expect, it } from 'vitest';
import { buttonVariants } from './button';

describe('buttonVariants', () => {
  it('usa o token de hover com contraste AA na variante primária', () => {
    expect(buttonVariants({ variant: 'default' })).toContain('hover:bg-[var(--accent-hover)]');
    expect(buttonVariants({ variant: 'default' })).not.toContain('hover:bg-primary/80');
  });

  it('mantém as demais variantes inalteradas', () => {
    expect(buttonVariants({ variant: 'outline' })).toContain('hover:bg-muted');
    expect(buttonVariants({ variant: 'secondary' })).toContain('hover:bg-[color-mix(');
    expect(buttonVariants({ variant: 'ghost' })).toContain('hover:bg-muted');
    expect(buttonVariants({ variant: 'destructive' })).toContain('hover:bg-destructive/20');
    expect(buttonVariants({ variant: 'link' })).toContain('hover:underline');
  });
});
