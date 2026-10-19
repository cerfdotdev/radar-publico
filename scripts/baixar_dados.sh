#!/usr/bin/env bash
# Baixa os arquivos de origem para projeto/db/data antes do primeiro `docker compose up`.
# Opcional: o container do banco baixa sozinho se os arquivos faltarem, mas pela rede do host
# o download costuma ser mais confiável (o DNS do dados.gov.br falha às vezes dentro do Docker).
set -euo pipefail

BASE="https://repositorio.dados.gov.br/segrt"
DEST="$(cd "$(dirname "$0")/.." && pwd)/projeto/db/data"

baixar() {
    local arquivo="$1" url="$2"
    if [ -s "$DEST/$arquivo" ]; then
        echo "já existe: $arquivo"
        return
    fi
    echo "baixando $arquivo..."
    curl -fL --retry 5 --retry-delay 5 --retry-all-errors -o "$DEST/$arquivo.part" "$url"
    mv "$DEST/$arquivo.part" "$DEST/$arquivo"
}

baixar CARREIRA_082026.txt "$BASE/Cargos%20e%20Carreiras/2026/CARREIRA_082026.txt"
baixar APOSENTADOS_052026_FULL.csv "$BASE/Aposentados/2026/APOSENTADOS_052026_FULL.csv"
ls -lh "$DEST"
