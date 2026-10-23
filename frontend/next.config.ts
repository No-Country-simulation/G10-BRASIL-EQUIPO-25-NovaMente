import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Acesso ao dev server a partir de outros dispositivos da rede local.
  // Só afeta `next dev`; em produção o Next ignora esta opção.
  // O host 192.168.1.* cobre a faixa (o `*` vale por um rótulo do hostname).
  allowedDevOrigins: ['192.168.1.50', '192.168.1.*'],
  turbopack: {
    rules: {
      '*.css': {
        loaders: ['@tailwindcss/turbopack'],
        as: '*.css',
      },
    },
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.API_BASE_URL ?? 'http://localhost:8000'}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
