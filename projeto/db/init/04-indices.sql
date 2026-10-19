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

-- Estatísticas mais detalhadas para cargo e órgão: com o padrão, um órgão ou cargo raro
-- (1 a 20 vínculos) é estimado em ~1.000 linhas e o planejador percorre o índice de nome
-- inteiro (1,5 a 2 s por consulta). Com mais amostras a estimativa fica certa (< 1 ms).
ALTER TABLE servidor ALTER COLUMN orgao_id SET STATISTICS 1000;
ALTER TABLE servidor ALTER COLUMN cargo_id SET STATISTICS 3000;

VACUUM ANALYZE;
