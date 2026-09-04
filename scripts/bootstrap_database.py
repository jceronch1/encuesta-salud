from __future__ import annotations

import os
import sys
from pathlib import Path


admin_url = os.getenv("DATABASE_ADMIN_URL", "").strip()
if not admin_url:
    print("Defina DATABASE_ADMIN_URL con una cuenta que pueda crear tablas.", file=sys.stderr)
    raise SystemExit(2)

# It must be set before app.config is imported.
os.environ["DATABASE_URL"] = admin_url
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401


Base.metadata.create_all(bind=engine)
print("Tablas listas:", ", ".join(sorted(Base.metadata.tables)))
