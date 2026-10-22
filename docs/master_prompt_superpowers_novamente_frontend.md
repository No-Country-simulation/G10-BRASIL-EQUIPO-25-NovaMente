# TASK: Desenvolver o Frontend da Aplicação "NovaMente" (Spec-Driven Development)

Você é um Engenheiro Frontend Principal especializado em React, Next.js (App Router), TypeScript, Tailwind CSS e Framer Motion. 
Sua missão é implementar a interface gráfica do projeto **NovaMente** utilizando Spec-Driven Development (SDD), estrito cumprimento dos princípios SOLID, Clean Code e otimização avançada de performance.

---

## 1. CONTEXTO DO PROJETO & ESPECIFICAÇÃO DE DOMÍNIO

O **NovaMente** é um sistema inteligente que ingere documentações técnicas (PDF, MD, TXT) e as converte em materiais didáticos adaptados (Flashcards, Quizzes, Tutoriais) ancorados via RAG e armazenados na Oracle Cloud Infrastructure (OCI Object Storage).

### Tipos e Contratos de Dados (TypeScript Spec)
Utilize rigorosamente estas interfaces em `src/types/novamente.ts`:

```typescript
export type PerfilDestinatario = 'Iniciante' | 'Desenvolvedor' | 'LiderTecnico' | 'Gestor';
export type FormatoSaida = 'Flashcards' | 'Quiz' | 'Tutorial' | 'ResumoExecutivo';
export type NichoSetor = 'Fintech' | 'Saude' | 'Ecommerce' | 'Geral';

export interface AdaptContentRequest {
  documento_titulo: string;
  documento_conteudo?: string;
  arquivo?: File;
  perfil_destinatario: PerfilDestinatario;
  formato_saida: FormatoSaida;
  nicho_setor: NichoSetor;
}

export interface FlashcardItem {
  frente: string;
  verso: string;
  dica_didatica?: string;
}

export interface QuizItem {
  pergunta: string;
  opcoes: string[];
  resposta_correta: number;
  explicacao: string;
}

export interface AdaptContentResponse {
  status: 'sucesso' | 'erro';
  metadados: {
    perfil_aplicado: PerfilDestinatario;
    formato_gerado: FormatoSaida;
    tempo_estimado_estudo_minutos: number;
    conceitos_chave: string[];
  };
  conteudo_adaptado: {
    titulo: string;
    introducao_contextualizada: string;
    itens: FlashcardItem[] | QuizItem[] | string;
  };
  avaliacao_qualidade: {
    ancoragem_fonte_score: number;
    clareza_pedagogica: 'Alta' | 'Media' | 'Baixa';
    observacoes?: string;
  };
  armazenamento_oci: {
    bucket: string;
    objeto_id: string;
    status_upload: 'concluido' | 'falha';
  };
}
```

---

## 2. DIRETRIZES DE ARQUITETURA E CLEAN CODE (SOLID)

1. **Single Responsibility Principle (SRP):**
   - Decouple completamente UI, Gerenciamento de Estado e Camada de Serviço/API.
   - Componentes visuais apenas renderizam dados. Regras de submissão e conversão de formulários devem ficar em Custom Hooks (ex: `useAdaptationForm`, `useFlashcards`).
2. **Open/Closed Principle (OCP):**
   - Implemente um padrão Strategy no renderizador de conteúdo (`ContentRenderer.tsx`). O aditamento de um novo formato de saída não deve modificar a estrutura da página principal, apenas registrar um novo visualizador no mapa de componentes.
3. **Interface Segregation Principle (ISP):**
   - Componentes visuais devem receber apenas os subconjuntos de dados necessários via props (ex: `FlashcardDeck` recebe apenas `items: FlashcardItem[]` e não o objeto `AdaptContentResponse` inteiro).
4. **Dependency Inversion Principle (DIP):**
   - Crie uma abstração para a API Client (`src/services/apiClient.ts`). O código dos componentes deve depender de interfaces de serviço, facilitando o chaveamento automático entre Mocks e Endpoints FastAPI reais.

---

## 3. DIRETRIZES DE PERFORMANCE & UX

- **Tree-Shaking & Dynamic Imports:** Carregue componentes pesados de animação (Framer Motion) e renderização de Markdown dinamicamente com `next/dynamic`.
- **Renderização e Memoização:** Utilize `useCallback` e `useMemo` estratégicos em manipuladores de eventos e cálculos pesados para evitar re-renders desnecessários.
- **Layout Shift Zero (CLS Zero):** Defina dimensões explícitas ou skeletons com CSS Tailwind em todas as áreas de carregamento de conteúdo.
- **Microinterações:**
  - `FlashcardDeck`: Animação 3D Flip usando `preserve-3d`, `backface-visibility: hidden` e Framer Motion.
  - `IngestionForm`: Estados visuais para Drag & Drop e progresso por etapas (*Processing step indicator*).

---

## 4. PLANO DE EXECUÇÃO PASSO A PASSO (SDD TASKS)

Execute as seguintes etapas sequencialmente:

1. **FASE 1 - Specs & Mock Service:**
   - Criar `src/types/novamente.ts` com as interfaces.
   - Criar `src/services/mockData.ts` contendo payloads válidos para Flashcards e Quizzes baseados na documentação da OCI VCN.
   - Criar `src/services/api.ts` que simula um delay de rede ($1.5s$) e retorna os mocks em modo de desenvolvimento.

2. **FASE 2 - Componentes Atômicos de Apresentação:**
   - Desenvolver `src/components/ui/FlashcardCard.tsx` (Card individual 3D com rotação via Framer Motion).
   - Desenvolver `src/components/views/FlashcardDeck.tsx` (Navegação/Carousel entre cartões).
   - Desenvolver `src/components/views/InteractiveQuiz.tsx` (Interface com seleção de alternativas e feedback imediato).
   - Desenvolver `src/components/views/OCIPanel.tsx` (Badge do RAG score + status do Bucket OCI).

3. **FASE 3 - Formulação & Orquestração:**
   - Criar `src/components/forms/IngestionForm.tsx` com validação estrita dos tipos de arquivo (`.pdf`, `.md`, `.txt`) e seletores parametrizados.
   - Criar `src/components/views/ContentRenderer.tsx` (Strategy Pattern para chavear entre Flashcard, Quiz e Tutorial).

4. **FASE 4 - Integração de Página Principal:**
   - Montar `src/app/page.tsx` conectando o formulário, o carregamento com Skeletons e os componentes visualizadores em um layout responsivo estilo Dashboard.

---
*Comece gerando a FASE 1 e aguarde aprovação antes de avançar para as FASEs seguintes.*