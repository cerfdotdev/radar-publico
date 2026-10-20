-- Cenário 4: plano e tempo do SQL de `similar` (SIMILAR_QUERY em app/routes/servidores.py) nos
-- dados reais, com e sem filtros. Só leitura. Rode como o usuário radar, sem statement_timeout,
-- para ver o tempo inteiro e comparar com os 5 s de DB_STATEMENT_TIMEOUT_S:
--   docker compose -p projeto exec -T db-server psql -U radar -d radar < scripts/carga/explain_similar.sql
\pset pager off
SET statement_timeout = '60s';
\set similar 'SELECT s.id, s.nome, s.situacao, c.nome AS cargo, o.nome AS orgao, o.sigla AS sigla_orgao, s.uf, s.valor, similarity(s.nome, :pad) AS similaridade FROM servidor s JOIN orgao o ON o.id = s.orgao_id LEFT JOIN cargo c ON c.id = s.cargo_id WHERE '

\echo '== %JOSE%SILVA%, limit 100'
\set pad '''%JOSE%SILVA%'''
EXPLAIN (ANALYZE, BUFFERS) :similar s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %JOSE%SILVA% + uf=RJ, limit 100'
EXPLAIN (ANALYZE, BUFFERS) :similar s.uf = 'RJ' AND s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %MARIA%, limit 100'
\set pad '''%MARIA%'''
EXPLAIN (ANALYZE, BUFFERS) :similar s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %MARIA% + cargo contém PROFESSOR (ids resolvidos como a API), limit 100'
EXPLAIN (ANALYZE, BUFFERS) :similar s.cargo_id = ANY(ARRAY(SELECT id FROM cargo WHERE nome LIKE '%PROFESSOR%')) AND s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %ANA% (3 letras), limit 100'
\set pad '''%ANA%'''
EXPLAIN (ANALYZE, BUFFERS) :similar s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %ANA% + uf=SP, limit 100'
EXPLAIN (ANALYZE, BUFFERS) :similar s.uf = 'SP' AND s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
\echo '== %A%A%A% (nenhum trigrama), limit 100'
\set pad '''%A%A%A%'''
EXPLAIN (ANALYZE, BUFFERS) :similar s.nome LIKE :pad ORDER BY similaridade DESC, s.nome, s.id LIMIT 100;
