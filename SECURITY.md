# Política de segurança

## Como reportar uma vulnerabilidade

Não abra issue pública. Use **Security → Report a vulnerability** neste repositório (reporte privado do GitHub). Respondemos em até 3 dias.

## O que o repositório aplica

- `main` protegida: só entra por Pull Request, com o check `ci-ok` passando, a branch atualizada e todas as conversas resolvidas. Sem force push e sem apagar a branch. A aprovação obrigatória valeu até 20/10/2026.
- CODEOWNERS: o líder técnico é pedido como revisor de CI/CD e dos arquivos de segurança.
- Secret scanning com push protection: pushes com credenciais são bloqueados.
- Dependabot: alertas, PRs de segurança e atualizações semanais com cooldown de 7 dias.
- GitHub Actions: só as do próprio GitHub e `anchore/scan-action`, `ossf/scorecard-action` e `zizmorcore/zizmor-action`; o repositório exige que todas estejam fixadas por SHA de commit, e o token é só de leitura por padrão.
- CI: ruff, bandit, pip-audit, npm audit, hadolint, scan de imagens (Grype), CodeQL, revisão de dependências nos PRs, auditoria dos workflows (zizmor) e OpenSSF Scorecard.
