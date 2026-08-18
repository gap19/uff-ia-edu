"""Exporta o dashboard como site estático para hospedagem no Firebase Hosting.

Pré-computa todas as respostas da API que o frontend pode solicitar e as salva
como arquivos JSON em dist/api/, seguindo o mesmo esquema de nomes usado por
staticDataURL() em frontend/static/js/app.js:

    /api/<path>[__<k>-<v>__<k>-<v>...].json   (pares k-v ordenados)

Também renderiza o HTML do dashboard (com window.STATIC_DATA=true injetado),
copia os assets estáticos e pré-gera o relatório PDF completo.

Uso:
    python scripts/export_static.py [--skip-pdf] [--out DIR]
"""

import argparse
import itertools
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import app  # noqa: E402

SERIES = ["5EF", "9EF", "34EM"]
DISCIPLINAS = ["LP", "MT"]
QUESTIONNAIRE_DATASETS = ["aluno_5ef", "aluno_9ef", "aluno_34em", "professor", "diretor"]
STUDENT_TECH_VARS = ["TX_RESP_Q12b", "TX_RESP_Q12g", "TX_RESP_Q13a", "TX_RESP_Q13b"]
DIRECTOR_TECH_VARS = ["TX_Q194", "TX_Q219", "TX_Q035", "TX_Q036"]
TEACHER_TECH_VARS = ["TX_Q029", "TX_Q037"]


def slug_path(path: str, params: dict) -> str:
    """Espelha staticDataURL() do app.js: pares k-v ordenados, separados por __."""
    pairs = sorted(
        f"{k}-{str(v).lower() if isinstance(v, bool) else v}"
        for k, v in params.items()
        if v is not None and v != ""
    )
    suffix = "__" + "__".join(pairs) if pairs else ""
    return f"api{path}{suffix}.json"


def enumerate_calls() -> list[tuple[str, dict]]:
    """Todas as combinações (path, params) alcançáveis pelo frontend."""
    calls: list[tuple[str, dict]] = [
        ("/saeb/overview", {}),
        ("/saeb/proficiency/comparison", {}),
        ("/saeb/proficiency/levels", {"scope": "rj"}),
        ("/saeb/equity/inse", {}),
        ("/saeb/equity/location", {}),
        ("/saeb/teachers/formation", {}),
        ("/tic/infrastructure", {}),
        ("/tic/ai", {}),
        ("/tic/privacy", {}),
        ("/tic/teacher-training", {}),
        ("/tic/digital-literacy", {}),
    ]

    for serie, disc in itertools.product(SERIES, DISCIPLINAS):
        base = {"serie": serie, "disciplina": disc}
        calls.append(("/saeb/proficiency", base))
        calls.append(("/saeb/proficiency/ranking", base))
        calls.append(("/saeb/equity/gap", base))
        calls.append(("/cross/summary", base))
        calls.append(("/cross/digital-index", {**base, "use_precomputed": True}))
        calls.append(("/cross/digital-index", {**base, "stratify_inse": True}))
        for var in STUDENT_TECH_VARS:
            calls.append(
                ("/cross/student-tech", {**base, "variable": var, "use_precomputed": True})
            )
        calls.append(
            (
                "/cross/student-tech",
                {**base, "variable": "TX_RESP_Q13b", "stratify_inse": True,
                 "use_precomputed": False},
            )
        )
        for var in DIRECTOR_TECH_VARS:
            calls.append(("/cross/director-tech", {**base, "variable": var}))
        for var in TEACHER_TECH_VARS:
            calls.append(("/cross/teacher-tech", {**base, "variable": var}))

    return calls


def export(out_dir: Path, skip_pdf: bool) -> int:
    client = TestClient(app)
    api_dir = out_dir / "api"
    failures: list[str] = []
    n_ok = 0

    def save(path: str, params: dict) -> dict | None:
        nonlocal n_ok
        # Booleans como o URLSearchParams serializa ("true"/"false")
        query = {
            k: (str(v).lower() if isinstance(v, bool) else v)
            for k, v in params.items()
            if v is not None and v != ""
        }
        resp = client.get(f"/api{path}", params=query)
        if resp.status_code != 200:
            failures.append(f"{path} {params} -> HTTP {resp.status_code}")
            return None
        data = resp.json()
        target = api_dir.parent / slug_path(path, params)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        n_ok += 1
        return data

    print("Exportando respostas da API...")
    for path, params in enumerate_calls():
        save(path, params)

    print("Exportando questionários...")
    for dataset in QUESTIONNAIRE_DATASETS:
        full = save(f"/saeb/questionnaire/{dataset}", {})
        if not full:
            continue
        for q in full.get("questions") or []:
            save(f"/saeb/questionnaire/{dataset}", {"questao": q["code"]})

    print("Renderizando dashboard...")
    resp = client.get("/dashboard")
    resp.raise_for_status()
    html = resp.text
    marker = "<script"
    inject = "<script>window.STATIC_DATA = true;</script>\n    "
    idx = html.find(marker)
    html = html[:idx] + inject + html[idx:] if idx >= 0 else inject + html
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    print("Copiando assets estáticos...")
    static_src = PROJECT_ROOT / "frontend" / "static"
    static_dst = out_dir / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)

    if not skip_pdf:
        print("Gerando relatório PDF completo (pode demorar alguns minutos)...")
        resp = client.get(
            "/api/reports/generate",
            params=[
                *[("secoes", s) for s in ["proficiencia", "equidade", "tecnologia", "etica"]],
                *[("series", s) for s in SERIES],
                *[("disciplinas", d) for d in DISCIPLINAS],
                ("incluir_apendice", "true"),
            ],
        )
        if resp.status_code == 200:
            reports_dir = out_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "relatorio_ia_educacao_uff.pdf").write_bytes(resp.content)
        else:
            failures.append(f"/reports/generate -> HTTP {resp.status_code}")

    print(f"\n{n_ok} arquivos JSON exportados em {out_dir}")
    if failures:
        print(f"{len(failures)} falhas:")
        for f in failures:
            print(f"  - {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "dist")
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()
    sys.exit(export(args.out, args.skip_pdf))
