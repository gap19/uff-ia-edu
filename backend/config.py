"""Configuração central do projeto."""

from pathlib import Path

# Raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Diretórios de dados
DATA_DIR = PROJECT_ROOT / "data"
SAEB_RAW_DIR = DATA_DIR / "MICRODADOS_SAEB_2023"
SAEB_CSV_DIR = SAEB_RAW_DIR / "DADOS"
SAEB_INPUTS_DIR = SAEB_RAW_DIR / "INPUTS"
SAEB_DICT_DIR = SAEB_RAW_DIR / "DICIONÁRIO"
TIC_RAW_DIR = DATA_DIR / "tic_educacao_2023_escolas_tabelas_xlsx_v1.0"
PROCESSED_DIR = DATA_DIR / "processed"
SAEB_PARQUET_DIR = PROCESSED_DIR / "saeb"
TIC_PARQUET_DIR = PROCESSED_DIR / "tic"
DUCKDB_PATH = PROCESSED_DIR / "saeb.duckdb"

# Filtros geográficos (códigos IBGE)
ID_UF_RJ = 33
ID_REGIAO_SUDESTE = 3

# Arquivos SAEB esperados
SAEB_CSV_FILES = [
    "TS_ALUNO_2EF",
    "TS_ALUNO_5EF",
    "TS_ALUNO_9EF",
    "TS_ALUNO_34EM",
    "TS_ESCOLA",
    "TS_PROFESSOR",
    "TS_DIRETOR",
    "TS_SECRETARIO_MUNICIPAL",
    "TS_ITEM",
]

# Arquivos TIC esperados
TIC_XLSX_FILES = {
    "proporcao": TIC_RAW_DIR / "tic_educacao_2023_escolas_tabela_proporcao_v1.0.xlsx",
    "total": TIC_RAW_DIR / "tic_educacao_2023_escolas_tabela_total_v1.0.xlsx",
    "margem_erro": TIC_RAW_DIR / "tic_educacao_2023_escolas_tabela_margem_de_erro_v1.0.xlsx",
    "margem_erro_total": TIC_RAW_DIR / "tic_educacao_2023_escolas_tabela_margem_de_erro_total_v1.0.xlsx",
}

# Colunas de proficiência (escala SAEB, não padronizada)
PROFICIENCY_COLS = {
    "LP": "PROFICIENCIA_LP_SAEB",
    "MT": "PROFICIENCIA_MT_SAEB",
    "CH": "PROFICIENCIA_CH_SAEB",
    "CN": "PROFICIENCIA_CN_SAEB",
}

# Colunas de proficiência padronizada (z-score)
PROFICIENCY_Z_COLS = {
    "LP": "PROFICIENCIA_LP",
    "MT": "PROFICIENCIA_MT",
    "CH": "PROFICIENCIA_CH",
    "CN": "PROFICIENCIA_CN",
}

# Colunas de peso amostral
WEIGHT_COLS = {
    "LP": "PESO_ALUNO_LP",
    "MT": "PESO_ALUNO_MT",
    "CH": "PESO_ALUNO_CH",
    "CN": "PESO_ALUNO_CN",
    "INSE": "PESO_ALUNO_INSE",
}

# Séries
SERIES_MAP = {
    2: "2EF",
    5: "5EF",
    9: "9EF",
    12: "3EM",
    13: "4EM",
}

# UFs (código IBGE -> sigla)
UF_MAP = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

# Regiões
REGIAO_MAP = {
    1: "Norte",
    2: "Nordeste",
    3: "Sudeste",
    4: "Sul",
    5: "Centro-Oeste",
}
