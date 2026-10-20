FROM node:26.11.1-alpine3.24@sha256:143494b1da2945f061539253adc65e4f1569ddf07da2d384c022c791a9d90a4a AS builder

WORKDIR /app

COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:378d0c32f6562f7fd9629170797f57d2b953aa09be983b3daaf4809bb039ca00

# CVEs altas com correção já publicada no Alpine 3.24, mas ainda não na imagem base
# (Grype, out/2026). Remover quando a base trouxer estas versões.
USER root
RUN apk add --no-cache libexpat=2.9.0-r0 zlib=1.3.2-r1 libx11=1.8.14-r0

# Arquivos pertencem ao root: o usuário do nginx só lê.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
# Na subida, o entrypoint da imagem gera /etc/nginx/conf.d/api-cache.conf a partir deste
# template, trocando só as variáveis API_CACHE_* (NGINX_ENVSUBST_FILTER).
COPY api-cache.conf.template /etc/nginx/templates/api-cache.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html

# Vazio = cache ligado, como no backend; o docker-compose.yml repassa o valor do .env.
ENV API_CACHE_TTL_S="" \
    NGINX_ENVSUBST_FILTER="^API_CACHE_"

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]

CMD ["nginx", "-g", "daemon off;"]
