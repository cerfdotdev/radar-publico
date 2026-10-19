#!/bin/sh
# Usuário da API: só leitura, com tempo máximo por consulta e limite de conexões.
set -eu

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q \
    -v usuario="${POSTGRES_API_USER:-radar_api}" \
    -v senha="${POSTGRES_API_PASSWORD:-radar_api}" \
    -v banco="$POSTGRES_DB" \
    -v timeout="${POSTGRES_API_STATEMENT_TIMEOUT:-5s}" <<'EOF'
CREATE ROLE :"usuario" LOGIN PASSWORD :'senha' CONNECTION LIMIT 50;
ALTER ROLE :"usuario" SET statement_timeout = :'timeout';
ALTER ROLE :"usuario" SET default_transaction_read_only = on;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE :"banco" TO :"usuario";
GRANT USAGE ON SCHEMA public TO :"usuario";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"usuario";
EOF
