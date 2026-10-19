-- Modelo do banco do Radar Público. Descrição dos campos de origem em docs/dados.md.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE orgao (
    id    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome  text NOT NULL UNIQUE,
    sigla text
);

CREATE TABLE cargo (
    id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome text NOT NULL UNIQUE
);

-- Cada linha é um vínculo (ativo ou aposentado) de uma pessoa com um órgão.
CREATE TABLE servidor (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome               text NOT NULL,
    situacao           text NOT NULL CHECK (situacao IN ('ativo', 'aposentado')),
    cargo_id           integer REFERENCES cargo (id),
    orgao_id           integer NOT NULL REFERENCES orgao (id),
    uf                 char(2) CHECK (uf ~ '^[A-Z]{2}$'),  -- só ativos têm UF na fonte
    valor              numeric(14, 2),                      -- remuneração ou valor da aposentadoria
    codigo_carreira    text,                                -- só ativos
    tipo_aposentadoria text,                                -- só aposentados (daqui para baixo)
    fundamento_legal   text,
    portaria           text,
    data_aposentadoria date,
    forma_ingresso     text,
    data_ingresso      date,
    referencia         text NOT NULL                        -- mês de referência do arquivo, AAAA-MM
);

COMMENT ON TABLE servidor IS 'Vínculos de servidores ativos (CARREIRA) e aposentados (APOSENTADOS) do Executivo Federal';
