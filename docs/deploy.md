# Deploy no Dokploy

O mesmo `projeto/docker-compose.yml` roda no [Dokploy](https://dokploy.com), atrás do Traefik dele, com HTTPS. O deploy contínuo é o job `deploy` do CI ([`ci.yml`](../.github/workflows/ci.yml)): a cada push na `main` com o `ci-ok` verde, ele pede ao Dokploy um novo deploy do compose. A chave da API do Dokploy fica só nos segredos do GitHub.

## 1. Criar o serviço no Dokploy

1. **Projects → Create Project** (ex.: "Radar Público") → **Create Service → Compose**.
2. Em **General**, fonte **Git** (ou **GitHub**, se o app do GitHub estiver instalado):
   - repositório `https://github.com/cerfdotdev/radar-publico.git`, branch `main`;
   - **Compose Path**: `./projeto/docker-compose.yml`.
3. Deixe o **Autodeploy** do Dokploy desligado: quem dispara o deploy é o CI, só depois dos testes.

## 2. Variáveis de ambiente

Na aba **Environment** do serviço (o Dokploy grava num `.env` que o compose lê):

```bash
POSTGRES_PASSWORD=<senha forte>
POSTGRES_API_PASSWORD=<outra senha forte>
# O Traefik fala com o frontend pela rede do Docker; as portas do host ficam só locais.
WEB_BIND_ADDRESS=127.0.0.1
WEB_PORT=18080
API_PORT=15000
# Rede do Traefik do Dokploy: o X-Forwarded-For que ele manda vale como IP do cliente,
# senão todos os visitantes dividem o mesmo limite por IP.
NGINX_PROXY_CONFIAVEL=10.0.0.0/8
```

As demais variáveis (limites, cache) estão no [README](../README.md#limites-e-ajuste-por-máquina) e em [`.env.example`](../projeto/.env.example). Vazias, usam o padrão do código.

`WEB_PORT` e `API_PORT` só precisam ser portas livres no servidor. `NGINX_PROXY_CONFIAVEL` deve cobrir o IP com que o Traefik chega ao frontend; a rede `dokploy-network` do Dokploy usa a faixa `10.0.0.0/8` por padrão (confira com `docker network inspect dokploy-network`).

## 3. Domínio

Na aba **Domains**: serviço `frontend`, porta `8080`, o host (ex.: `radar.seudominio`), **HTTPS** ligado com Let's Encrypt. Crie o registro DNS `A` do host apontando para o servidor. O site fica em `https://<host>/` e a API em `https://<host>/api/`; a porta 5000 do backend não é publicada.

## 4. Primeiro deploy

Clique em **Deploy**. Na primeira subida, o `db-server` baixa os arquivos do dados.gov.br e carrega o banco; o healthcheck espera até 20 minutos, e o backend só sobe depois disso. Acompanhe pelos logs do serviço. O volume do banco fica entre os deploys; para recarregar os dados, apague o volume no Dokploy e faça um novo deploy.

## 5. Deploy contínuo pelo GitHub

1. No Dokploy, gere uma chave em **Settings → Profile → API/CLI**.
2. No GitHub, **Settings → Environments → New environment** `producao` (pode exigir aprovação de um revisor antes de cada deploy, se quiser).
3. No ambiente `producao`:
   - secret `DOKPLOY_API_KEY`: a chave do passo 1;
   - variável `DOKPLOY_URL`: o endereço do painel do Dokploy (ex.: `https://dokploy.seudominio`);
   - variável `DOKPLOY_COMPOSE_ID`: o id do serviço, que aparece no endereço da página dele no Dokploy.

Sem `DOKPLOY_COMPOSE_ID`, o job `deploy` não roda. Com ela, cada merge na `main` com o CI verde chama `POST /api/compose.deploy`.

## 6. Conferir

```bash
curl -s https://<host>/api/health
curl -s "https://<host>/api/servidores?uf=DF&per_page=1"
```

Para ver se o limite por IP enxerga o cliente certo, faça mais de `RATE_LIMIT_REQUESTS` buscas diferentes em um minuto a partir de uma máquina: ela recebe 429, e outra máquina continua buscando.
