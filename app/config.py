from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} debe ser un numero entero") from exc
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_host: str
    app_port: int
    database_url: str
    upload_dir: Path
    max_file_size_bytes: int
    max_batch_files: int
    processing_workers: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    explicit_url = os.getenv("DATABASE_URL", "").strip()
    if explicit_url:
        database_url = explicit_url
    else:
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = _positive_int("DB_PORT", 3306)
        user = quote_plus(os.getenv("DB_USER", "sigendin"))
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        database = quote_plus(os.getenv("DB_NAME", "encuesta-salud"))
        database_url = (
            f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
            "?charset=utf8mb4"
        )

    upload_dir = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
    if not upload_dir.is_absolute():
        upload_dir = PROJECT_ROOT / upload_dir

    return Settings(
        app_name="Encuesta Salud - Captura OMR",
        app_host=os.getenv("APP_HOST", "127.0.0.1"),
        app_port=_positive_int("APP_PORT", 8000),
        database_url=database_url,
        upload_dir=upload_dir.resolve(),
        max_file_size_bytes=_positive_int("MAX_FILE_SIZE_MB", 50) * 1024 * 1024,
        max_batch_files=_positive_int("MAX_BATCH_FILES", 250),
        processing_workers=_positive_int("PROCESSING_WORKERS", 2),
    )
