# Dados de origem

Fonte: Portal Brasileiro de Dados Abertos ([dados.gov.br](https://dados.gov.br)), arquivos publicados em `https://repositorio.dados.gov.br/segrt/`.

| Conjunto | Arquivo usado | Situação | Linhas |
|---|---|---|---|
| [Gestão de Pessoas — Carreiras/Cargos](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal---carreiras--cargos) | `Cargos e Carreiras/2026/CARREIRA_082026.txt` (193 MB) | ativos, referência 08/2026 | 1.092.162 |
| [Gestão de Pessoas — Aposentados](https://dados.gov.br/dados/conjuntos-dados/gestao-de-pessoas-executivo-federal--aposentados) | `Aposentados/2026/APOSENTADOS_052026_FULL.csv` (162 MB) | aposentados, estoque completo de 05/2026 | 412.354 |

Os dois são os arquivos completos mais recentes publicados. Os arquivos mensais de aposentados (`APOSENTADOS_062026.csv` em diante) trazem só as aposentadorias novas do mês, sem cabeçalho, e não foram incorporados (ver Limitações).

## Formato

Os dois arquivos usam:

- encoding **ISO-8859-1 (Latin-1)**;
- separador `;`, sem aspas como delimitador de campo (existem `"` dentro de alguns valores);
- campos com largura fixa, completados com espaços;
- valores monetários no formato brasileiro, `1.234,56`;
- datas como `DDMMYYYY`, vazias quando não informadas;
- CPF já mascarado pela fonte (`***123456**`).

Nomes, cargos e órgãos estão em **maiúsculas, quase sempre sem acentos** (há exceções, como um cargo com "Ã" e 28 nomes com espaço duplo; a carga normaliza tudo). Nomes de órgãos e cargos são truncados em 40 caracteres pela fonte (ex.: `DEP.DE CENTRAL.SERV.DE INATIVOS E PENS.`).

### CARREIRA_082026.txt (ativos)

A 1ª linha é um título (`CARREIRA.082026`), a 2ª o cabeçalho. Toda linha termina com `;`. Ao fim de cada carreira há uma linha de subtotal `TOTAL DA CARREIRA nnn:` e, no fim do arquivo, `TOTAL GERAL:` (133 linhas de totais, todas com CPF vazio, descartadas na carga).

| Campo | Exemplo | Distintos | Uso |
|---|---|---|---|
| Nome | `TEREZINHA MAGALHAES SANTANA` | 1.040.793 | `servidor.nome` |
| CPF | `***762815**` | 630.815 | não importado |
| Código da carreira | `001` | 119 | `servidor.codigo_carreira` |
| Descrição do cargo emprego | `TECNICO DE FINANCAS E CONTROLE` | 2.998 | `cargo.nome` |
| UF da UPAG de vinculação | `BA` | 27 | `servidor.uf` |
| Denominação do órgão de atuação | `MINISTERIO DA AGRICULTURA E PECUARIA` | 230 | `orgao.nome` |
| Mês de referência | `08` | 1 | não importado (constante) |
| Valor da remuneração | `1.621,00` | 490.149 | `servidor.valor` |

### APOSENTADOS_052026_FULL.csv (aposentados)

Cabeçalho na 1ª linha, 18 campos, sem `;` final. **123 linhas** têm `;` dentro do campo *Portaria aposentadoria* (ex.: `POR.NR 025, DE 26 FEV 1986; E DOU DE 28 FEV 1986.`). Como os 13 campos anteriores e os 4 posteriores são fixos, a carga reconstrói a portaria juntando os campos do meio.

| Campo | Exemplo | Distintos | Uso |
|---|---|---|---|
| Nome | `ABNER URIAS DE ABREU` | 388.351 | `servidor.nome` |
| CPF | `***150721**` | 318.223 | não importado |
| Matricula | `133000000003` | 412.354 (única) | não importado |
| Orgao | `MINISTERIO DA AGRICULTURA E PECUARIA` | 180 | `orgao.nome` |
| Sigla Orgao | `MAPA` | 180 | `orgao.sigla` |
| Orgao vinculacao | `00000` | 22 | não importado |
| Cargo emprego | `AGENTE DE PORTARIA` | 1.594 (65 vazios) | `cargo.nome` |
| Classe / Padrao / Referencia / Nivel | `S` / `II` / `00` / `000` | | não importados |
| Tipo aposentadoria | `VOLUNTARIA` | 6 | `servidor.tipo_aposentadoria` |
| Fund legal aposentadoria | `CF 40 III C` | 492 | `servidor.fundamento_legal` |
| Portaria aposentadoria | `LEI 014600/2023, ...` | 311.673 | `servidor.portaria` |
| Dt ocorrencia inatividade | `30111990` | 15.196 | `servidor.data_aposentadoria` |
| Nome ocorrencia | `NOMEACAO PARA CARGO` | 168 | `servidor.forma_ingresso` |
| Dt ingresso servico publico | `01101958` | 18.868 (4.312 vazios) | `servidor.data_ingresso` |
| Valor aposentadoria | `4.754,61` | 321.782 | `servidor.valor` |

## Limitações

- **Aposentados não têm UF.** O conjunto não traz estado; o filtro `uf` só encontra ativos. O enunciado pede os campos "conforme os campos disponíveis nos conjuntos de dados utilizados".
- **CPF e matrícula não são usados.** O CPF vem mascarado e não identifica a pessoa de forma única, então não dá para ligar um aposentado ao seu registro de ativo.
- **Uma pessoa pode aparecer mais de uma vez**: cada linha é um vínculo (ex.: dois cargos acumuláveis).
- **Aposentados com data de corte 05/2026**: as aposentadorias de 06 a 08/2026, publicadas em arquivos mensais, ficam fora.
- O dicionário de dados oficial (PDF na página do conjunto) ainda não foi anexado em `docs/`; a descrição acima foi feita a partir dos cabeçalhos e de uma análise completa dos arquivos.
