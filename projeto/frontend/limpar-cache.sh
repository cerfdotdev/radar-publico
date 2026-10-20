#!/bin/sh
# Esvazia o cache da API a cada subida do container (restart, recriação, deploy), antes de o
# nginx começar. O cache fica num volume (docker-compose.yml), que sobrevive aos deploys: sem
# isto, uma resposta guardada por uma versão antiga do backend continuaria sendo servida,
# renovada pelo 304 do ETag, que só muda com os dados. O nginx recria o diretório ao subir.
# O caminho é o de proxy_cache_path em nginx.conf.
set -eu

CACHE_API=/var/cache/nginx/api

rm -rf "$CACHE_API"
echo "limpar-cache.sh: cache da API esvaziado ($CACHE_API)"
