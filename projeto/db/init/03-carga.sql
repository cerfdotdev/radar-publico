-- Carga dos arquivos de origem. Formato e armadilhas documentados em docs/dados.md.
\set ON_ERROR_STOP on
\timing on

-- '1.234,56' -> 1234.56
CREATE FUNCTION pg_temp.valor(t text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT nullif(replace(replace(trim(t), '.', ''), ',', '.'), '')::numeric
$$;

-- 'DDMMYYYY' -> date; vazio ou data impossível -> NULL
-- Nomes, cargos e órgãos como a API compara: maiúsculas, sem acento, espaços simples.
-- (A fonte é quase toda assim, mas há exceções, como um cargo com "Ã" e 28 nomes com
-- espaço duplo; a API normaliza a entrada do usuário do mesmo jeito.)
CREATE FUNCTION pg_temp.texto(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT upper(translate(regexp_replace(trim(t), '\s+', ' ', 'g'),
                           'áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ',
                           'aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN'))
$$;

CREATE FUNCTION pg_temp.data(t text) RETURNS date
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF trim(t) !~ '^\d{8}$' THEN
        RETURN NULL;
    END IF;
    RETURN make_date(substr(trim(t), 5, 4)::int, substr(trim(t), 3, 2)::int, substr(trim(t), 1, 2)::int);
EXCEPTION WHEN others THEN
    RETURN NULL;
END
$$;

-- Cada linha do arquivo entra inteira em uma coluna. Delimitador e aspas são bytes que não
-- aparecem nos arquivos, para que ';' e '"' dentro dos valores não quebrem a importação.
CREATE TEMP TABLE linha_ativo (linha text);
CREATE TEMP TABLE linha_aposentado (linha text);

DO $$
BEGIN
    EXECUTE format($f$COPY linha_ativo FROM %L WITH (FORMAT csv, DELIMITER E'\x01', QUOTE E'\x02', ENCODING 'LATIN1')$f$,
                   (SELECT caminho FROM _arquivos WHERE nome = 'ativos'));
    EXECUTE format($f$COPY linha_aposentado FROM %L WITH (FORMAT csv, DELIMITER E'\x01', QUOTE E'\x02', ENCODING 'LATIN1')$f$,
                   (SELECT caminho FROM _arquivos WHERE nome = 'aposentados'));
END
$$;

-- Ativos: descarta título, cabeçalho e linhas de total (CPF vazio).
CREATE TEMP TABLE ativo AS
SELECT pg_temp.texto(a[1]) AS nome, trim(a[3]) AS codigo_carreira, pg_temp.texto(a[4]) AS cargo,
       trim(a[5]) AS uf, pg_temp.texto(a[6]) AS orgao, pg_temp.valor(a[8]) AS valor
FROM (SELECT string_to_array(linha, ';') AS a FROM linha_ativo) s
WHERE cardinality(a) >= 8 AND trim(a[2]) <> '' AND trim(a[1]) <> 'Nome';

-- Aposentados: os 13 primeiros e os 4 últimos campos são fixos; o que sobra no meio é a
-- portaria, que em 123 linhas contém ';'.
CREATE TEMP TABLE aposentado AS
SELECT pg_temp.texto(a[1]) AS nome, pg_temp.texto(a[4]) AS orgao, nullif(trim(a[5]), '') AS sigla,
       nullif(pg_temp.texto(a[7]), '') AS cargo, nullif(trim(a[12]), '') AS tipo_aposentadoria,
       nullif(trim(a[13]), '') AS fundamento_legal,
       nullif(trim(array_to_string(a[14:n - 4], ';')), '') AS portaria,
       pg_temp.data(a[n - 3]) AS data_aposentadoria, nullif(trim(a[n - 2]), '') AS forma_ingresso,
       pg_temp.data(a[n - 1]) AS data_ingresso, pg_temp.valor(a[n]) AS valor
FROM (SELECT a, cardinality(a) AS n FROM (SELECT string_to_array(linha, ';') AS a FROM linha_aposentado) x) s
WHERE n >= 18 AND trim(a[1]) <> 'Nome';

INSERT INTO orgao (nome, sigla)
SELECT nome, max(sigla)
FROM (SELECT orgao AS nome, NULL AS sigla FROM ativo UNION ALL SELECT orgao, sigla FROM aposentado) o
GROUP BY nome;

INSERT INTO cargo (nome)
SELECT cargo FROM ativo UNION SELECT cargo FROM aposentado WHERE cargo IS NOT NULL;

INSERT INTO servidor (nome, situacao, cargo_id, orgao_id, uf, valor, codigo_carreira, referencia)
SELECT a.nome, 'ativo', c.id, o.id, a.uf, a.valor, a.codigo_carreira, '2026-08'
FROM ativo a JOIN orgao o ON o.nome = a.orgao JOIN cargo c ON c.nome = a.cargo;

INSERT INTO servidor (nome, situacao, cargo_id, orgao_id, valor, tipo_aposentadoria, fundamento_legal,
                      portaria, data_aposentadoria, forma_ingresso, data_ingresso, referencia)
SELECT a.nome, 'aposentado', c.id, o.id, a.valor, a.tipo_aposentadoria, a.fundamento_legal,
       a.portaria, a.data_aposentadoria, a.forma_ingresso, a.data_ingresso, '2026-05'
FROM aposentado a JOIN orgao o ON o.nome = a.orgao LEFT JOIN cargo c ON c.nome = a.cargo;

-- Resumo da carga, conferido contra as contagens de docs/dados.md
SELECT situacao, count(*) FROM servidor GROUP BY situacao ORDER BY situacao;

DROP TABLE _arquivos;
