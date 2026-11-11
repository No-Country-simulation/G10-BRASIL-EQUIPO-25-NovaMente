import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Providers } from './providers';
import { SkinProvider } from '@/features/theme/SkinProvider';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

export const metadata: Metadata = {
  title: {
    default: 'NovaMente — material didático a partir de documentação técnica',
    template: '%s · NovaMente',
  },
  description: 'Gere flashcards, quizzes, tutoriais e resumos executivos ancorados na sua documentação.',
};

const scriptTema = `try{var b=localStorage.getItem('novamente.skin');var s=b?JSON.parse(b).state:null;var skin=s&&s.skin==='ciano'?'ciano':'violeta';var modo=s&&s.modo==='light'?'light':'dark';document.documentElement.dataset.skin=skin;document.documentElement.dataset.modo=modo;document.documentElement.style.colorScheme=modo}catch(e){document.documentElement.dataset.skin='violeta';document.documentElement.dataset.modo='dark';document.documentElement.style.colorScheme='dark'}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-skin="violeta"
      data-modo="dark"
      className={`${inter.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: scriptTema }} />
      </head>
      <body>
        <Providers>
          <SkinProvider>{children}</SkinProvider>
        </Providers>
      </body>
    </html>
  );
}
