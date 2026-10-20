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

## Executável (PyInstaller)

O `build.py` gera, com o PyInstaller, uma pasta com o executável e as bibliotecas ao lado (modo
*onedir*), que roda sem Python instalado. O build é feito em cada sistema: o PyInstaller não gera o
executável de um sistema em outro.

### Gerar

Com o ambiente da seção [Instalação e execução](#instalação-e-execução) ativo (Python 3.13 e
`requirements.txt` instalados), os comandos são os mesmos no Linux, no Windows e no macOS:

```bash
pip install --require-hashes -r requirements-build.txt
python build.py
```

| Sistema | Onde fica o executável |
|---|---|
| Linux | `dist/RadarPublico/RadarPublico` |
| Windows | `dist\RadarPublico\RadarPublico.exe` (sem janela de console) |
| macOS | `dist/RadarPublico.app` (e `dist/RadarPublico/RadarPublico`) |

O executável não roda sozinho: para levar a outra máquina, copie a pasta `dist/RadarPublico/`
inteira (no macOS, o `RadarPublico.app`). `dist/` e `build/` ficam fora do Git.

- **Linux**: o Qt usa bibliotecas gráficas do sistema, presentes em qualquer desktop. Num servidor
  ou container Debian/Ubuntu, instale antes do build `libegl1 libgl1 libxkbcommon0
  libxkbcommon-x11-0 libfontconfig1 libdbus-1-3` e, para o PyInstaller copiar o que o plugin xcb
  (X11) usa, `libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0
  libxcb-shape0 libxcb-util1`. O executável roda em distribuições com glibc igual ou mais nova
  que a da máquina do build.
- **Windows** e **Linux** são gerados e testados pelo CI (abaixo); o **macOS** segue os mesmos
  passos, mas não passa pelo CI.

### Rodar contra a API

A URL da API vem do mesmo lugar que no código-fonte ([URL da API](#url-da-api)):

```bash
./dist/RadarPublico/RadarPublico --api-url http://localhost:5000/api     # Linux
dist\RadarPublico\RadarPublico.exe --api-url http://localhost:5000/api   # Windows
open dist/RadarPublico.app --args --api-url http://localhost:5000/api    # macOS
RADAR_API_URL=http://servidor:5000/api ./dist/RadarPublico/RadarPublico  # pela variável
```

### Verificar o executável

`--verificar` abre a janela fora da tela (plugin `offscreen` do Qt, se `QT_QPA_PLATFORM` não
indicar outro), consulta `GET <api>/health` e sai, sem mudar nada na execução normal:

```console
$ ./dist/RadarPublico/RadarPublico --api-url http://localhost:5000/api --verificar
Radar Público 1.0.0: janela ok (plataforma offscreen).
API em http://localhost:5000/api: ok.
```

Sai com código 0 quando a janela abre, mesmo com a API fora do ar (a linha da API mostra
"indisponível" e o motivo), e com 1 quando o Qt ou a janela falham. No Windows o executável não
tem console e o terminal não espera por ele; para ver o código de saída, no PowerShell:
`(Start-Process dist\RadarPublico\RadarPublico.exe -ArgumentList '--verificar' -Wait -PassThru).ExitCode`.

### Baixar o executável do CI

O workflow [Desktop (executável)](../../.github/workflows/desktop-build.yml) gera o executável no
Linux e no Windows, roda os testes e o `--verificar` em cada PR ou push na `main` que mexa em
`projeto/desktop/`; também dá para rodar à mão em **Actions → Desktop (executável) → Run
workflow**. O executável fica em **Artifacts**, no fim da página da execução (é preciso estar
logado no GitHub), por 7 dias (`RETENCAO_DIAS` no workflow):

- `RadarPublico-Linux.tar.gz`: `tar -xzf RadarPublico-Linux.tar.gz` e rode
  `RadarPublico/RadarPublico`. É `.tar.gz` porque o zip do GitHub perde a permissão de execução;
- `RadarPublico-Windows`: baixa como `.zip`; extraia e rode `RadarPublico\RadarPublico.exe`.

Não é um check obrigatório do PR: o `ci-ok` do CI continua sendo o único.

### Licenças (LGPL-3.0)

O Qt for Python (PySide6, Shiboken6) e o Qt são usados sob a LGPL-3.0, sem modificações. Por isso:

- o build é sempre *onedir*: o Qt e o PySide6 ficam como bibliotecas compartilhadas separadas em
  `_internal/`, e quem recebe o app pode trocá-las por outra versão compatível sem recompilar o
  app. Não use `--onefile`, que junta tudo num arquivo só;
- o executável leva `_internal/LICENCAS/`, copiada de [`licencas/`](licencas/): o
  [`AVISO.txt`](licencas/AVISO.txt) (componentes, onde baixar o código-fonte do Qt e do PySide6),
  os textos da LGPL-3.0 e da GPL-3.0 e a licença do Python;
- para trocar o Qt, substitua os arquivos do Qt 6.12 da mesma arquitetura em
  `_internal/PySide6/`: no Linux, `Qt/lib/libQt6*.so.6` (os `_internal/libQt6*.so.6` são links
  para eles); no Windows, `Qt6*.dll`; no macOS, os `*.framework` em
  `RadarPublico.app/Contents/Frameworks/PySide6/Qt/lib/`. Os plugins do Qt ficam na mesma pasta,
  em `plugins/` (no Linux, `Qt/plugins/`).

## Dependências

Só `pyside6-essentials` e `shiboken6` (QtCore, QtGui e QtWidgets), com versão exata. O pacote
`pyside6` traria também Addons, WebEngine e Pdf, que o app não usa. O HTTP usa a biblioteca
padrão (`urllib`). O Qt for Python é usado sob a LGPL-3.0, sem modificações.

As dependências de build ficam à parte, em `requirements-build.txt`: o PyInstaller e as
dependências dele com versão exata e hash, inclusive as que só o Windows e o macOS usam. O arquivo
é gerado pelo [uv](https://docs.astral.sh/uv/) a partir de `requirements-build.in`, só com versões
publicadas há pelo menos 7 dias (a mesma espera do Dependabot):

```bash
uv pip compile requirements-build.in --universal --generate-hashes --python-version 3.13 \
  --exclude-newer "$(date -d '7 days ago' +%F)" -o requirements-build.txt
```

## Testes

Os mesmos comandos do CI, dentro de `projeto/desktop`:

```bash
pip install --require-hashes --no-deps -r ../../.github/ci/requirements.txt
ruff check . && ruff format --check .
bandit -r . -x ./tests,./.venv -ll
pip-audit --strict
pip-audit --strict --disable-pip -r requirements-build.txt
python -m pytest
```

Os testes da janela usam `QT_QPA_PLATFORM=offscreen`, sem abrir tela. Se o Qt não puder ser
carregado (faltam bibliotecas gráficas do sistema), eles são pulados; os do `build.py` também,
sem as dependências de build instaladas.
