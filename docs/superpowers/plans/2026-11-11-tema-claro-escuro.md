# Tema claro/escuro — plano de implementação

> **For agentic workers:** Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** modo claro/escuro combinável com violeta/ciano, persistido e sem flash.

**Architecture:** `data-modo` no `<html>` ao lado de `data-skin`; tokens em quatro blocos; store Zustand v2 com `{ skin, modo }`; logo claro/escuro trocado por CSS.

**Tech Stack:** Next 16, React 19, Zustand persist, Tailwind 4, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-11-tema-claro-escuro-design.md`

## Global Constraints

- Não ativar `dark:` do Tailwind nesta entrega.
- Chave `novamente.skin`, versão 2, migração v1 → modo `dark`.
- Validar `skin`/`modo` na reidratação.
- Default `violeta` + `dark`.
- AA nas quatro combinações.
- Sem dependência nova.
- Header pode quebrar linha no mobile; sem rolagem horizontal em 320/375 px.
- Logo claro: “ova” `#1E1B2E`, gradiente `#6D28D9 → #0E7490`, dobra `#DDD6FE`, miolo da faísca `#EDE9FE`.

---

### Task 1: Tokens e CSS

**Files:** `frontend/src/themes/tokens.css`, `frontend/src/app/globals.css`
- [ ] Adicionar blocos claro violeta e claro ciano com os valores da spec.
- [ ] Adicionar `color-scheme` por modo e regras `.logo-para-modo-*`.
- [ ] Não alterar `@custom-variant dark` nem os tokens escuros.
- [ ] Verificar `npm run build`.

### Task 2: Estado, provider e anti-flash

**Files:** `frontend/src/themes/registry.ts`, `frontend/src/features/theme/useSkin.ts`, `frontend/src/features/theme/SkinProvider.tsx`, `frontend/src/app/layout.tsx`
- [ ] Adicionar `Modo`, `MODOS`, `MODO_PADRAO`.
- [ ] Store v2 `{ skin, modo, setSkin, setModo, alternarModo }`, migração e validação.
- [ ] Provider aplica `data-modo` + `colorScheme`.
- [ ] Script inline aplica skin + modo antes do paint; `<html data-modo="dark">`.
- [ ] Teste de migração e valores inválidos.

### Task 3: Seletor

**Files:** `frontend/src/components/layout/SkinSwitcher.tsx`, `frontend/src/lib/mensagens.ts`, `frontend/src/components/layout/SkinSwitcher.test.tsx`
- [ ] Botão de modo com Sun/Moon, `aria-label` de ação e `aria-pressed`.
- [ ] Acento violeta/ciano inalterado.
- [ ] Header da empresa com `min-h-16` + `flex-wrap`.
- [ ] Mensagens novas e testes de toggle/persistência.

### Task 4: Logo claro

**Files:** `frontend/public/brand/logo-header-light.svg`, `frontend/src/components/layout/Logo.tsx`, `frontend/src/components/layout/Logo.test.tsx`, `docs/brand/preview/conceito-3/`
- [ ] Gerar lockup claro com os preenchimentos definidos.
- [ ] Renderizar as duas variantes e trocar por CSS.
- [ ] Atualizar teste do logo e capturas de header.

### Task 5: E2E, acessibilidade e verificação

**Files:** `frontend/e2e/4-acessibilidade.spec.ts`, `frontend/e2e/5-responsivo.spec.ts`, `frontend/e2e/6-landing-empresa.spec.ts`, `frontend/e2e/9-tema.spec.ts`, `frontend/README.md`
- [ ] Cobrir toggle, persistência, acento no claro, empresa/aluno.
- [ ] axe em `/` nas 4 combinações + rotas claras.
- [ ] Teste de logo por modo.
- [ ] `npm run typecheck`, lint, Vitest, build, E2E.
- [ ] Documentar as 4 combinações no README.
