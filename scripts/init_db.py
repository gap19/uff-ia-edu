#!/usr/bin/env python3
"""ETL completo: CSV/Excel -> Parquet -> tabelas de agregação DuckDB.

Uso:
    python scripts/init_db.py
    python scripts/init_db.py --skip-tic     # Pula TIC (mais rápido)
    python scripts/init_db.py --only-precompute  # Apenas pré-computação
"""

import sys
import time
import argparse
from pathlib import Path

# Adicionar raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Pipeline ETL SAEB/TIC")
    parser.add_argument("--skip-tic", action="store_true", help="Pular processamento TIC")
    parser.add_argument("--only-precompute", action="store_true", help="Apenas pré-computação")
    args = parser.parse_args()

    total_start = time.time()

    if not args.only_precompute:
        # Etapa 1: SAEB CSV -> Parquet
        print("=" * 60)
        print("ETAPA 1: Conversão SAEB CSV -> Parquet")
        print("=" * 60)
        t0 = time.time()
        from backend.etl.saeb_loader import load_all_saeb
        results = load_all_saeb()
        elapsed = time.time() - t0
        print(f"\nSAEB concluído em {elapsed:.1f}s")
        for name, count in results.items():
            print(f"  {name}: {count:,} linhas")

        # Etapa 2: TIC Excel -> Parquet
        if not args.skip_tic:
            print("\n" + "=" * 60)
            print("ETAPA 2: Conversão TIC Excel -> Parquet")
            print("=" * 60)
            t0 = time.time()
            from backend.etl.tic_loader import load_all_tic
            tic_count = load_all_tic()
            elapsed = time.time() - t0
            print(f"\nTIC concluído em {elapsed:.1f}s ({tic_count:,} linhas)")
        else:
            print("\nTIC: PULADO (--skip-tic)")

        # Etapa 3: Codebook
        print("\n" + "=" * 60)
        print("ETAPA 3: Carregando codebook dos scripts R")
        print("=" * 60)
        t0 = time.time()
        from backend.etl.codebook import load_codebook
        codebook = load_codebook()
        elapsed = time.time() - t0
        total_vars = sum(len(v) for v in codebook.values())
        print(f"Codebook carregado em {elapsed:.1f}s: {len(codebook)} tabelas, {total_vars} variáveis")

    # Etapa 4: Pré-computação
    print("\n" + "=" * 60)
    print("ETAPA 4: Pré-computação de tabelas de agregação")
    print("=" * 60)
    t0 = time.time()
    from backend.etl.precompute import precompute_all
    tables = precompute_all()
    elapsed = time.time() - t0
    print(f"Pré-computação concluída em {elapsed:.1f}s: {len(tables)} tabelas")

    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"ETL COMPLETO em {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
