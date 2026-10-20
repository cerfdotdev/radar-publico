# Sprint review e retrospectiva

Duas sprints de um dia no [Project](https://github.com/users/cerfdotdev/projects/12), com as datas reais. Os números de pontos são do [`burndown.md`](../burndown.md); o que cada integrante fez em cada dia está no [relatório](../relatorio.md#5-histórico-diário-do-github).

## Sprint 1 (18/10/2026)

**Meta:** containers subindo, banco carregado e indexado, API com filtros básicos e o frontend fazendo a primeira busca.

### Review

| | Pontos |
|---|--:|
| Planejados | 41 |
| Concluídos dentro da sprint | 19 |
| Concluídos depois do fim da sprint | 21 |
| Não planejados (daily #1) | 1 |

Entregue:

- Dicionário e análise dos dados de origem, contrato da API (#30, #32).
- Schema, carga e tratamento dos dados, índices B-tree e `pg_trgm` (#31).
- Pipeline de CI e controles de cadeia de suprimentos (#28).
- Backend: Dockerfile, Flask e Gunicorn (#34); pool de conexões e configuração por ambiente (#36); `GET /api/servidores` com filtros (#38).
- Frontend: stack, Dockerfile e proxy para a API (#37); identidade visual e busca simples (#40).

O backlog foi cadastrado às 22:30, a uma hora e meia do fim do dia, e a maior parte da Sprint 1 foi feita na madrugada de 19/10.

### Retrospectiva

- **Foi bem:** CI e proteção da `main` desde o início; revisão cruzada em todos os PRs; banco medido e ajustado com os dados reais.
- **Não foi bem:** começamos tarde no dia e depois do prazo do enunciado; nenhuma daily registrada; vários PRs só passaram depois de correções do líder.
- **Ação para a Sprint 2:** cada integrante abrir o PR cedo, com `Closes #N`, testes e o CI verde antes de pedir revisão.

## Sprint 2 (19/10/2026)

**Meta:** similaridade, busca combinada, paginação, tratamento de erros, proteção contra sobrecarga, teste de carga, frontend completo, app desktop e relatório.

### Review

Planejados 56 pontos, mais 13 adicionados em 20/10 (#52 contrato da API, #53 arquitetura e #54 cache). Nenhuma issue da Sprint 2 fechou dentro de 19/10: as entregas foram mergeadas na noite de 19/10 e em 20/10, e as issues fecharam em 20/10 (detalhes e números finais no [`burndown.md`](../burndown.md)).

Entregue:

- Busca por similaridade (#44, #45) e contrato completo: detalhe, `similar` com filtros, aspas e `%` cru (#58).
- Timeout das buscas (#47), limite por IP e de concorrência (#49), limites pelo `.env` e API só em `127.0.0.1` (#51), cache das buscas (#59).
- Frontend: busca combinada e por similaridade (#46), paginação, detalhe e estados de erro (#48).
- Desktop: app PySide6 (#50) e executável com PyInstaller para Linux e Windows (#55).
- Arquitetura (#56), burndown (#57), relatório (#60), teste de carga paralela ([`carga.md`](../carga.md)) e esta retrospectiva.

### Retrospectiva

- **Foi bem:** o sistema chegou completo, com os requisitos do enunciado cobertos e testados com os dados reais; documentação e scripts geram o burndown e o histórico.
- **Não foi bem:** de novo sem dailies; as entregas dos colegas chegaram de madrugada e precisaram de correção; o trabalho passou do dia da sprint; a revisão obrigatória foi removida no fim para destravar os merges.
- **Para um próximo projeto:** cadastrar o backlog antes da primeira sprint; sprints com tamanho realista; daily curta registrada na issue; um PR pequeno por issue, com testes e o CI verde antes da revisão; manter a revisão cruzada até o fim.
