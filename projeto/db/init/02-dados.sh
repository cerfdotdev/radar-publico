#!/bin/sh
# Garante que os arquivos de origem existam antes da carga.
# Usa os arquivos de projeto/db/data (montado em /data) e, se faltarem, baixa do dados.gov.br.
set -eu

BASE="${DADOS_BASE_URL:-https://repositorio.dados.gov.br/segrt}"
ATIVOS="CARREIRA_082026.txt"
APOSENTADOS="APOSENTADOS_052026_FULL.csv"

# Download vai para /data quando dá para escrever (fica salvo no host); senão, para o volume do banco.
DEST=/data
if ! touch "$DEST/.escrita" 2>/dev/null; then
    DEST=/var/lib/postgresql/dados
    mkdir -p "$DEST"
fi
rm -f "$DEST/.escrita"

# Imprime o caminho do arquivo, baixando-o se necessário.
garantir() {
    arquivo="$1"; url="$2"
    if [ -s "/data/$arquivo" ]; then
        echo "dados: usando /data/$arquivo" >&2
        echo "/data/$arquivo"
        return
    fi
    for tentativa in 1 2 3 4 5 6; do
        echo "dados: baixando $arquivo (tentativa $tentativa)" >&2
        if wget -q -O "$DEST/$arquivo.part" "$url"; then
            mv "$DEST/$arquivo.part" "$DEST/$arquivo"
            echo "$DEST/$arquivo"
            return
        fi
        sleep $((tentativa * 5))
    done
    echo "dados: falha ao baixar $url. Rode scripts/baixar_dados.sh no host e suba de novo." >&2
    exit 1
}

ativos=$(garantir "$ATIVOS" "$BASE/Cargos%20e%20Carreiras/2026/$ATIVOS")
aposentados=$(garantir "$APOSENTADOS" "$BASE/Aposentados/2026/$APOSENTADOS")

# Caminhos lidos pelo 03-carga.sql
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -q \
    -v ativos="$ativos" -v aposentados="$aposentados" <<'EOF'
CREATE TABLE _arquivos (nome text PRIMARY KEY, caminho text NOT NULL);
INSERT INTO _arquivos VALUES ('ativos', :'ativos'), ('aposentados', :'aposentados');
EOF
