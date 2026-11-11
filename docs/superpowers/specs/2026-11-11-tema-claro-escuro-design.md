# Tema claro/escuro combinável com as skins

**Data:** 2026-11-11
**Status:** design aprovado na conversa; spec revisada por builder check em 2026-11-11; aguardando aprovação final
**Escopo:** frontend Next.js — tokens, estado de tema, switch, logo e testes

Fontes de verdade:

- `docs/superpowers/specs/2026-10-21-novamente-frontend-design.md` — sistema de skins e tokens.
- `docs/brand/preview/conceito-3/` — identidade escolhida.
- Este documento — resolve o modo claro/escuro.

---

## 1. Objetivo

Adicionar um **modo claro/escuro** que funcione de forma independente do **acento** já existente (`violeta` e `ciano`). O resultado são quatro combinações:

| Modo | Acento | Resultado |
|---|---|---|
| Escuro | Violeta | atual |
| Escuro | Ciano | atual |
| Claro | Violeta | novo |
| Claro | Ciano | novo |

O usuário troca modo e acento separadamente, em qualquer tela, e a escolha persiste entre recarregamentos.

Sucesso significa:

1. O header, a landing, a empresa e a área do aluno funcionam nas quatro combinações.
2. O modo escolhido é aplicado antes do primeiro paint, sem flash de tema errado.
3. O logo tem variante legível no claro; o ícone e o wordmark mantêm contraste.
4. Textos e controles atendem AA nas quatro combinações.
5. O estado persiste com migração dos usuários que já tinham apenas `skin`.

---

## 2. Escopo

### Dentro

- Tokens de cor para `violeta` claro e `ciano` claro.
- Estado `modo` (`dark` | `light`) no store de tema, persistido.
- Atributo `data-modo` no `<html>`, ao lado de `data-skin`.
- Script anti-flash atualizado para aplicar skin + modo antes do paint.
- `SkinSwitcher` com dois controles: modo (sol/lua) e acento (violeta/ciano).
- Logo claro (`logo-header-light.svg`) e troca por CSS baseada em `data-modo`.
- Ajuste de `color-scheme` para controles nativos, scrollbars e autofill.
- Testes unitários, de componente e E2E; axe nas quatro combinações.
- Capturas de header claro para documentação.

### Fora

- Seguir automaticamente `prefers-color-scheme` na primeira visita.
- Modo de alto contraste, daltonismo ou escala de cinza.
- Novos acentos além de violeta/ciano.
- Tema por rota, por aluno ou por empresa.
- Reestilização de páginas de Storybook (`src/stories`) e componentes de exemplo.
- Migração de dados de backend (nada no backend muda).

---

## 3. Decisões

| # | Decisão | Alternativa descartada | Motivo |
|---|---|---|---|
| D1 | Modo e acento são ortogonais, com 4 combinações | Uma terceira skin “Claro” | O pedido é dark/light mode; separar modo de acento mantém as duas marcas |
| D2 | `data-skin` + `data-modo` no `<html>` | Um único `data-tema="violeta-dark"` | Atributos independentes simplificam CSS e testes |
| D3 | Store mantém a chave `novamente.skin`, versão 2, com `{ skin, modo }` | Nova chave `novamente.tema` | Evita perder a preferência de skin dos usuários atuais |
| D4 | Padrão inicial `dark` | Seguir o sistema operacional | A marca nasceu dark; mudança de modo deve ser escolha explícita |
| D5 | Tokens claros próprios por acento | Inverter cores automaticamente | Contraste e hierarquia exigem escolhas por acento |
| D6 | Logo claro separado, trocado por CSS | Recolorir o SVG via `currentColor` | O wordmark tem gradiente e branco; recolorir não resolve contraste |
| D7 | Dois controles no header (modo + acento) | Quatro botões de combinação | Menos ruído e mais clara a ideia de modo independente |
| D8 | `color-scheme` acompanha o modo | Deixar o navegador no padrão | Scrollbar, selects e autofill precisam combinar com o tema |
| D9 | Testes axe nas 4 combinações em `/` e ao menos uma rota clara da empresa e do aluno | Só testar o escuro | Contraste é o risco principal do claro |
| D10 | Sem dependência nova | Biblioteca de temas | O sistema atual já tem Zustand + CSS vars |
| D11 | Não ativar o variant `dark:` nesta entrega | Trocar `@custom-variant dark` para `[data-modo='dark']` | Hoje nenhum componente usa `dark:`; ativar mudaria o visual escuro atual (botões, selects, abas) |
| D12 | Header pode quebrar em duas linhas no mobile | Forçar uma linha ou esconder o seletor | O botão de modo acrescenta largura; quebrar evita overflow em 320 px sem esconder controle |
| D13 | Store valida `skin` e `modo` na reidratação | Validar só no script anti-flash | Sem isso, um valor corrompido no localStorage sobrescreve o fallback após a hidratação |
| D14 | Logo claro com “ova” escuro, gradiente escurecido, dobra lilás e miolo da faísca lilás | Recolorir o SVG atual ou usar branco | “ova” branco e faísca branca desaparecem no claro; o gradiente atual tem pouco contraste |

---

## 4. Tokens

### 4.1 Estrutura

`themes/tokens.css` passa a ter quatro blocos:

```css
:root,
[data-skin='violeta'][data-modo='dark'] { /* violeta escuro atual */ }

[data-skin='ciano'][data-modo='dark'] { /* ciano escuro atual */ }

[data-skin='violeta'][data-modo='light'] { /* novo */ }

[data-skin='ciano'][data-modo='light'] { /* novo */ }
```

O bloco `:root` cobre o primeiro paint antes do script, com `data-modo="dark"` no HTML.

### 4.2 Violeta claro

| Token | Valor |
|---|---|
| `--bg` | `#F7F5FF` |
| `--surface` | `#FFFFFF` |
| `--surface-elevated` | `#F1EDFF` |
| `--border` | `#DDD6FE` |
| `--border-strong` | `#C4B5FD` |
| `--fg` | `#1E1B2E` |
| `--fg-muted` | `#5B556E` |
| `--accent` | `#6D28D9` |
| `--accent-fg` | `#FFFFFF` |
| `--accent-hover` | `#5B21B6` |
| `--accent-muted` | `#EDE9FE` |
| `--success` | `#047857` |
| `--warning` | `#B45309` |
| `--danger` | `#B91C1C` |
| `--ring` | `#6D28D9` |

Contrastes calculados: `fg` 15,55:1; `fg-muted` 6,55:1; `accent` 7,10:1; `accent-fg` sobre accent 7,10:1; `warning` 5,02:1; `success` 5,48:1; `danger` 6,47:1.

### 4.3 Ciano claro

| Token | Valor |
|---|---|
| `--bg` | `#F1FBFD` |
| `--surface` | `#FFFFFF` |
| `--surface-elevated` | `#E6F7FB` |
| `--border` | `#BAE6FD` |
| `--border-strong` | `#7DD3FC` |
| `--fg` | `#102A36` |
| `--fg-muted` | `#4B6472` |
| `--accent` | `#0E7490` |
| `--accent-fg` | `#FFFFFF` |
| `--accent-hover` | `#155E75` |
| `--accent-muted` | `#CFFAFE` |
| `--success` | `#047857` |
| `--warning` | `#B45309` |
| `--danger` | `#B91C1C` |
| `--ring` | `#0E7490` |

Contrastes calculados: `fg` 14,19:1; `fg-muted` 5,93:1; `accent` 5,36:1; `accent-fg` sobre accent 5,36:1; `warning` 5,02:1; `success` 5,48:1; `danger` 6,47:1.

### 4.4 Tokens escuros

Os valores atuais de violeta/ciano escuro permanecem inalterados.

---

## 5. Estado e persistência

### 5.1 Store

`features/theme/useSkin.ts` continua sendo o store, agora com:

```ts
export type Modo = 'dark' | 'light';

interface SkinState {
  skin: SkinId;
  modo: Modo;
  setSkin: (skin: SkinId) => void;
  setModo: (modo: Modo) => void;
  alternarModo: () => void;
}
```

`persist` mantém `name: 'novamente.skin'`, `version: 2`, com `migrate`:

- versão 1 ou ausente: `{ ...estado, modo: 'dark' }`
- versão 2: mantém.

Além da migração, o store valida os valores na reidratação: `skin` fora de `violeta|ciano` cai em `violeta`; `modo` fora de `dark|light` cai em `dark`. A validação fica no `merge`/`migrate` do Zustand, não só no script inline, para que um localStorage corrompido não seja reaplicado pelo provider depois da hidratação.

### 5.2 `<html>`

`app/layout.tsx` passa a renderizar:

```tsx
<html lang="pt-BR" data-skin="violeta" data-modo="dark" ...>
```

O script inline lê `novamente.skin`, aplica `dataset.skin`, `dataset.modo` e `style.colorScheme` antes do paint. Valores inválidos caem em `violeta` + `dark`.

### 5.3 Provider

`SkinProvider` (mantém o nome para minimizar churn) observa `skin` e `modo` e atualiza:

```ts
document.documentElement.dataset.skin = skin;
document.documentElement.dataset.modo = modo;
document.documentElement.style.colorScheme = modo;
```

### 5.4 CSS

`globals.css` adiciona:

```css
html { color-scheme: dark; }
html[data-modo='light'] { color-scheme: light; }
```

O variant `dark` do Tailwind **não muda nesta entrega**. Hoje nenhum componente usa `dark:`, e trocar a âncora para `[data-modo='dark']` ativaria utilities `dark:` existentes nas primitivas shadcn, alterando o visual escuro aprovado. A troca fica para uma entrega futura, junto com a auditoria dessas utilities.

---

## 6. UI do seletor

`SkinSwitcher` vira dois grupos:

1. **Modo** — botão único com ícone `Sun`/`Moon`.
   - No escuro mostra `Sun` e `aria-label="Ativar modo claro"`.
   - No claro mostra `Moon` e `aria-label="Ativar modo escuro"`.
   - `aria-pressed` reflete `modo === 'light'`.
   - Toque mínimo de 44 px no mobile; no desktop pode compactar como o seletor atual.
2. **Acento** — os dois botões atuais, `Violeta` e `Ciano`, com `aria-pressed`.

Textos novos em `M.app`:

- `modoClaro`, `modoEscuro`, `ativarModoClaro`, `ativarModoEscuro`.

O seletor continua no header da landing, da empresa e do aluno.

**Responsivo:** `EmpresaHeader` passa de `h-16` para `min-h-16` e permite `flex-wrap` abaixo de `sm`; `LandingHeader` e `AlunoHeader` já quebram linha. O teste `5-responsivo` continua exigindo ausência de rolagem horizontal em 320/375 px, sem exigir header de uma linha. O botão de modo tem 44 px; os botões de acento mantêm o tamanho atual (24 px no mobile), dívida preexistente que não será ampliada nesta entrega.

---

## 7. Logo no modo claro

### 7.1 Arquivo

Criar `frontend/public/brand/logo-header-light.svg` com a mesma construção do lockup atual (`ícone principal + ovaMente`), mas:

- “ova” em `#1E1B2E`.
- Gradiente do “Mente”, da página e da faísca em `#6D28D9` → `#0E7490`.
- Página com contorno em gradiente e **sem preenchimento de fundo**.
- Dobra da página em `#DDD6FE` (lilás claro), visível sobre o branco.
- Faísca externa em gradiente; miolo em `#EDE9FE` (o contraste é com o gradiente da estrela, não com o fundo).
- Ícone continua ocupando o lugar do N.

O `logo-header.svg` atual permanece para o escuro.

### 7.2 Troca sem hydration mismatch

`Logo.tsx` renderiza os dois `<img>`:

```tsx
<img className="logo-para-modo-escuro" src="/brand/logo-header.svg" ... />
<img className="logo-para-modo-claro" src="/brand/logo-header-light.svg" ... />
```

CSS em `globals.css`:

```css
[data-modo='light'] .logo-para-modo-escuro { display: none; }
[data-modo='dark'] .logo-para-modo-claro { display: none; }
```

Isso garante que o primeiro paint já mostre o logo certo, sem depender de estado React nem causar mismatch. O link mantém `aria-label`; apenas o `<img>` visível entra na árvore de acessibilidade.

### 7.3 Favicon

`src/app/icon.svg` continua sendo o símbolo principal com fundo escuro, que funciona nos dois modos do navegador. Não há variante clara de favicon.

---

## 8. Acessibilidade

- AA em texto normal nas quatro combinações; os tokens claros foram calculados acima.
- Foco visível com `--ring` nos dois modos.
- Controles nativos com `color-scheme` correto.
- O botão de modo tem nome acessível que descreve a ação, não o estado.
- Overlays `bg-black/50` dos diálogos continuam funcionando no claro.
- Axe sem violação crítica ou séria em `/` nas quatro combinações.
- Axe sem violação crítica em uma rota clara da empresa e uma da área do aluno.
- `prefers-reduced-motion` não é afetado.

---

## 9. Testes

### Unitários/componentes

- `useSkin`: migração v1 → v2 adiciona `modo: 'dark'`; troca de modo persiste; `skin`/`modo` inválidos na reidratação caem em `violeta`/`dark`.
- `SkinSwitcher`: alterna modo, atualiza `data-modo`, mantém `data-skin`, persiste; `aria-pressed` correto; acento continua funcionando.
- `SkinProvider`: aplica `data-modo` e `colorScheme`.
- `Logo`: renderiza as duas variantes, com os `src` corretos e uma visível por CSS (classe).
- Layout/anti-flash: teste de unidade do script é opcional; validar por E2E.

### E2E

- Novo `9-tema.spec.ts`:
  1. Abre `/`, alterna para claro, confere `data-modo="light"` e persiste após reload.
  2. Alterna acento para ciano no claro e confere `data-skin="ciano"`.
  3. Volta ao escuro e confere o logo escuro visível / claro oculto.
  4. Abre `/empresa/gerar` e `/aluno` no claro e confere que o tema se mantém.
- `4-acessibilidade.spec.ts`: adicionar `/` em violeta claro e ciano claro; manter as duas escuras. Adicionar uma rota da empresa e uma do aluno no claro.
- `5-responsivo.spec.ts`: garantir que o header com o novo controle de modo continua sem rolagem horizontal em 320/375 px.
- `6-landing-empresa.spec.ts`: o teste do logo passa a considerar a variante visível por modo.

---

## 10. Fases

| Fase | Entrega |
|---|---|
| 1 | Tokens claros, store com `modo`, migração, provider e anti-flash |
| 2 | `SkinSwitcher` com modo + acento, mensagens e testes |
| 3 | Logo claro, troca por CSS, capturas e ajuste do teste de logo |
| 4 | E2E de tema, axe nas 4 combinações, README e verificação final |

---

## 11. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Flash de tema errado | Médio | Script inline aplica `data-modo` antes do paint |
| Hydration mismatch no logo | Médio | Duas imagens + CSS, sem estado React |
| Contraste do gradiente no claro | Alto | Gradiente escurecido `#6D28D9 → #0E7490`; axe nas 4 combinações |
| Componente com cor hardcoded | Médio | Auditoria encontrou só overlays e Storybook; revisar no E2E visual |
| Migração perder a skin atual | Médio | Chave existente + `migrate` para v2 |
| Superfície shadcn assumir claro/escuro errado | Médio | Aliases já apontam para tokens; manter `:root` e `.dark` mapeados |
| Ativar `dark:` do Tailwind sem auditoria | Alto | Variant permanece inerte nesta entrega (D11) |
| Header estourar em 320 px com o novo botão | Médio | `flex-wrap` + `min-h-16`; E2E de responsivo |
| Testes de axe ficarem lentos | Baixo | Cobrir 4 combinações só em `/`, mais uma rota clara por área |

---

## 12. Critérios de sucesso

- As quatro combinações são acessíveis pelo header e persistem.
- O primeiro paint não pisca o tema errado.
- O logo é legível no claro e no escuro; “ova” mantém contraste.
- `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` e `npm run e2e` verdes.
- Axe sem violação crítica/séria nas quatro combinações em `/` e sem crítica nas rotas claras de empresa/aluno.
- Nenhuma nova dependência.

---

## 13. Abordagens consideradas

1. **Modo + acento ortogonais (escolhida)** — 4 combinações, duas dimensões de escolha, tokens por combinação. Mais trabalho, melhor modelo mental e preserva as duas skins.
2. **Terceira skin clara** — 3 botões, implementação menor, mas mistura conceitos de modo e acento e não permite claro + ciano.
3. **Inversão automática de cores** — pouco trabalho, mas gera contraste ruim e identidade inconsistente; descartada.

A opção 1 foi escolhida na conversa.
