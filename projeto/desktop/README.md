# Radar Público — Desktop

App PySide6 que consulta a mesma API do frontend web ([docs/api.md](../../docs/api.md)):
nome exato ou parecido (com limite), cargo, órgão, UF, situação, paginação e o detalhe do
vínculo.

## Instalação e execução

Requer Python 3.13 e a API no ar (`docker compose up` em `projeto/`).

```bash
cd projeto/desktop
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## URL da API

Por ordem de precedência:

1. `--api-url` na linha de comando;
2. variável de ambiente `RADAR_API_URL`;
3. padrão `http://localhost:5000/api`, o backend do Docker Compose.

É a base da API, terminada em `/api`, como em `docs/api.md`. Só `http://` e `https://` são
aceitos.

```bash
python main.py --api-url http://localhost:5000/api
RADAR_API_URL=http://servidor:5000/api python main.py
```

Com o app aberto, dá para trocar em **Configurações → URL da API…**.

## Uso

- Enter em qualquer campo do formulário busca; Alt + a letra sublinhada leva a cada campo.
- **Nome parecido** aceita `%` como curinga, precisa de 3 letras fora dos `%` e devolve até o
  limite escolhido (1 a 100), sem paginação.
- O filtro de UF só encontra servidores ativos: a fonte dos aposentados não traz UF.
- Enter ou duplo clique numa linha, ou **Ver detalhe**, abre a ficha do vínculo.
- As chamadas à API rodam fora da thread da interface, com tempo limite de 20 s
  (`TEMPO_LIMITE_S` em `radar_desktop/api.py`). Uma busca nova descarta a resposta da anterior.

## Dependências

Só `pyside6-essentials` e `shiboken6` (QtCore, QtGui e QtWidgets), com versão exata. O pacote
`pyside6` traria também Addons, WebEngine e Pdf, que o app não usa. O HTTP usa a biblioteca
padrão (`urllib`). O Qt for Python é usado sob a LGPL-3.0, sem modificações.

## Testes

Os mesmos comandos do CI, dentro de `projeto/desktop`:

```bash
pip install --require-hashes --no-deps -r ../../.github/ci/requirements.txt
ruff check . && ruff format --check .
bandit -r . -x ./tests,./.venv -ll
pip-audit --strict
python -m pytest
```

Os testes da janela usam `QT_QPA_PLATFORM=offscreen`, sem abrir tela. Se o Qt não puder ser
carregado (faltam bibliotecas gráficas do sistema), eles são pulados.
