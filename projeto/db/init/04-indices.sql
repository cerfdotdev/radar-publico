-- Índices criados depois da carga (muito mais rápido que manter durante o INSERT).
\set ON_ERROR_STOP on
\timing on

-- Nome exato e ordenação padrão da listagem (nome, id)
CREATE INDEX servidor_nome_idx ON servidor (nome, id);

-- Similaridade e padrões com '%' (ILIKE / LIKE) no nome
CREATE INDEX servidor_nome_trgm_idx ON servidor USING gin (nome gin_trgm_ops);

-- Filtros já ordenados por nome, para a paginação não precisar ordenar milhares de linhas
CREATE INDEX servidor_cargo_nome_idx ON servidor (cargo_id, nome, id);
CREATE INDEX servidor_orgao_nome_idx ON servidor (orgao_id, nome, id);
CREATE INDEX servidor_uf_nome_idx    ON servidor (uf, nome, id) WHERE uf IS NOT NULL;

-- Busca parcial ("contém") nos nomes de cargo e órgão
CREATE INDEX cargo_nome_trgm_idx ON cargo USING gin (nome gin_trgm_ops);
CREATE INDEX orgao_nome_trgm_idx ON orgao USING gin (nome gin_trgm_ops);
CREATE INDEX orgao_sigla_idx     ON orgao (upper(sigla));

VACUUM ANALYZE;
