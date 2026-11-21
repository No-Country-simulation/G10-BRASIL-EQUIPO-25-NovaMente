import type { Metadata } from 'next';
import { PoliticaPrivacidade } from '@/components/privacidade/PoliticaPrivacidade';

export const metadata: Metadata = {
  title: 'Privacidade e cookies',
  description:
    'Como o NovaMente trata dados pessoais e usa cookies, de acordo com a LGPD (Lei nº 13.709/2018).',
};

export default function PrivacidadePage() {
  return <PoliticaPrivacidade />;
}
