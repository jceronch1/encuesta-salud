from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.omr import extract_survey  # noqa: E402


EXPECTED_SHA256 = "2160839f0030c13dda64d40aff5322150ef79204aef0d7795b0d7c2137afff2e"
EXPECTED_DISTRIBUTION = {
    "Siempre": 21,
    "Casi siempre": 16,
    "Algunas veces": 26,
    "Casi nunca": 24,
    "Nunca": 27,
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Uso: python scripts/verify_sample.py RUTA_AL_PDF", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"No existe: {path}", file=sys.stderr)
        return 2

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    result = extract_survey(path)
    distribution = Counter(
        response.answer_label
        for response in result.responses
        if response.status == "answered"
    )

    checks = {
        "sha256": digest == EXPECTED_SHA256,
        "id": result.respondent_identifier == "653118",
        "paginas": result.page_count == 4,
        "clientes": result.serves_customers is True,
        "jefe": result.is_manager is False,
        "respondidas": result.answered_count == 114,
        "esperadas": result.expected_count == 114,
        "distribucion": dict(distribution) == EXPECTED_DISTRIBUTION,
        "sin_avisos": not result.warnings,
    }
    for name, passed in checks.items():
        print(f"{'OK' if passed else 'ERROR':5} {name}")
    print("Metodo:", result.extraction_method)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
