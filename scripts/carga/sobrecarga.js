// Cenário 2: sobrecarga com consultas pesadas, muito acima de workers × threads (8), e sondas
// leves (health e uma busca simples) antes, durante e depois, para medir espera e recuperação.
// Uso: scripts/carga/rodar.sh sobrecarga (VUS e DURACAO pelo ambiente).
import exec from 'k6/execution';
import { busca, caminho, limitesPorTipo, requisitar, resumir, sortear, ESTATISTICAS,
  PADROES_PESADOS } from './consultas.js';

const VUS = Number(__ENV.VUS || 300);
const ANTES_S = 15;
const SUBIDA_S = 5;
const DURACAO_S = Number(__ENV.DURACAO_S || 60);
const DEPOIS_S = 45;
const SONDAS_POR_S = 2;
const VUS_SONDA = 20;
const LIMIT_PESADO = 100;
const PER_PAGE_FUNDA = 100;
const PAGINA_FUNDA_MIN = 50;
const PAGINA_FUNDA_MAX = 100;
const CARGOS_AMPLOS = ['de', 'ar', 'professor', 'tecnico'];
// Fim da carga pesada, em segundos desde o início do teste.
const FIM_CARGA_S = ANTES_S + SUBIDA_S + DURACAO_S;
// Metade da carga é similar caro; a outra, página funda de cargo amplo.
const CHANCE_SIMILAR = 0.5;
const TIPOS = ['pesada_similar', 'pesada_pagina', 'sonda_health', 'sonda_busca'];

export const options = {
  scenarios: {
    pesada: {
      executor: 'ramping-vus',
      exec: 'pesada',
      startTime: `${ANTES_S}s`,
      startVUs: 0,
      stages: [
        { duration: `${SUBIDA_S}s`, target: VUS },
        { duration: `${DURACAO_S}s`, target: VUS },
      ],
      // A carga para de uma vez: o k6 abandona as requisições em andamento.
      gracefulRampDown: '0s',
      gracefulStop: '0s',
    },
    sonda: {
      executor: 'constant-arrival-rate',
      exec: 'sonda',
      rate: SONDAS_POR_S,
      timeUnit: '1s',
      duration: `${FIM_CARGA_S + DEPOIS_S}s`,
      preAllocatedVUs: VUS_SONDA,
    },
  },
  thresholds: (() => {
    const limites = limitesPorTipo(TIPOS);
    for (const fase of ['antes', 'durante', 'depois']) {
      for (const tipo of ['sonda_health', 'sonda_busca']) {
        limites[`http_req_duration{tipo:${tipo},fase:${fase}}`] = ['max>=0'];
      }
    }
    return limites;
  })(),
  summaryTrendStats: ESTATISTICAS,
};

function faseAtual() {
  const decorridoS = exec.instance.currentTestRunDuration / 1000;
  if (decorridoS < ANTES_S) return 'antes';
  return decorridoS < FIM_CARGA_S ? 'durante' : 'depois';
}

export function pesada() {
  if (Math.random() < CHANCE_SIMILAR) {
    requisitar('pesada_similar', busca({ similar: sortear(PADROES_PESADOS), limit: LIMIT_PESADO }));
  } else {
    const pagina = PAGINA_FUNDA_MIN + Math.floor(Math.random() * (PAGINA_FUNDA_MAX - PAGINA_FUNDA_MIN + 1));
    requisitar('pesada_pagina', busca({ cargo: sortear(CARGOS_AMPLOS), page: pagina, per_page: PER_PAGE_FUNDA }));
  }
}

// Cada sonda vai para o log com o instante, para calcular a recuperação depois do fim da carga.
export function sonda() {
  const fase = faseAtual();
  const t = (exec.instance.currentTestRunDuration / 1000).toFixed(1);
  for (const [tipo, url] of [['sonda_health', '/health'], ['sonda_busca', caminho('uf')]]) {
    const res = requisitar(tipo, url, { fase });
    console.log(`SONDA t=${t} fim_carga=${FIM_CARGA_S} tipo=${tipo} status=${res.status} ms=${res.timings.duration.toFixed(0)}`);
  }
}

export function handleSummary(data) {
  const saida = resumir(data, TIPOS);
  const fases = [];
  for (const fase of ['antes', 'durante', 'depois']) {
    for (const tipo of ['sonda_health', 'sonda_busca']) {
      const m = data.metrics[`http_req_duration{tipo:${tipo},fase:${fase}}`];
      if (m) fases.push(`${tipo} ${fase}: p50 ${m.values.med.toFixed(0)} ms, p95 ${m.values['p(95)'].toFixed(0)} ms, max ${m.values.max.toFixed(0)} ms`);
    }
  }
  saida.stdout += `${fases.join('\n')}\n`;
  return saida;
}
