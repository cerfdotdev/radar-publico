# Política de segurança

## Como reportar uma vulnerabilidade

Não abra issue pública. Use **Security → Report a vulnerability** neste repositório (reporte privado do GitHub). Respondemos em até 3 dias.

## O que o repositório aplica

- `main` protegida: só entra por Pull Request aprovado, com o check `ci-ok` passando e todas as conversas resolvidas. Sem force push e sem apagar a branch.
- CODEOWNERS: o líder técnico revisa CI/CD e arquivos de segurança.
- Secret scanning com push protection: pushes com credenciais são bloqueados.
- Dependabot: alertas, PRs de segurança e atualizações semanais com cooldown de 7 dias.
- GitHub Actions: só actions permitidas, fixadas por SHA de commit, com token só de leitura por padrão.
- CI: ruff, bandit, pip-audit, npm audit, hadolint, scan de imagens (Grype), CodeQL, revisão de dependências nos PRs, auditoria dos workflows (zizmor) e OpenSSF Scorecard.
