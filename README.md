# Radar Público

Aplicação full stack para consulta de servidores ativos e aposentados do Poder Executivo Federal, usando os dados abertos do [dados.gov.br](https://dados.gov.br):

- [Gestão de Pessoas do Executivo Federal — Aposentados](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal--aposentados)
- [Gestão de Pessoas do Executivo Federal — Carreiras/Cargos](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal---carreiras--cargos)

## Stack

| Camada | Tecnologia |
|---|---|
| Banco (`db-server`) | PostgreSQL + `pg_trgm` (busca por similaridade) |
| Backend | Python + Flask + Gunicorn |
| Frontend | Aplicação web em container próprio |
| Desktop (extra) | Python + PySide6, compilado com PyInstaller |
| Orquestração | Docker Compose |

## Como executar

```bash
cd projeto
docker compose up --build
```

O app desktop (PySide6) usa a mesma API: veja [`projeto/desktop/README.md`](projeto/desktop/README.md).

## Estrutura

```
projeto/            # pasta entregue no .zip
├── backend/        # API Flask + Gunicorn (Dockerfile)
├── frontend/       # aplicação web (Dockerfile)
├── desktop/        # app PySide6 que consome a API
├── db/             # scripts de schema, índices e carga dos dados
│   ├── init/       # executados pelo Postgres na primeira inicialização
│   └── data/       # CSVs baixados (não versionados)
└── docker-compose.yml
docs/               # relatório, sprints, dailies, burndown
scripts/            # utilitários da equipe (ex.: gerar burndown)
```

## Equipe

| Papel | GitHub | Responsabilidade principal |
|---|---|---|
| Líder técnico | [@cerfdotdev](https://github.com/cerfdotdev) | Banco de dados, Docker, relatório e burndown, revisão de PRs |
| Dev | [@joaoarenda](https://github.com/joaoarenda) | Backend / API |
| Dev | [@Alisson-dutra](https://github.com/Alisson-dutra) | Frontend web e app desktop |

## Metodologia

Scrum com 2 sprints de 1 dia (18/10/2026 e 19/10/2026), gerenciadas no GitHub Project **Radar Público**. Detalhes em [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`docs/`](docs/).
