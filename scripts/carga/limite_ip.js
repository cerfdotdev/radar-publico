// Cenário 3: um cliente sozinho martelando com o limite por IP ligado (padrão 60 a cada 60 s).
// Fases: a mesma URL repetida (o nginx responde do cache e não conta), URLs distintas (cada uma
// vai ao backend e conta) e, já limitado, uma URL em cache e o /api/health.
// Uso: scripts/carga/rodar.sh limite-ip (com RATE_LIMIT_REQUESTS e API_CACHE_TTL_S padrão).
import http from 'k6/http';
import { ALVO, TIMEOUT_REQUISICAO, busca } from './consultas.js';

const REPETICOES_MESMA_URL = 150;
const URLS_DISTINTAS = 250;
const UF_DISTINTAS = 'SP';
const URL_REPETIDA = busca({ uf: 'AC' });

export const options = {
  scenarios: { limite: { executor: 'per-vu-iterations', vus: 1, iterations: 1, maxDuration: '5m' } },
};

function get(caminhoUrl) {
  return http.get(`${ALVO}${caminhoUrl}`, { timeout: TIMEOUT_REQUISICAO });
}

function contar(contagem, res) {
  const chave = `${res.status} ${res.headers['X-Cache-Status'] || '-'}`;
  contagem[chave] = (contagem[chave] || 0) + 1;
}

export default function () {
  const mesma = {};
  for (let i = 0; i < REPETICOES_MESMA_URL; i += 1) contar(mesma, get(URL_REPETIDA));
  console.log(`MESMA_URL ${REPETICOES_MESMA_URL} pedidos: ${JSON.stringify(mesma)}`);

  const distintas = {};
  let primeiro429 = null;
  const health = {};
  for (let pagina = 1; pagina <= URLS_DISTINTAS; pagina += 1) {
    const res = get(busca({ uf: UF_DISTINTAS, page: pagina }));
    contar(distintas, res);
    if (res.status === 429 && primeiro429 === null) {
      primeiro429 = pagina;
      console.log(`PRIMEIRO_429 na URL distinta ${pagina}; Retry-After=${res.headers['Retry-After']}; corpo=${res.body}`);
    }
    contar(health, get('/health'));
  }
  console.log(`URLS_DISTINTAS ${URLS_DISTINTAS} pedidos: ${JSON.stringify(distintas)}`);
  console.log(`HEALTH intercalado: ${JSON.stringify(health)}`);

  const depois = {};
  contar(depois, get(URL_REPETIDA));
  contar(depois, get(busca({ uf: UF_DISTINTAS, page: 1 })));
  contar(depois, get(busca({ uf: 'TO' })));
  console.log(`JA_LIMITADO url_repetida/pagina_1_ja_pedida/url_nova: ${JSON.stringify(depois)}`);
}
