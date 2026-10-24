FROM node:26.11.1-alpine3.24@sha256:143494b1da2945f061539253adc65e4f1569ddf07da2d384c022c791a9d90a4a AS builder

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:378d0c32f6562f7fd9629170797f57d2b953aa09be983b3daaf4809bb039ca00

# Processos do nginx. O "auto" da imagem conta os núcleos da máquina, não o limite de CPU do
# container (FRONTEND_CPUS no docker-compose.yml, padrão 1): num servidor de 32 núcleos seriam
# 32 processos. 2 dão conta de um núcleo, com um processo livre se o outro estiver ocupado.
ARG NGINX_WORKER_PROCESSES=2

# CVEs altas com correção já publicada no Alpine 3.24, mas ainda não na imagem base
# (Grype, out/2026). Remover quando a base trouxer estas versões.
USER root
# A configuração do site vem do template (nginx.conf), gerada na subida; o default.conf da
# imagem sai. O grep falha o build se a linha do worker_processes mudar de formato na base.
RUN apk add --no-cache libexpat=2.9.0-r0 zlib=1.3.2-r1 libx11=1.8.14-r0 \
    && rm /etc/nginx/conf.d/default.conf \
    && sed -i "s/^worker_processes .*/worker_processes ${NGINX_WORKER_PROCESSES};/" /etc/nginx/nginx.conf \
    && grep -qx "worker_processes ${NGINX_WORKER_PROCESSES};" /etc/nginx/nginx.conf

# Arquivos pertencem ao root: o usuário do nginx só lê. Na subida, o entrypoint da imagem gera
# /etc/nginx/conf.d/*.conf a partir dos templates, trocando só as variáveis do filtro
# (NGINX_ENVSUBST_FILTER): o site e as duas camadas do proxy (nginx.conf), o cache da API, o
# IP real atrás do Traefik e as zonas dos limites da borda.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY api-cache.conf.template real-ip.conf.template limites-borda.conf.template /etc/nginx/templates/
COPY security-headers.conf erro-json.conf api-borda.conf api-admissao.conf /etc/nginx/snippets/
# Padrões e validação dos limites da borda, carregados pelo entrypoint antes dos templates, e o
# cache da API esvaziado a cada subida.
COPY --chmod=755 limites-borda.envsh /docker-entrypoint.d/18-limites-borda.envsh
COPY --chmod=755 limpar-cache.sh /docker-entrypoint.d/19-limpar-cache.sh
COPY --from=builder /app/dist /usr/share/nginx/html

# Vazio = cache ligado, como no backend; o docker-compose.yml repassa o valor do .env. Os
# padrões das variáveis NGINX_LIMITE_* ficam em limites-borda.envsh.
ENV API_CACHE_TTL_S="" \
    NGINX_PROXY_CONFIAVEL="127.0.0.1/32" \
    NGINX_ENVSUBST_FILTER="^(API_CACHE_|NGINX_PROXY_|NGINX_LIMITE_)"

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]

CMD ["nginx", "-g", "daemon off;"]
