"""Gera uma amostra sintética dos arquivos de origem, no mesmo formato do dados.gov.br.

Usada pelo smoke test do CI e por quem quer subir o projeto sem baixar ~355 MB:

    python3 scripts/gerar_amostra.py
    cp projeto/db/amostra/* projeto/db/data/

Os nomes são fictícios (combinações de listas abaixo). O formato reproduz o que a carga
(projeto/db/init/03-carga.sql) trata: Latin-1, separador ';', campos com largura fixa,
linha de título e linhas de total no arquivo de ativos, e ';' dentro da portaria.
"""

import random
from pathlib import Path

SEED = 2026
ENCODING = "latin-1"
DESTINO = Path(__file__).resolve().parent.parent / "projeto" / "db" / "amostra"
ARQUIVO_ATIVOS = "CARREIRA_082026.txt"
ARQUIVO_APOSENTADOS = "APOSENTADOS_052026_FULL.csv"

QTD_ATIVOS = 300
QTD_APOSENTADOS = 150
MES_REFERENCIA = "08"

# Larguras dos campos como no arquivo original
L_NOME = 60
L_CARGO = 40
L_ORGAO = 40
L_SIGLA = 10
L_VALOR = 18
L_TITULO = 180

PRIMEIROS = ["MARIA", "JOSE", "ANA", "JOAO", "FRANCISCO", "ANTONIO", "CARLOS", "PAULO", "LUCIA"]
MEIOS = ["", "DA SILVA ", "DE SOUZA ", "DOS SANTOS ", "APARECIDA ", "CARLOS "]
ULTIMOS = ["SILVA", "SANTOS", "OLIVEIRA", "SOUZA", "LIMA", "PEREIRA", "COSTA", "FERREIRA"]
# Nomes repetidos de propósito, para a busca por nome exato achar vários vínculos
NOMES_FIXOS = ["MARIA DA SILVA", "MARIA DA SILVA", "MARIA DA SILVA", "JOSE CARLOS DA SILVA"]

CARREIRAS = [
    ("001", "ANALISTA DE FINANCAS E CONTROLE"),
    ("019", "ASSISTENTE EM ADMINISTRACAO"),
    ("038", "PROFESSOR DO MAGISTERIO SUPERIOR"),
    ("045", "PROFESSOR ENS BASICO TECN TECNOLOGICO"),
    ("621", "TECNICO DO SEGURO SOCIAL"),
    ("070", "MEDICO"),
]
ORGAOS = [
    ("MINISTERIO DA SAUDE", "MS"),
    ("INSTITUTO NACIONAL DE SEGURO SOCIAL", "INSS"),
    ("COLEGIO PEDRO II", "CPII"),
    ("UNIVERSIDADE FEDERAL DO RIO DE JANEIRO", "UFRJ"),
    ("CONTROLADORIA-GERAL DA UNIAO", "CGU"),
]
UFS = ["DF", "RJ", "SP", "MG", "BA", "PE", "RS", "CE"]
TIPOS_APOSENTADORIA = ["VOLUNTARIA", "APOSENTADORIA POR INVALIDEZ", "COMPULSORIA"]
FUNDAMENTOS = ["EC47 3º", "CF 40 III C", "EC103 3º EC47 3º"]
OCORRENCIAS = ["ADMISSAO POR CONCURSO PUBLICO", "ADMISSAO SEM CONCURSO PUBLICO"]
PORTARIA_COM_PONTO_E_VIRGULA = "POR.NR 025, DE 26 FEV 1986; E DOU DE 28 FEV 1986."

VALOR_MIN = 1_500
VALOR_MAX = 35_000
ANO_INGRESSO = (1975, 2010)
ANO_APOSENTADORIA = (1995, 2026)


def nome(rng: random.Random, indice: int) -> str:
    if indice < len(NOMES_FIXOS):
        return NOMES_FIXOS[indice]
    return f"{rng.choice(PRIMEIROS)} {rng.choice(MEIOS)}{rng.choice(ULTIMOS)}"


def valor_br(valor: float) -> str:
    """12345.6 -> '12.345,60'"""
    return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def cpf_mascarado(rng: random.Random) -> str:
    return f"***{rng.randrange(10**6):06d}**"


def data(rng: random.Random, anos: tuple[int, int]) -> str:
    return f"{rng.randint(1, 28):02d}{rng.randint(1, 12):02d}{rng.randint(*anos)}"


def gerar_ativos(rng: random.Random) -> list[str]:
    linhas = [
        "CARREIRA.082026".ljust(L_TITULO),
        (
            "Nome;CPF;Código da carreira;Descrição do cargo emprego;UF da UPAG de vinculação;"
            "Denominação do órgão de atuação;Mês de referência;Valor da remuneração;"
        ),
    ]
    por_carreira: dict[str, list[tuple[str, float]]] = {codigo: [] for codigo, _ in CARREIRAS}
    for i in range(QTD_ATIVOS):
        codigo, cargo = CARREIRAS[i % len(CARREIRAS)]
        orgao, _ = rng.choice(ORGAOS)
        valor = round(rng.uniform(VALOR_MIN, VALOR_MAX), 2)
        linha = ";".join(
            [
                nome(rng, i).ljust(L_NOME),
                cpf_mascarado(rng),
                codigo,
                cargo.ljust(L_CARGO),
                rng.choice(UFS),
                orgao.ljust(L_ORGAO),
                MES_REFERENCIA,
                valor_br(valor).rjust(L_VALOR),
                "",
            ]
        )
        por_carreira[codigo].append((linha, valor))

    total_geral = 0.0
    for codigo, registros in por_carreira.items():
        linhas.extend(linha for linha, _ in registros)
        total = sum(valor for _, valor in registros)
        total_geral += total
        linhas.append(linha_total(f"TOTAL DA CARREIRA {codigo}:", total))
    linhas.append(linha_total("TOTAL GERAL:", total_geral))
    return linhas


def linha_total(rotulo: str, total: float) -> str:
    vazios = [" " * 11, " " * 3, " " * L_CARGO, " " * 2, " " * L_ORGAO, " " * 2]
    return ";".join([rotulo.ljust(L_NOME), *vazios, valor_br(total).rjust(L_VALOR), ""])


def gerar_aposentados(rng: random.Random) -> list[str]:
    linhas = [
        (
            "Nome;CPF;Matricula;Orgao;Sigla Orgao;Orgao vinculacao;Cargo emprego;Classe;Padrao;"
            "Referencia;Nivel;Tipo aposentadoria;Fund legal aposentadoria;Portaria aposentadoria;"
            "Dt ocorrencia inatividade;Nome ocorrencia;Dt ingresso servico publico;Valor aposentadoria"
        )
    ]
    for i in range(QTD_APOSENTADOS):
        orgao, sigla = rng.choice(ORGAOS)
        _, cargo = rng.choice(CARREIRAS)
        cargo = "" if i == 1 else cargo  # há aposentados sem cargo na fonte
        portaria = (
            PORTARIA_COM_PONTO_E_VIRGULA if i == 2 else f"DEC {rng.randrange(10**6):06d}/2018"
        )
        ingresso = "" if i == 3 else data(rng, ANO_INGRESSO)  # e sem data de ingresso
        linha = ";".join(
            [
                nome(rng, i).ljust(L_NOME),
                cpf_mascarado(rng),
                f"{133000000000 + i}",
                orgao.ljust(L_ORGAO),
                sigla.ljust(L_SIGLA),
                "00000",
                cargo.ljust(L_CARGO),
                "S",
                "V  ",
                "00",
                "000",
                rng.choice(TIPOS_APOSENTADORIA).ljust(27),
                rng.choice(FUNDAMENTOS).ljust(40),
                portaria.ljust(60),
                data(rng, ANO_APOSENTADORIA),
                rng.choice(OCORRENCIAS).ljust(50),
                ingresso.ljust(8),
                valor_br(round(rng.uniform(VALOR_MIN, VALOR_MAX), 2)).rjust(L_VALOR),
            ]
        )
        linhas.append(linha)
    return linhas


def main() -> None:
    rng = random.Random(SEED)
    DESTINO.mkdir(parents=True, exist_ok=True)
    for arquivo, linhas in [
        (ARQUIVO_ATIVOS, gerar_ativos(rng)),
        (ARQUIVO_APOSENTADOS, gerar_aposentados(rng)),
    ]:
        (DESTINO / arquivo).write_bytes(("\n".join(linhas) + "\n").encode(ENCODING))
        print(f"{DESTINO / arquivo}: {len(linhas)} linhas")


if __name__ == "__main__":
    main()
