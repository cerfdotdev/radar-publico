# Referências de design

HTML e CSS estáticos das telas do Radar Público, prontos para importar no Figma e para servir de base à implementação. São a mesma coisa que o canvas de design, em código comum.

| Arquivo | Conteúdo |
|---|---|
| `tokens.css` | Variáveis de cor, tipografia, espaço, raio e movimento. Fonte da verdade no código. |
| `componentes.css` | Classes de todos os componentes, só com os tokens. Responsivo (abaixo de 640 px vira layout de celular). |
| `busca.html` | Busca por nome parecido com filtro de órgão, resultados, paginação. Tabela no desktop, lista no celular. |
| `detalhe.html` | Detalhe de um vínculo (aposentado) com outros vínculos do mesmo nome. |
| `estados.html` | Carregando, mais de 10.000, nenhum resultado, entrada inválida, página inexistente, 429/503, 504/500. |
| `componentes.html` | Cores e estados de botões, campos, alternador, pílulas, chips e avisos. |
| `tokens.json` | Tokens no formato do plugin Tokens Studio para Figma. |
| `telas/*.png` | Capturas dos `.html` acima, em desktop (1440 px) e celular (390 px). |

Para ver: abra os `.html` direto no navegador. Nomes e valores são fictícios; as contagens citadas (1.504.516 vínculos, 23.362 professores em RJ) são reais.

## Importar no Figma

1. **Telas** com o plugin **html.to.design**: publique a pasta (ex.: GitHub Pages) ou use a extensão de navegador do plugin com o `.html` aberto. Importe cada tela em 1440 px e a `busca.html` também em 390 px (celular).
2. **Tokens** com o plugin **Tokens Studio**: carregue `tokens.json` e crie as variáveis/estilos do Figma a partir dele.
3. **Arrume** as camadas importadas: agrupe por seção e transforme botão, campo, pílula, chip e aviso em componentes, usando `componentes.html` como referência.

Confira se o seu plano do Figma permite esses plugins.

## Implementar com IA (Gemini ou outra)

Para cada issue, passe para a IA: este brief, `tokens.css`, `componentes.css`, o `.html` e o `.png` da tela e as partes de `docs/api.md` que ela usa. Depois compare o resultado com o canvas antes de abrir o PR.

**Brief para colar:**

> Implemente a tela a partir do HTML de referência anexado, mantendo a mesma estrutura, classes e textos. Use só as variáveis de `tokens.css`; não crie cores, tamanhos ou fontes novas. Os dados vêm da API descrita em `docs/api.md`.
>
> Regras que não aparecem no HTML:
> - O estado da busca fica na URL (`?similar=...&orgao=...&page=2`). Recarregar a página, "Copiar link" e voltar no navegador devem manter a busca.
> - Valide antes de chamar a API: nome com 2 a 100 caracteres; em "Nome parecido", pelo menos 3 letras além dos `%`; limite de 1 a 100.
> - "Nome exato" envia `nome=`; "Nome parecido" envia `similar=` e `limit=` e mostra a coluna Semelhança.
> - Se `meta.total` for 1, abra direto o detalhe. Se `meta.total_exato` for `false`, mostre o aviso de mais de 10.000.
> - Mapeie cada `error.code` para o estado correspondente de `estados.html`. Em 429/503, conte o tempo do header `Retry-After` e reabilite o botão sozinho.
> - Valores com `Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2 })`, em fonte mono, alinhados à direita. Datas ISO da API viram `DD/MM/AAAA`.
> - Texto vindo da fonte (nome, cargo, órgão) aparece como veio, em maiúsculas; não converta.
> - `uf` nulo aparece como "—" com `aria-label="não informado"`.
> - Autocompletar de cargo e órgão com `/api/cargos?q=` e `/api/orgaos?q=`, esperando 250 ms depois da última tecla.
> - Botão Buscar desabilitado e com "Buscando…" enquanto a requisição roda; título dos resultados com `aria-live="polite"`.
> - Respeite `prefers-reduced-motion`, foco visível e alvos de 44 px, como em `componentes.css`.

## Ordem sugerida

| Issue | Tela | Referência |
|---|---|---|
| #10 | Container, proxy `/api` | — |
| #11 | Tokens, topo, busca por nome exato, tabela | `tokens.css`, `busca.html`, `componentes.html` |
| #20 | Nome parecido, filtros, chips, layout de celular | `busca.html` (desktop e 390 px) |
| #21 | Paginação, detalhe, estados | `busca.html`, `detalhe.html`, `estados.html` |
