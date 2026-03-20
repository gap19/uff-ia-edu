#!/bin/bash
# Setup completo do projeto: instala dependências e executa ETL
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================="
echo "  Setup: Dashboard IA e Educação (UFF)"
echo "========================================="

# Criar venv se não existir
if [ ! -d ".venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv .venv
fi

# Ativar venv
source .venv/bin/activate

# Instalar dependências
echo "Instalando dependências..."
pip install -r backend/requirements.txt --quiet

# Criar diretórios de dados processados
mkdir -p data/processed/saeb data/processed/tic

# Executar ETL
echo ""
echo "Executando pipeline ETL..."
python scripts/init_db.py "$@"

echo ""
echo "Setup concluído! Execute:"
echo "  source .venv/bin/activate"
echo "  python scripts/run.py"
