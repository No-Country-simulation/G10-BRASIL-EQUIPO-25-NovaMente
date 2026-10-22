import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Providers } from './providers';
import { SkinProvider } from '@/features/theme/SkinProvider';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-jetbrains', display: 'swap' });

export const metadata: Metadata = {
  title: 'NovaMente — material didático a partir de documentação técnica',
  description: 'Gere flashcards, quizzes, tutoriais e resumos executivos ancorados na sua documentação.',
};

const scriptSkin = `try{var b=localStorage.getItem('novamente.skin');var s=b?JSON.parse(b).state.skin:null;document.documentElement.dataset.skin=s==='ciano'?'ciano':'violeta'}catch(e){document.documentElement.dataset.skin='violeta'}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-skin="violeta"
      className={`${inter.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: scriptSkin }} />
      </head>
      <body>
        <Providers>
          <SkinProvider>{children}</SkinProvider>
        </Providers>
      </body>
    </html>
  );
}
