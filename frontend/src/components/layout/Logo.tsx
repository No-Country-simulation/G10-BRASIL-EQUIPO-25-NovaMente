import Link from 'next/link';
import { ROTAS } from '@/lib/rotas';

export interface LogoProps {
  href?: string;
  className?: string;
}

/**
 * Lockup da marca para headers. O SVG já traz símbolo + wordmark em contornos,
 * então não depende de fonte instalada e funciona nas duas skins.
 */
export function Logo({ href = ROTAS.landing, className }: LogoProps) {
  return (
    <Link
      href={href}
      aria-label="NovaMente — página inicial"
      className={className}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/logo-header.svg"
        alt="NovaMente"
        width={425}
        height={130}
        className="logo-para-modo-escuro h-8 w-auto sm:h-10"
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/logo-header-light.svg"
        alt="NovaMente"
        width={425}
        height={130}
        className="logo-para-modo-claro h-8 w-auto sm:h-10"
      />
    </Link>
  );
}
