# Conceito 3 — Página + faísca

Kit de teste do conceito escolhido para exploração. **Abra `index.html`** para ver a folha completa.

## Arquivos

| Arquivo | Uso |
|---|---|
| `simbolo-principal.svg` | Símbolo completo (página + N + faísca), usado no header e no favicon |
| `logo-header.svg` | Lockup do header no modo escuro: ícone principal + “ovaMente” |
| `logo-header-light.svg` | Lockup do header no modo claro |
| `simbolo-mono-claro.svg` | Monocromático claro, para fundos escuros |
| `simbolo-mono-escuro.svg` | Monocromático escuro, para fundos claros |
| `wordmark.svg` | Wordmark “NovaMente” em contornos, com “Mente” em gradiente |
| `wordmark-mono-claro.svg` | Wordmark monocromático claro |
| `wordmark-mono-escuro.svg` | Wordmark monocromático escuro |
| `lockup-horizontal.svg` | Símbolo + wordmark horizontal |
| `lockup-vertical.svg` | Símbolo + wordmark vertical |
| `icone-app.svg` | Ícone de aplicativo com fundo em gradiente |

O wordmark foi convertido em **contornos reais** a partir da Inter variável já usada no app (SIL Open Font License), sem depender de fonte instalada.

## Decisão

- **Linha oficial:** símbolo principal (página + N + faísca), sem versão compacta.
- **Header:** o ícone principal ocupa o lugar do N e é seguido por “ovaMente”.
- **Faísca:** acompanha o gradiente violeta → ciano.
- **Ícone de app:** a faísca fica branca para manter contraste sobre o fundo em gradiente.
- **Favicon:** usa o símbolo principal.

## O que o teste mostra

- **Acima de 48 px:** o símbolo principal funciona bem; a página dá contexto e a faísca chama atenção.
- **Entre 16 e 32 px:** o contorno da página e o N interno perdem definição, mas a decisão foi manter o principal para preservar a assinatura.
- **Monocromático:** a silhueta se mantém; a faísca é o elemento que continua reconhecível.
- **Header:** o lockup horizontal precisa de um wordmark desenhado em contornos para não depender da fonte do sistema.
- **Ícone de app:** o fundo em gradiente funciona, mas a página interna pode ser simplificada para 128 px.

## Próximos passos

1. Refinar a geometria da página e do N no símbolo principal.
2. Validar o espaçamento/kerning do wordmark e a relação símbolo + texto.
3. Testar a marca nas skins violeta e ciano do app.
4. Fechar as regras de uso: margem de respiro, tamanho mínimo, fundos permitidos e versões proibidas.
5. Produzir favicon `.ico`/PNG e os tamanhos de app icon.

> Conceito exploratório. Ainda não é a marca final.
