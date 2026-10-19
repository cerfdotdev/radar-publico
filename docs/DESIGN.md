# Design

Sistema visual do Radar Público. Telas de referência: canvas "Radar Público — Wireframe e Hi-fi" (artboards Hi-fi e Sistema). Contexto de produto em [PRODUCT.md](PRODUCT.md).

## Direção

Ferramenta cívica de consulta: fundo branco puro, texto quase preto, uma cor de marca (terracota) usada com moderação. A busca é o centro da tela; a fonte do dado aparece junto de cada resultado.

- **Estratégia de cor:** contida. A terracota ocupa no máximo ~10% da tela: botão principal, foco, links e chips de filtro.
- **Tipografia:** uma família só, IBM Plex Sans, mais IBM Plex Mono para números, códigos e padrões de busca.
- **Profundidade:** sem sombras; separação por bordas de 1 px e pela superfície `--surface`.

## Tokens

```css
:root {
  /* Neutros */
  --bg: oklch(1 0 0);                    /* #FFFFFF  fundo */
  --surface: oklch(0.975 0.004 42);      /* #F9F6F5  painel de busca, cabeçalho de tabela, hover de linha */
  --line: oklch(0.9 0.008 42);           /* #E3DCDA  divisórias */
  --line-strong: oklch(0.62 0.012 42);   /* #8D8481  borda de campos, 3,7:1 */
  --ink: oklch(0.22 0.012 42);           /* #201916  texto, 17,4:1 */
  --ink-2: oklch(0.4 0.012 42);          /* #4E4643  texto secundário, 9,3:1 */
  --muted: oklch(0.5 0.012 42);          /* #6A615E  placeholder, 6,0:1 */

  /* Marca */
  --primary: oklch(0.5 0.13 42);         /* #9E441D  botão principal, foco; texto branco 6,4:1 */
  --primary-hover: oklch(0.44 0.12 42);  /* #873611 */
  --primary-soft: oklch(0.955 0.022 42); /* #FEECE5  chips de filtro */
  --primary-text: oklch(0.42 0.12 42);   /* #803009  links, 8,9:1 */

  /* Situação do vínculo */
  --ativo-bg: oklch(0.95 0.03 240);      /* #DDF2FF */
  --ativo-fg: oklch(0.38 0.09 240);      /* #00476D  8,6:1 sobre ativo-bg */
  --apos-bg: oklch(0.95 0.045 85);       /* #FCEDCD */
  --apos-fg: oklch(0.42 0.08 75);        /* #664610  7,4:1 sobre apos-bg */

  /* Retorno */
  --info-bg: oklch(0.96 0.02 240);   --info-fg: oklch(0.38 0.09 240);  --info-line: oklch(0.86 0.04 240);
  --warn-bg: oklch(0.965 0.04 85);   --warn-fg: oklch(0.42 0.08 70);   --warn-line: oklch(0.86 0.07 80);
  --err-bg: oklch(0.96 0.022 12);    --err-fg: oklch(0.48 0.17 12);    --err-line: oklch(0.85 0.06 12);

  /* Tipografia */
  --sans: 'IBM Plex Sans', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;

  /* Espaço (px): 4 8 12 16 24 32 40 64 · Raio: 6 chips internos, 8 controles, 10 painéis, 16 pílulas */
}
```

Os comentários com hex são para referência (Figma); no código use os valores OKLCH.

## Tipografia

| Uso | Tamanho / peso |
|---|---|
| Título da página | 34 / 600, `letter-spacing: -0.015em`, `text-wrap: balance` |
| Título de seção | 23 / 600 |
| Subtítulo | 19 / 600 |
| Corpo | 16 / 400, linha 1,5, máximo ~70 caracteres |
| Rótulo de campo | 14 / 600 |
| Auxiliar | 14 / 400 em `--ink-2` |
| Números, códigos, padrões `%` | Plex Mono 15 / 500, `font-variant-numeric: tabular-nums`, alinhados à direita |

Interface em caixa de frase, sem rótulos em maiúsculas espaçadas. Texto vindo da fonte (nomes, cargos, órgãos) fica em maiúsculas como publicado, com `letter-spacing: 0.01em`.

## Componentes

- **Botão principal** (`--primary`, texto branco, 48–52 px de altura): uma ação principal por tela (Buscar). Estados: hover `--primary-hover`, foco com anel, carregando ("Buscando…", desabilitado), desabilitado em `--line`.
- **Botão secundário:** borda `--line-strong` 1,5 px, fundo branco; hover em `--surface`.
- **Campo:** 44 px (52 px no campo de nome), borda `--line-strong` 1,5 px; hover `--ink-2`; foco `--primary` + anel; erro com borda 2 px `--err-fg`, fundo `--err-bg`, ícone e mensagem abaixo, `aria-invalid` e `aria-describedby`.
- **Alternador** (só Nome exato × Nome parecido): selecionado em `--ink`, não em terracota. Situação e UF usam `<select>`.
- **Pílulas de situação:** Ativo (marcador cheio, azul) e Aposentado (marcador vazado, ocre). Nunca só cor.
- **Chips de filtro:** `--primary-soft` com botão de remover de 28 px e "Limpar tudo".
- **Tabela:** cabeçalho em `--surface`, linhas com hover `--surface`, nome em `<th scope="row">` como link para o detalhe; em telas estreitas a tabela rola dentro da própria caixa e, no celular, vira lista.
- **Avisos:** informação (azul, ex.: 429), atenção (ocre, ex.: mais de 10.000), erro (rosado, ex.: 504). Sempre ícone + título + o que fazer.

## Interação e acessibilidade

- Foco visível em tudo: `outline: 2px solid var(--primary); outline-offset: 2px` em `:focus-visible`.
- Alvos de toque de no mínimo 44 × 44 px.
- Título dos resultados em `aria-live="polite"`; carregamento com `aria-busy`.
- Movimento só para estado: hover/foco 150 ms, troca de resultados 200 ms, `cubic-bezier(.25, 1, .5, 1)`. Com `prefers-reduced-motion: reduce`, sem transições.
- Risco conhecido: `--primary` e `--err-fg` têm luminosidade parecida e diferem no matiz. Por isso erro nunca é só uma borda vermelha: sempre ícone, mensagem e fundo `--err-bg`.
