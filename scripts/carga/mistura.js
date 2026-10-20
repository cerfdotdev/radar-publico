// Cenário 1: mistura realista de consultas, sem pausa (cada VU é uma requisição em andamento).
// Uso: scripts/carga/rodar.sh mistura (VUS e DURACAO pelo ambiente).
import { consultaDaMistura, limitesPorTipo, resumir, ESTATISTICAS, TIPOS_MISTURA } from './consultas.js';

const VUS = Number(__ENV.VUS || 50);
const SUBIDA = __ENV.SUBIDA || '10s';
const DURACAO = __ENV.DURACAO || '60s';
const DESCIDA = '5s';

export const options = {
  scenarios: {
    mistura: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: SUBIDA, target: VUS },
        { duration: DURACAO, target: VUS },
        { duration: DESCIDA, target: 0 },
      ],
    },
  },
  thresholds: limitesPorTipo(TIPOS_MISTURA),
  summaryTrendStats: ESTATISTICAS,
};

export default function () {
  consultaDaMistura();
}

export function handleSummary(data) {
  return resumir(data, TIPOS_MISTURA);
}
