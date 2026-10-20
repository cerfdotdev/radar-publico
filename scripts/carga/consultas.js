// Módulo comum dos cenários de carga (docs/carga.md): consultas, requisição com tags e resumo.
import http from 'k6/http';
import { Counter } from 'k6/metrics';

// Base da API; padrão: pelo nginx do frontend, a entrada pública.
export const ALVO = __ENV.ALVO || 'http://localhost:8080/api';
// O mesmo tempo que o site espera por uma busca (SEARCH_TIMEOUT_MS). Estourou: status 0 no k6.
export const TIMEOUT_REQUISICAO = '20s';
// Status que aparecem na tabela de cada tipo de consulta (0 = tempo do k6 esgotado).
export const STATUS = ['200', '304', '400', '404', '429', '500', '502', '503', '504', '0'];
export const ESTADOS_CACHE = ['HIT', 'MISS', 'EXPIRED', 'REVALIDATED', 'UPDATING', 'STALE', 'NENHUM'];
export const ESTATISTICAS = ['avg', 'med', 'p(95)', 'p(99)', 'max'];

// Páginas: com per_page 20 a busca vai até a página 500 (10.000 resultados).
const PER_PAGE_PADRAO = 20;
const PAGINA_RASA_MAX = 10;
const PAGINA_FUNDA_MIN = 100;
const PAGINA_FUNDA_MAX = 500;
const LIMIT_SIMILAR = 100;
const LIMIT_SIMILAR_FILTRO = 20;
// Metade das buscas parecidas com filtro usa UF; a outra metade, cargo.
const CHANCE_FILTRO_UF = 0.5;
// Quantos ids cada VU guarda das respostas para pedir o detalhe depois.
const IDS_GUARDADOS = 200;

const UFS = ['AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'];
const UFS_GRANDES = ['SP', 'RJ', 'DF', 'MG', 'RS', 'PR', 'BA'];
const CARGOS = ['professor', 'analista', 'tecnico', 'agente', 'auditor', 'enfermeiro', 'medico',
  'policial', 'engenheiro', 'assistente', 'administrador', 'contador', 'pesquisador'];
const CARGOS_AMPLOS = ['professor', 'analista', 'tecnico', 'agente', 'assistente'];
const ORGAOS = ['INSS', 'saude', 'educacao', 'fazenda', 'universidade', 'IBAMA', 'ministerio',
  'instituto', 'fundacao', 'agricultura', 'defesa', 'justica'];
// Nomes genéricos que a documentação já usa; o resto é padrão de sobrenome comum.
const NOMES = ['MARIA DA SILVA', 'JOSE CARLOS DA SILVA'];
const PADROES = ['%MARIA%SILVA%', '%JOSE%SILVA%', '"%MARIA%DA%SILVA%"', '%MARIA%', '%JOSE%',
  '%SILVA%', '%SANTOS%', '%SOUZA%', '%OLIVEIRA%', '%PEREIRA%', '%COSTA%', '%FERREIRA%'];
// Padrões caros: pedaços de uma letra não geram trigramas e a busca lê e compara muito mais.
export const PADROES_PESADOS = ['%A%A%A%', '%A%E%I%', '%A%E%O%', '%E%A%O%', '%MAR%', '%ARI%',
  '%ANA%', '%MARIA%'];

// Mistura realista: tipo de consulta e peso (soma 100).
export const MISTURA = [
  ['cargo', 20], ['uf', 15], ['orgao', 15], ['nome_cargo_uf', 10], ['similar', 15],
  ['similar_filtro', 10], ['pagina_funda', 10], ['detalhe', 5],
];
export const TIPOS_MISTURA = MISTURA.map(([tipo]) => tipo);

const respostasCache = new Counter('respostas_cache');
const idsVistos = [];

export function sortear(lista) {
  return lista[Math.floor(Math.random() * lista.length)];
}

function inteiro(minimo, maximo) {
  return minimo + Math.floor(Math.random() * (maximo - minimo + 1));
}

function query(params) {
  return Object.entries(params)
    .map(([chave, valor]) => `${chave}=${encodeURIComponent(valor)}`)
    .join('&');
}

export function busca(params) {
  return `/servidores?${query(params)}`;
}

function sortearTipo() {
  let sorteio = Math.random() * 100;
  for (const [tipo, peso] of MISTURA) {
    sorteio -= peso;
    if (sorteio < 0) return tipo;
  }
  return MISTURA[0][0];
}

// Caminho da consulta de cada tipo, com valores sorteados.
export function caminho(tipo) {
  switch (tipo) {
    case 'cargo': return busca({ cargo: sortear(CARGOS), page: inteiro(1, PAGINA_RASA_MAX) });
    case 'uf': return busca({ uf: sortear(UFS) });
    case 'orgao': return busca({ orgao: sortear(ORGAOS) });
    case 'nome_cargo_uf':
      return busca({ nome: sortear(NOMES), cargo: sortear(CARGOS), uf: sortear(UFS_GRANDES) });
    case 'similar': return busca({ similar: sortear(PADROES), limit: LIMIT_SIMILAR });
    case 'similar_filtro':
      return Math.random() < CHANCE_FILTRO_UF
        ? busca({ similar: sortear(PADROES), uf: sortear(UFS), limit: LIMIT_SIMILAR_FILTRO })
        : busca({ similar: sortear(PADROES), cargo: sortear(CARGOS), limit: LIMIT_SIMILAR_FILTRO });
    case 'pagina_funda':
      return busca({ uf: sortear(UFS_GRANDES), page: inteiro(PAGINA_FUNDA_MIN, PAGINA_FUNDA_MAX),
        per_page: PER_PAGE_PADRAO });
    case 'detalhe': return `/servidores/${sortear(idsVistos)}`;
    default: throw new Error(`tipo desconhecido: ${tipo}`);
  }
}

// GET com o tipo como tag (e como nome, para não abrir uma série por URL).
export function requisitar(tipo, caminhoUrl, tagsExtras = {}) {
  const tags = { tipo, name: tipo, ...tagsExtras };
  const res = http.get(`${ALVO}${caminhoUrl}`, { tags, timeout: TIMEOUT_REQUISICAO });
  respostasCache.add(1, { cache: res.headers['X-Cache-Status'] || 'NENHUM' });
  if (res.status === 200 && idsVistos.length < IDS_GUARDADOS && caminhoUrl.startsWith('/servidores?')) {
    const corpo = res.json();
    for (const item of corpo.data.slice(0, 3)) idsVistos.push(item.id);
  }
  return res;
}

// Uma consulta da mistura; o detalhe só entra depois de alguma busca ter devolvido ids.
export function consultaDaMistura() {
  let tipo = sortearTipo();
  if (tipo === 'detalhe' && idsVistos.length === 0) tipo = 'cargo';
  return requisitar(tipo, caminho(tipo));
}

// Limites que nunca falham: só existem para o k6 guardar as submétricas por tipo e status.
export function limitesPorTipo(tipos) {
  const limites = { http_req_duration: ['max>=0'], http_reqs: ['count>=0'] };
  for (const tipo of tipos) {
    limites[`http_req_duration{tipo:${tipo}}`] = ['max>=0'];
    for (const status of STATUS) limites[`http_reqs{tipo:${tipo},status:${status}}`] = ['count>=0'];
  }
  for (const estado of ESTADOS_CACHE) limites[`respostas_cache{cache:${estado}}`] = ['count>=0'];
  return limites;
}

function ms(valor) {
  return valor === undefined ? null : Math.round(valor * 10) / 10;
}

function contagem(metricas, nome) {
  const metrica = metricas[nome];
  return metrica ? metrica.values.count : 0;
}

// Resumo compacto (JSON e tabela de texto) do que vai para docs/carga.md.
export function resumir(data, tipos) {
  const m = data.metrics;
  const duracaoS = data.state.testRunDurationMs / 1000;
  const linha = (tipo, duracao, filtro) => {
    const valores = duracao ? duracao.values : {};
    const status = {};
    for (const s of STATUS) {
      const n = contagem(m, `http_reqs{${filtro}status:${s}}`);
      if (n > 0) status[s] = n;
    }
    const total = Object.values(status).reduce((a, b) => a + b, 0);
    return { tipo, requisicoes: total, rps: Math.round((total / duracaoS) * 10) / 10,
      media_ms: ms(valores.avg), p50_ms: ms(valores.med), p95_ms: ms(valores['p(95)']),
      p99_ms: ms(valores['p(99)']), max_ms: ms(valores.max), status };
  };
  const porTipo = tipos.map((t) => linha(t, m[`http_req_duration{tipo:${t}}`], `tipo:${t},`));
  const cache = {};
  for (const estado of ESTADOS_CACHE) {
    const n = contagem(m, `respostas_cache{cache:${estado}}`);
    if (n > 0) cache[estado] = n;
  }
  const total = m.http_req_duration.values;
  const resultado = {
    cenario: __ENV.NOME || 'sem-nome', alvo: ALVO, duracao_s: Math.round(duracaoS),
    vus_max: m.vus_max ? m.vus_max.values.max : null,
    total: { requisicoes: m.http_reqs.values.count, rps: Math.round(m.http_reqs.values.rate * 10) / 10,
      media_ms: ms(total.avg), p50_ms: ms(total.med), p95_ms: ms(total['p(95)']),
      p99_ms: ms(total['p(99)']), max_ms: ms(total.max) },
    por_tipo: porTipo, cache,
  };
  const texto = [`# ${resultado.cenario} (${ALVO}, ${resultado.duracao_s} s)`,
    `total: ${resultado.total.requisicoes} req, ${resultado.total.rps} req/s, p50 ${resultado.total.p50_ms} ms, `
      + `p95 ${resultado.total.p95_ms} ms, p99 ${resultado.total.p99_ms} ms, max ${resultado.total.max_ms} ms`,
    `cache: ${JSON.stringify(cache)}`,
    ...porTipo.map((l) => `${l.tipo}: ${l.requisicoes} req, p50 ${l.p50_ms}, p95 ${l.p95_ms}, `
      + `p99 ${l.p99_ms}, max ${l.max_ms} ms, status ${JSON.stringify(l.status)}`)].join('\n');
  const saida = { stdout: `${texto}\n` };
  if (__ENV.RESULTADO) saida[__ENV.RESULTADO] = `${JSON.stringify(resultado, null, 2)}\n`;
  return saida;
}
