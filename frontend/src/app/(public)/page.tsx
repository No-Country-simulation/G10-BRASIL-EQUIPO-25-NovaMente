import type { Metadata } from 'next';
import { LandingPage } from '@/components/landing/LandingPage';

export const metadata: Metadata = {
  title: { absolute: 'NovaMente — material didático a partir de documentação técnica' },
  description:
    'Transforme documentação técnica em flashcards, quizzes, tutoriais e resumos executivos adaptados ao perfil do seu público.',
  openGraph: {
    title: 'NovaMente — material didático a partir de documentação técnica',
    description:
      'Transforme documentação técnica em flashcards, quizzes, tutoriais e resumos executivos adaptados ao perfil do seu público.',
    type: 'website',
    locale: 'pt_BR',
  },
};

export default function Home() {
  return <LandingPage />;
}
