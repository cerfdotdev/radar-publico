#!/usr/bin/env bash
# Roda um cenário de carga com o k6 em Docker (imagem fixada por digest) e guarda o resumo em
# docs/carga/. Detalhes, configuração da stack e resultados em docs/carga.md.
#
# Uso: scripts/carga/rodar.sh <mistura|sobrecarga|limite-ip> <nome-do-resultado> [VAR=valor ...]
#   ex.: scripts/carga/rodar.sh mistura mistura-cache-off VUS=50 DURACAO=60s
# Variáveis: ALVO (padrão http://localhost:8080/api), VUS, DURACAO / DURACAO_S, SUBIDA.
# PROJETO_COMPOSE (padrão projeto) é o projeto do compose monitorado na sobrecarga.
set -euo pipefail

# k6 v2.3.0 (2026-09-21).
K6_IMAGEM="grafana/k6@sha256:9c2dee7f8ed74d317e4027c06a10f169b625638189de8d4555d0b3486a5aeb34"
PROJETO_COMPOSE="${PROJETO_COMPOSE:-projeto}"
INTERVALO_MONITOR_S=1

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
SAIDA="$RAIZ/docs/carga"
cenario="${1:?cenário: mistura, sobrecarga ou limite-ip}"
nome="${2:?nome do resultado}"
shift 2
script="${cenario//-/_}.js"
[ -f "$RAIZ/scripts/carga/$script" ] || { echo "cenário desconhecido: $cenario" >&2; exit 2; }

envs=(-e "NOME=$nome" -e "RESULTADO=/resultados/$nome.json")
for par in "$@"; do envs+=(-e "$par"); done

monitorar() {
  # Conexões do backend no banco (só client backend: os workers paralelos do Postgres também
  # aparecem como radar_api) e estado dos containers, a cada segundo.
  echo "t,conexoes_radar_api,ativas_radar_api,workers_paralelos,backend,load1"
  while true; do
    sql="select count(*) filter (where backend_type='client backend'),
                count(*) filter (where backend_type='client backend' and state='active'),
                count(*) filter (where backend_type='parallel worker')
         from pg_stat_activity where usename='radar_api'"
    banco=$(docker compose -p "$PROJETO_COMPOSE" exec -T db-server psql -U radar -d radar -AtF, -c "$sql" 2>/dev/null || echo "?,?,?")
    estado=$(docker inspect -f '{{.RestartCount}}/{{.State.Status}}/{{.State.Health.Status}}' "$PROJETO_COMPOSE-backend-1")
    echo "$(date +%s),$banco,$estado,$(cut -d' ' -f1 /proc/loadavg)"
    sleep "$INTERVALO_MONITOR_S"
  done
}

estado_containers() {
  for c in db-server backend frontend; do
    docker inspect -f '{{.Name}} reinicios={{.RestartCount}} estado={{.State.Status}} oom={{.State.OOMKilled}} saude={{.State.Health.Status}}' "$PROJETO_COMPOSE-$c-1"
  done
}

echo "load average antes: $(cut -d' ' -f1-3 /proc/loadavg)"
pid_monitor=""
if [ "$cenario" = sobrecarga ]; then
  estado_containers
  monitorar > "$SAIDA/$nome-monitor.csv" &
  pid_monitor=$!
fi

docker run --rm --network host --user "$(id -u):$(id -g)" \
  -v "$RAIZ/scripts/carga:/carga:ro" -v "$SAIDA:/resultados" \
  "${envs[@]}" "$K6_IMAGEM" run --quiet --no-usage-report \
  --console-output "/resultados/$nome-console.log" "/carga/$script"

if [ -n "$pid_monitor" ]; then
  kill "$pid_monitor"
  estado_containers
  awk -F, 'NR>1 && $2!="?" { if ($2>c) c=$2; if ($3>a) a=$3; if ($4>p) p=$4 }
    END { printf "máximo no banco: %d conexões radar_api (%d ativas), %d workers paralelos\n", c, a, p }' \
    "$SAIDA/$nome-monitor.csv"
  # Recuperação: a partir do fim da carga, o primeiro instante em que todas as sondas seguintes
  # responderam 200 abaixo de LIMITE_NORMAL_MS.
  LIMITE_NORMAL_MS=500 awk '/SONDA/ {
      for (i = 1; i <= NF; i++) { split($i, kv, "="); v[kv[1]] = kv[2] }
      t = v["t"] + 0; fim = v["fim_carga"] + 0
      if (t >= fim && (v["status"] != 200 || v["ms"] + 0 >= ENVIRON["LIMITE_NORMAL_MS"])) ultimo_ruim = t
      if (t >= fim) { visto = 1; if (t > ultimo) ultimo = t }
    }
    END {
      if (!visto) exit
      if (ultimo_ruim >= ultimo - 1) printf "recuperação: ainda havia sondas lentas no fim da observação (%.1f s depois do fim da carga)\n", ultimo - fim
      else printf "recuperação: sondas normais (200, < %s ms) a partir de %.1f s depois do fim da carga\n", ENVIRON["LIMITE_NORMAL_MS"], (ultimo_ruim ? ultimo_ruim - fim : 0)
    }' "$SAIDA/$nome-console.log"
fi
echo "load average depois: $(cut -d' ' -f1-3 /proc/loadavg)"
