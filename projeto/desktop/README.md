# Radar Público — Desktop

Aplicativo PySide6 que consulta a mesma API do frontend web. Permite busca por
nome exato ou parecido (com limite), filtros combináveis de cargo, órgão e UF,
paginação e detalhe do vínculo.

## Instalação e execução

```bash
cd projeto/desktop
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

## URL da API

A URL é configurável sem alterar o código, por ordem de precedência:

1. `--api-url` na linha de comando;
2. variável `RADAR_API_URL`;
3. variáveis `RADAR_PUBLICO_API_URL` ou `API_URL`;
4. padrão `http://localhost:5000`.

A URL pode incluir ou não o sufixo `/api`:

```bash
python main.py --api-url http://localhost:5000
RADAR_API_URL=http://servidor:5000/api python main.py
```

Também é possível alterar em **Configurações → URL da API…** com o app aberto.

## Testes

Os testes do cliente e das validações não precisam abrir a interface:

```bash
python -m unittest discover -s tests -v
```
