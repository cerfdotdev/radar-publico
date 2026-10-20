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
5. Outro integrante revisa. Desde 20/10/2026 a aprovação não é obrigatória (só o líder tinha tarefas abertas), mas o CI continua. Depois do merge, a issue fecha sozinha e vai para **Done**.

Ninguém faz push direto na `main`.

## Daily

No início de cada sprint e ao fim de cada bloco de trabalho, cada integrante comenta na issue de daily da sprint:

- O que fiz
- O que vou fazer
- Impedimentos

## Pontos (story points)

Fibonacci: 1, 2, 3, 5, 8. Issues acima de 8 devem ser quebradas.

## CI e segurança

Todo PR roda o workflow **CI**. O merge só é liberado com o check `ci-ok` verde, a branch atualizada com a `main` e todas as conversas resolvidas. Até 20/10/2026 também exigia a aprovação de um code owner.

| Área | O que o CI verifica | Rodar localmente |
|---|---|---|
| Backend | `ruff`, `bandit`, `pip-audit`, `pytest` com cobertura mínima de 70% e Postgres real | `pip install -r .github/ci/requirements.txt` e os mesmos comandos dentro de `projeto/backend` |
| Frontend | `npm ci --ignore-scripts`, `npm audit signatures`, `npm audit`, lint, testes, build | `npm ci && npm run lint && npm test` |
| Docker | `docker compose config`, `hadolint`, build, scan de vulnerabilidades (Grype), smoke test com `docker compose up` | `docker compose up --build` |
| Scripts | `ruff`, `bandit` e `pytest` do burndown e do histórico (`scripts/burndown.py` e `scripts/historico_github.py`) | os mesmos comandos dentro de `scripts/` |
| Geral | CodeQL, revisão de dependências do PR, auditoria dos workflows (zizmor) | — |

O backend espera os testes em `projeto/backend/tests/` e lê o banco de `DATABASE_URL`.

### Regras de cadeia de suprimentos

- Fixe versões exatas no `requirements.txt` (`flask==x.y.z`) e versione o `package-lock.json`.
- Imagens base dos Dockerfiles com tag e digest: `FROM python:3.13-slim@sha256:...` (o Dependabot atualiza).
- Containers não rodam como root: use `USER` no Dockerfile.
- Actions novas só fixadas por SHA de commit, nunca por tag. O repositório recusa actions não fixadas.
- Nunca commite `.env` nem credenciais. Use `projeto/.env.example` como modelo.
