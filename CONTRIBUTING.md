# Como contribuir

## Antes do primeiro commit

O e-mail do seu git precisa estar cadastrado e verificado na sua conta do GitHub. Sem isso, seus commits não aparecem como seus no histórico, e o histórico de cada integrante é item avaliado.

```bash
git config user.name  "Seu Nome"
git config user.email "email-cadastrado-no-github@exemplo.com"
```

## Fluxo de trabalho

1. Pegue uma issue da coluna **Todo** da sprint atual no Project e mova para **In Progress**.
2. Crie uma branch a partir da `main`: `feat/<numero-da-issue>-descricao-curta` (ou `fix/`, `docs/`, `chore/`).
3. Faça commits pequenos e frequentes, no padrão [Conventional Commits](https://www.conventionalcommits.org/pt-br/):
   - `feat(api): adiciona filtro por uf`
   - `fix(db): corrige índice trigram do nome`
   - `docs: daily de 18/10`
4. Abra um Pull Request com `Closes #<numero>` na descrição e mova a issue para **In Review**.
5. Outro integrante revisa e aprova. Depois do merge, a issue fecha sozinha e vai para **Done**.

Ninguém faz push direto na `main`.

## Daily

No início de cada sprint e ao fim de cada bloco de trabalho, cada integrante comenta na issue de daily da sprint:

- O que fiz
- O que vou fazer
- Impedimentos

## Pontos (story points)

Fibonacci: 1, 2, 3, 5, 8. Issues acima de 8 devem ser quebradas.
