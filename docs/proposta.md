# Proposta do Projeto - NovaMente

---

## 1. Visão do Produto

- **Para** EdTechs, instituições de ensino, empresas de tecnologia e equipes de engenharia que precisam capacitar públicos diversos desde iniciantes em transição de carreira até lideranças técnicas e arquitetos.
- **Que enfrentam** processos morosos de semanas para a criação e adaptação manual de materiais didáticos densos e em constante evolução.
- **O NovaMente** é um sistema inteligente de adaptação e geração de conteúdo educacional baseado em IA Generativa, Arquitetura RAG e Orquestração de Agentes.
- **Que** ingere documentações técnicas, manuais de software e bases de conhecimento para transformá-los automaticamente em conteúdos educacionais personalizados e estruturados de acordo com o perfil do destinatário, a indústria de aplicação e o formato pedagógico.
- **Diferente de** processos manuais fragmentados com consultores especializados e geradores de texto genéricos sem ancoragem técnica.
- **Nosso produto** oferece automação completa via RAG (Retrieval-Augmented Generation) com fidelidade às fontes originais, permitindo parametrizar perfis (iniciante, pleno, arquiteto), formatos de saída (flashcards, quizzes, tutoriais) e persistência obrigatória em nuvem na Oracle Cloud (OCI Object Storage).

### Contextualização e Evidência do Problema
Empresas e escolas de tecnologia produzem documentações técnicas ricas, mas muitas vezes inacessíveis para quem não domina jargões avançados. Um mesmo manual de infraestrutura em nuvem (como a OCI), por exemplo, precisa ser ensinado de formas muito diferentes para quem está dando os primeiros passos na programação e para quem vai tomar decisões executivas de investimento. O **NovaMente** resolve esse gargalo ao permitir ingerir documentações complexas sem pré-processamento manual e gerar múltiplos formatos de estudo com poucos cliques, reduzindo o tempo de produção de semanas para minutos e mitigando alucinações por meio de ancoragem estrita nas fontes originais.

---

## 2. Fundamentação Pedagógica, Metodológica e Experiência do Usuário (UX/IHC)

Para garantir que o **NovaMente** entregue tanto eficácia no aprendizado quanto excelência na experiência de uso da interface interativa, o projeto fundamenta-se em pilares consolidados das ciências da educação e da Interação Humano-Computador (IHC):

### Fundamentação Pedagógica
- **Andaimagem Cognitiva (*Scaffolding* - Vygotsky):** O sistema atua como um mediador inteligente que reduz a complexidade de documentações densas, adaptando o discurso ao nível de proficiência do destinatário (do iniciante ao avançado), preenchendo lacunas de conhecimento técnico de forma gradual.
- **Teoria da Carga Cognitiva (Sweller):** Ao fragmentar manuais extensos em formatos objetivos (como resumos executivos, flashcards e tutoriais passo a passo), o NovaMente evita a sobrecarga de informações, otimizando a retenção cognitiva do aluno.
- **Aprendizagem Baseada em Evidências e *Microlearning*:** A disponibilização de flashcards de memorização e quizzes interativos fomenta a recuperação ativa e o aprendizado em pílulas, maximizando a fixação de conceitos técnicos complexos de infraestrutura e software.

## Princípios de IHC e Usabilidade
- **Teoria da Ação (Donald Norman):** Aplicada no design dos fluxos de ingestão de arquivos e parametrização. Garante alta visibilidade do estado do sistema, affordances claras e feedback imediato durante o processamento assíncrono da Inteligência Artificial.
- **Heurísticas de Usabilidade (Jakob Nielsen):** Norteiam a simplicidade e a eficiência da interface interativa, assegurando prevenção de erros, flexibilidade de uso e visibilidade limpa dos resultados.
- **Engenharia Semiótica (Clarisse de Souza):** Trata a interface como um "delegado" do designer que comunica de forma transparente ao usuário como a IA interpretou o documento técnico original, garantindo clareza na ancoragem das fontes e rastreabilidade dos dados gerados.

## 3. Definição do MVP

### Hipótese de Valor
> **Acreditamos que** educadores, instrutores e empresas de tecnologia **vão** utilizar o NovaMente para gerar pacotes didáticos personalizados a partir de manuais técnicos **porque** o sistema reduz o tempo de produção de semanas para minutos, garantindo rigor técnico, ancoragem sem alucinações e adequação pedagógica instantânea para diferentes públicos.

### Dentro do Escopo (MVP)
- **Ingestão de Conteúdo Técnico:** Recepção de arquivos nos formatos PDF, Markdown ou textos brutos.
- **Pipeline de RAG e Indexação:** Segmentação de texto (*chunking*), geração de embeddings e busca vetorial em Vector Store (ChromaDB / FAISS).
- **Orquestração com LLM:** Integração com Google Gemini (ou modelo equivalente) utilizando prompts estruturados (few-shot e role prompting).
- **Saída Estruturada (JSON):** Validação de schemas estritos com Pydantic contendo metadados, perfil aplicado, formato gerado e conteúdo adaptado.
- **Interface Interativa:** Aplicação web amigável em Next.js para upload e parametrização.
- **Persistência em Nuvem (OCI):** Integração obrigatória com o OCI Object Storage (camada *Always Free*) para armazenar documentos originais e artefatos gerados.

### Fora do Escopo (Pós-MVP)
- Deploy completo em nuvem em instância de máquina virtual OCI Compute.
- Sistema multi-agentes avançado utilizando LangGraph (planejador, redator e crítico).
- Geração de quizzes com avaliação e feedback em tempo real.
- Suporte multimodal para interpretação direta de diagramas técnicos.
- Exportação multiformato direta (Markdown, PDF formatado ou CSV compatível com Anki).

### Critérios de Sucesso do MVP
1. O sistema ingere com sucesso documentações técnicas em PDF, Markdown ou texto puro.
2. A pipeline de RAG recupera e ancora as respostas com alta fidelidade às fontes originais.
3. A aplicação gera saídas estruturadas em JSON e exibe o resultado interativamente na interface web (Next.js).
4. Os arquivos originais e JSONs gerados são salvos automaticamente no OCI Object Storage (*Always Free*).
5. O sistema demonstra a capacidade de adaptar um mesmo documento para pelo menos 2 perfis e 2 formatos distintos.

---

## 4. Backlog Inicial e Histórias de Usuário

*O backlog detalhado e dinâmico encontra-se no Quadro Kanban do projeto no GitHub.*

| ID | História de Usuário (Resultado de Valor) | Estimativa | Prioridade |
| :--- | :--- | :---: | :---: |
| **US01** | Como estudante ou instrutor, quero fazer upload de um manual técnico em PDF ou Markdown para que o sistema processe o conteúdo bruto. | 3 pts | **P1** |
| **US02** | Como desenvolvedor, quero implementar a pipeline de RAG com segmentação (chunking) e embeddings para ancorar as respostas na fonte. | 5 pts | **P1** |
| **US03** | Como usuário da plataforma, quero parametrizar o perfil do destinatário e o formato de saída (ex: Iniciante e Flashcards) para customizar o aprendizado. | 3 pts | **P1** |
| **US04** | Como avaliador, quero obter o resultado em formato JSON estrito validado via Pydantic contendo os termos-chave e o conteúdo didático adaptado. | 5 pts | **P1** |
| **US05** | Como administrador, quero integrar a aplicação com o OCI Object Storage (Always Free) para persistir automaticamente os arquivos gerados. | 5 pts | **P1** |
| **US06** | Como usuário final, quero interagir com uma interface gráfica amigável (Next.js) para testar os cenários de adaptação de forma simples. | 3 pts | **P2** |

---

## 5. Stack Tecnológico e Justificativa

- **Linguagem & Inteligência Artificial (Python 3.10+ & LangChain):** Padrão de mercado para ecossistemas de IA, oferecendo robustez na manipulação de dados, bibliotecas de leitura de PDFs e orquestração de LLMs.
- **Modelos de Linguagem (Google Gemini / OpenAI):** Modelos de alta capacidade para reescrita pedagógica, estruturação de tom e garantia de coerência didática.
- **Vector Store & Embeddings (ChromaDB / FAISS):** Soluções eficientes para armazenamento vetorial e buscas por similaridade semântica no processo de RAG.
- **Validação de Dados (Pydantic):** Utilizado para tipagem estrita de schemas de entrada e saída, garantindo a integridade dos objetos JSON gerados.
- **Interface Gráfica (Next.js):** Frameworks ágeis para a construção de interfaces web interativas voltadas a protótipos de IA.
- **Infraestrutura e Armazenamento (OCI Object Storage):** Serviço de armazenamento em nuvem da Oracle Cloud Infrastructure na camada *Always Free*, atendendo rigorosamente ao requisito de gratuidade do programa ONE.

---

## 6. Acordo de Processo

- **Cadência de Sprints:** O projeto será executado em sprints estruturadas de 0 a 5, cobrindo o período do programa.
- **Cerimônias do Scrum:**
  * **Sprint Planning:** Reunião de planejamento no início de cada sprint para alinhamento de metas e distribuição de tarefas.
  * **Daily Sync:** Acompanhamento diário para coordenar atividades, alinhar o progresso e destravar impedimentos.
  * **Sprint Review & Demo:** Apresentação prática dos resultados e entregas alcançadas ao final de cada ciclo.
- **Definição de Pronto (Definition of Done - DoD):**
  1. Código versionado em branch descritiva (`feat/...`, `fix/...`, `docs/...`) e integrado via Pull Request direcionado à branch `develop` com integração final em `main`.
  2. Pull Request revisado e aprovado por outros membro da equipe.
  3. Funcionalidade testada localmente com dados reais ou simulados.
  4. Documentação e comentários atualizados quando aplicável.
  5. Card correspondente atualizado e movido para a coluna **Done** no Kanban.
- **Limites de Trabalho em Progresso (WIP Limits):**
  * *Em Progresso:* Limitado para evitar sobrecarga e garantir foco nas entregas ativas.
  * *Em Revisão:* Limitado por tarefas simultâneas em validação de código.
- **Ferramentas Adotadas:**
  * **Gestão e Versionamento:** GitHub (Repositório, GitHub Projects com Kanban, Issues e Pull Requests)
  * **Comunicação:** Discord para alinhamentos síncronos e assíncronos.
  * **Ambiente de Desenvolvimento:** Python, Git e ferramentas de Cloud OCI.

---

## 7. Equipe

| Nome do Integrante | Papel no Projeto / Scrum |
| :--- | :--- |
| **Alex Grellet** | Vibe Coder / Developer |
| **Luan Carvalho** | Vibe Coder / Developer |
| **Mario Lucio Breder Junior** | Product Manager / Developer  |
| **Ramon Oliveira Cardoso** | Vibe Coder / Developer |
| **Renato Campos** | Tech Lead / Vibe Coder |


---

## 8. Informações da Apresentação DemoDay

- **Iniciativa:** Programa ONE (Oracle Next Education) & Alura — G10 / NoCountry
- **Foco Tecnológico:** Inteligência de Dados, RAG Avançado e Oracle Cloud Infrastructure (OCI)
- **Repositório GitHub:** [Repositório Oficial do NovaMente](https://github.com/No-Country-simulation/G10-BRASIL-EQUIPO-25-NovaMente)
