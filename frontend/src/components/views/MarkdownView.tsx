import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import type { ConteudoAdaptado } from '@/types/novamente';

type Props = { conteudo: Extract<ConteudoAdaptado, { tipo: 'markdown' }> };

export function MarkdownView({ conteudo }: Props) {
  return (
    <article className="prose prose-invert max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {conteudo.itens}
      </ReactMarkdown>
    </article>
  );
}
