#!/usr/bin/env bash
# Atribui cada issue ao responsável definido no planejamento.
# Rodar depois que os colegas aceitarem o convite do repositório.
set -euo pipefail
cd "$(dirname "$0")"
python3 -c 'import json; [print(i["issue"], i["login"]) for i in json.load(open("responsaveis.json"))]' |
while read -r issue login; do
  gh issue edit "$issue" -R cerfdotdev/radar-publico --add-assignee "$login" >/dev/null && echo "#$issue -> $login"
done
