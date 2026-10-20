# Deploy no Dokploy

O mesmo `projeto/docker-compose.yml` roda no [Dokploy](https://dokploy.com), atrás do Traefik dele, com HTTPS. O deploy contínuo é o job `deploy` do CI ([`ci.yml`](../.github/workflows/ci.yml)): a cada push na `main` com o `ci-ok` verde, ele pede ao Dokploy um novo deploy do compose. A chave da API do Dokploy fica só nos segredos do GitHub.

## Ambiente atual

| | |
|---|---|
| Painel | <https://dokploy.hatzer.cloud>, projeto **Radar-Público**, serviço compose `radar-publico` |
| Site e API | <https://radar.dok.hatzer.cloud> e `/api/` (o DNS `*.dok.hatzer.cloud` já aponta para o servidor) |
| Endereço de teste | <http://radar-publico-147-15-59-99.traefik.me> (HTTP, sem depender de DNS) |
| Deploy contínuo | job `deploy` do CI, ambiente `producao` do GitHub |

O serviço foi criado em 20/10/2026 com as variáveis da seção 2 e senhas aleatórias do banco, guardadas só no Dokploy.

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

As demais variáveis (limites do backend e da borda, cache, memória, CPU e processos de cada container, logs) estão no [README](../README.md#limites-e-ajuste-por-máquina) e em [`.env.example`](../projeto/.env.example). Vazias, usam o padrão, pensado para este servidor: nenhuma precisa ser definida no Dokploy.

`WEB_PORT` e `API_PORT` só precisam ser portas livres no servidor. `NGINX_PROXY_CONFIAVEL` deve cobrir o IP com que o Traefik chega ao frontend; a rede `dokploy-network` do Dokploy usa a faixa `10.0.0.0/8` por padrão (confira com `docker network inspect dokploy-network`). Ela vale também para os limites por IP da borda (10 requisições por segundo e 8 simultâneas por IP, no nginx): sem ela, todos os visitantes teriam o IP do Traefik e dividiriam esses limites.

Os tetos de recursos (`*_MEM_LIMIT`, `*_CPUS`, `*_PIDS_LIMIT`) somam 2,6 GB de memória e 5 núcleos. Se o servidor tiver menos folga que isso para o Radar Público, reduza no Dokploy, começando pelo banco. Depois do primeiro deploy, confira o uso real com `docker stats` no servidor: o banco com os dados reais é o único que não foi medido aqui (o teste de sobrecarga usou a amostra).

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

Sem `DOKPLOY_COMPOSE_ID`, o job `deploy` termina com um aviso e não faz deploy. Com ela, cada merge na `main` com o CI verde chama `POST /api/compose.deploy`.

## 6. Conferir

```bash
curl -s https://<host>/api/health
curl -s "https://<host>/api/servidores?uf=DF&per_page=1"
```

Para ver se o limite por IP enxerga o cliente certo, faça mais de `RATE_LIMIT_REQUESTS` buscas diferentes em um minuto a partir de uma máquina: ela recebe 429, e outra máquina continua buscando. O limite da borda é mais rápido de conferir: 60 requisições de uma máquina, 20 de cada vez, passam da rajada de 20 e recebem algumas 429, enquanto outra máquina continua recebendo 200. Uma seguida da outra não serve: pela internet, cada uma leva perto de 0,1 s, e a borda aceita 10 por segundo.

```bash
seq 1 60 | xargs -P 20 -I{} curl -s -o /dev/null -w '%{http_code}\n' "https://<host>/api/servidores?uf=DF&per_page=1" | sort | uniq -c
curl -sI https://<host>/ | grep -i -E 'strict-transport|content-security|cross-origin'
```

O segundo comando confere os cabeçalhos de segurança, inclusive o `Strict-Transport-Security` (1 ano, `includeSubDomains`), que só vale por HTTPS. O cache do nginx fica no volume `nginx-cache` do serviço e é esvaziado a cada deploy.
