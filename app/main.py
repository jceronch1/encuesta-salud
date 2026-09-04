from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import uuid
from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.analytics import summarize_responses
from app.config import PROJECT_ROOT, get_settings
from app.database import SessionLocal, database_status, ensure_schema
from app.models import Survey, SurveyResponse, Upload, utc_now
from app.processing import processing_manager
from app.questionnaire import ANSWER_OPTIONS
from app.review import (
    answer_option,
    apply_manual_answer,
    apply_manual_identifier,
    detected_answer_codes,
    detected_answer_labels,
    manual_identifier_record,
    recalculate_upload_review_state,
)


logger = logging.getLogger(__name__)
settings = get_settings()
STATIC_DIR = PROJECT_ROOT / "app" / "static"


class ResponseCorrectionRequest(BaseModel):
    answer_code: str


class RespondentIdentifierRequest(BaseModel):
    respondent_identifier: str


def _database_dependency() -> Generator[Session, None, None]:
    try:
        ensure_schema()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MySQL no esta disponible o la cuenta no tiene permisos",
        ) from exc
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    connected, _error = database_status()
    if connected:
        processing_manager.recover_pending()
    else:
        logger.warning("The web app started, but MySQL is not ready")
    yield
    processing_manager.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") + "Z" if value else None


def _upload_payload(upload: Upload, include_responses: bool = False) -> dict:
    survey = upload.survey
    payload = {
        "id": upload.id,
        "filename": upload.original_filename,
        "file_size": upload.file_size,
        "sha256": upload.sha256,
        "status": upload.status,
        "page_count": upload.page_count,
        "extraction_method": upload.extraction_method,
        "detected_answers": upload.detected_answers,
        "expected_answers": upload.expected_answers,
        "warnings": upload.warnings_json or [],
        "error_message": upload.error_message,
        "created_at": _iso(upload.created_at),
        "completed_at": _iso(upload.completed_at),
        "survey": None,
    }
    if survey is not None:
        payload["survey"] = {
            "id": survey.id,
            "respondent_identifier": survey.respondent_identifier,
            "form_type": survey.form_type,
            "serves_customers": survey.serves_customers,
            "is_manager": survey.is_manager,
            "answered_count": survey.answered_count,
            "expected_count": survey.expected_count,
        }
        if include_responses:
            payload["survey"]["respondent_identifier_manual"] = (
                manual_identifier_record(upload) is not None
            )
            payload["survey"]["responses"] = [
                {
                    "question_number": response.question_number,
                    "question_text": response.question_text,
                    "status": response.status,
                    "answer_code": response.answer_code,
                    "answer_label": response.answer_label,
                    "answer_position": response.answer_position,
                    "page_number": response.page_number,
                    "confidence": response.confidence,
                    "extraction_method": response.extraction_method,
                    "detected_answer_codes": detected_answer_codes(
                        response.raw_metadata
                    ),
                    "detected_answer_labels": detected_answer_labels(
                        response.raw_metadata
                    ),
                    "manually_reviewed": response.extraction_method == "manual_review",
                }
                for response in survey.responses
            ]
    return payload


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    connected, error = database_status()
    return {
        "status": "ok" if connected else "degraded",
        "database": {"connected": connected, "engine": "mysql", "error": error},
        "storage": {
            "ready": settings.upload_dir.exists(),
            "path": str(settings.upload_dir),
        },
    }


def _safe_filename(filename: str | None) -> str:
    raw = Path(filename or "encuesta.pdf").name
    cleaned = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", raw).strip(" .")
    return (cleaned or "encuesta.pdf")[:255]


async def _save_pdf(file: UploadFile) -> tuple[Path, str, int, str]:
    original_name = _safe_filename(file.filename)
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail=f"{original_name}: solo se permiten PDF")

    now = datetime.utcnow()
    target_dir = settings.upload_dir / f"{now:%Y}" / f"{now:%m}"
    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target_dir / f".{uuid.uuid4().hex}.uploading"
    digest = hashlib.sha256()
    size = 0
    signature = b""
    try:
        with temporary.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                if not signature:
                    signature = chunk[:8]
                size += len(chunk)
                if size > settings.max_file_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"{original_name}: supera el limite configurado",
                    )
                digest.update(chunk)
                destination.write(chunk)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if size == 0 or not signature.startswith(b"%PDF-"):
        temporary.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"{original_name}: PDF no valido")

    sha256 = digest.hexdigest()
    final_path = target_dir / f"{uuid.uuid4().hex}.pdf"
    temporary.replace(final_path)
    return final_path, sha256, size, original_name


@app.post("/api/uploads", status_code=status.HTTP_202_ACCEPTED)
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    session: Session = Depends(_database_dependency),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="Seleccione al menos un PDF")
    if len(files) > settings.max_batch_files:
        raise HTTPException(
            status_code=400,
            detail=f"El lote admite maximo {settings.max_batch_files} archivos",
        )

    accepted: list[dict] = []
    for file in files:
        final_path, sha256, size, original_name = await _save_pdf(file)
        existing = session.scalar(
            select(Upload)
            .options(selectinload(Upload.survey))
            .where(Upload.sha256 == sha256)
        )
        if existing is not None:
            final_path.unlink(missing_ok=True)
            item = _upload_payload(existing)
            item["duplicate"] = True
            accepted.append(item)
            continue

        upload = Upload(
            original_filename=original_name,
            stored_path=str(final_path),
            sha256=sha256,
            file_size=size,
            status="queued",
        )
        session.add(upload)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            final_path.unlink(missing_ok=True)
            existing = session.scalar(select(Upload).where(Upload.sha256 == sha256))
            if existing is None:
                raise
            item = _upload_payload(existing)
            item["duplicate"] = True
            accepted.append(item)
            continue
        session.refresh(upload)
        item = _upload_payload(upload)
        item["duplicate"] = False
        accepted.append(item)
        processing_manager.submit(upload.id)

    return {"items": accepted, "count": len(accepted)}


@app.get("/api/uploads")
def list_uploads(
    limit: int = Query(50, ge=1, le=250),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=120),
    session: Session = Depends(_database_dependency),
) -> dict:
    filters = []
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Upload.original_filename.like(term),
                Upload.survey.has(Survey.respondent_identifier.like(term)),
            )
        )
    total = session.scalar(select(func.count(Upload.id)).where(*filters)) or 0
    uploads = session.scalars(
        select(Upload)
        .options(selectinload(Upload.survey))
        .where(*filters)
        .order_by(Upload.created_at.desc(), Upload.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": [_upload_payload(upload) for upload in uploads], "total": total}


@app.get("/api/uploads/{upload_id}")
def upload_detail(
    upload_id: int, session: Session = Depends(_database_dependency)
) -> dict:
    upload = session.scalar(
        select(Upload)
        .options(selectinload(Upload.survey).selectinload(Survey.responses))
        .where(Upload.id == upload_id)
    )
    if upload is None:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    return _upload_payload(upload, include_responses=True)


@app.patch("/api/uploads/{upload_id}/respondent-identifier")
def update_respondent_identifier(
    upload_id: int,
    correction: RespondentIdentifierRequest,
    session: Session = Depends(_database_dependency),
) -> dict:
    identifier = correction.respondent_identifier.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", identifier):
        raise HTTPException(
            status_code=400,
            detail=(
                "ID invalido. Use entre 1 y 120 caracteres: letras, numeros, "
                "punto, guion o guion bajo"
            ),
        )

    upload = session.scalar(
        select(Upload)
        .options(selectinload(Upload.survey).selectinload(Survey.responses))
        .where(Upload.id == upload_id)
    )
    if upload is None or upload.survey is None:
        raise HTTPException(status_code=404, detail="Encuesta procesada no encontrada")
    if upload.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=409,
            detail="Espere a que termine el procesamiento antes de guardar el ID",
        )

    apply_manual_identifier(upload, identifier, utc_now())
    recalculate_upload_review_state(upload)
    session.commit()
    return _upload_payload(upload, include_responses=True)


@app.patch("/api/uploads/{upload_id}/responses/{question_number}")
def correct_response(
    upload_id: int,
    question_number: int,
    correction: ResponseCorrectionRequest,
    session: Session = Depends(_database_dependency),
) -> dict:
    option = answer_option(correction.answer_code)
    if option is None:
        allowed = ", ".join(code for code, _label, _position in ANSWER_OPTIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Respuesta invalida. Use uno de estos codigos: {allowed}",
        )

    upload = session.scalar(
        select(Upload)
        .options(selectinload(Upload.survey).selectinload(Survey.responses))
        .where(Upload.id == upload_id)
    )
    if upload is None or upload.survey is None:
        raise HTTPException(status_code=404, detail="Encuesta procesada no encontrada")
    response = next(
        (
            item
            for item in upload.survey.responses
            if item.question_number == question_number
        ),
        None,
    )
    if response is None:
        raise HTTPException(status_code=404, detail="Pregunta no encontrada")
    if response.status == "not_applicable":
        raise HTTPException(
            status_code=409, detail="La pregunta no aplica a esta encuesta"
        )

    corrected_at = utc_now()
    apply_manual_answer(response, option[0], corrected_at)
    recalculate_upload_review_state(upload)
    session.commit()
    return _upload_payload(upload, include_responses=True)


@app.get("/api/uploads/{upload_id}/file")
def original_pdf(
    upload_id: int, session: Session = Depends(_database_dependency)
) -> FileResponse:
    upload = session.get(Upload, upload_id)
    if upload is None or not Path(upload.stored_path).is_file():
        raise HTTPException(status_code=404, detail="PDF no encontrado")
    return FileResponse(
        upload.stored_path,
        media_type="application/pdf",
        filename=upload.original_filename,
    )


@app.delete("/api/uploads/{upload_id}")
def delete_upload(
    upload_id: int, session: Session = Depends(_database_dependency)
) -> dict:
    upload = session.scalar(
        select(Upload).where(Upload.id == upload_id).with_for_update()
    )
    if upload is None:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    if upload.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=409,
            detail="Espere a que termine el procesamiento antes de eliminar la encuesta",
        )

    stored_path = Path(upload.stored_path).resolve()
    upload_root = settings.upload_dir.resolve()
    try:
        stored_path.relative_to(upload_root)
        can_delete_file = True
    except ValueError:
        can_delete_file = False
        logger.error(
            "Upload %s references a file outside the configured upload directory",
            upload_id,
        )

    session.delete(upload)
    session.commit()

    file_deleted = False
    if can_delete_file:
        try:
            stored_path.unlink(missing_ok=True)
            file_deleted = True
        except OSError:
            # The database deletion succeeded; leave a diagnostic for manual cleanup.
            logger.exception("Could not delete stored PDF for upload %s", upload_id)
    return {
        "deleted": True,
        "upload_id": upload_id,
        "file_deleted": file_deleted,
    }


@app.post("/api/uploads/{upload_id}/reprocess", status_code=202)
def reprocess_upload(
    upload_id: int, session: Session = Depends(_database_dependency)
) -> dict:
    upload = session.get(Upload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Carga no encontrada")
    if upload.status in {"queued", "processing"}:
        return _upload_payload(upload)
    upload.status = "queued"
    upload.error_message = None
    upload.completed_at = None
    session.commit()
    processing_manager.submit(upload.id)
    return _upload_payload(upload)


@app.get("/api/stats")
def stats(session: Session = Depends(_database_dependency)) -> dict:
    rows = session.execute(
        select(Upload.status, func.count(Upload.id)).group_by(Upload.status)
    ).all()
    by_status = {name: count for name, count in rows}
    return {
        "total": sum(by_status.values()),
        "completed": by_status.get("completed", 0),
        "needs_review": by_status.get("needs_review", 0),
        "error": by_status.get("error", 0),
        "pending": by_status.get("queued", 0) + by_status.get("processing", 0),
    }


@app.get("/api/analytics")
def analytics(session: Session = Depends(_database_dependency)) -> dict:
    included_statuses = ("completed", "needs_review")
    survey_count = session.scalar(
        select(func.count(Survey.id))
        .join(Upload, Survey.upload_id == Upload.id)
        .where(Upload.status.in_(included_statuses), Survey.form_type == "A")
    ) or 0
    rows = session.execute(
        select(
            SurveyResponse.question_number,
            SurveyResponse.status,
            SurveyResponse.answer_code,
        )
        .select_from(SurveyResponse)
        .join(Survey, SurveyResponse.survey_id == Survey.id)
        .join(Upload, Survey.upload_id == Upload.id)
        .where(Upload.status.in_(included_statuses), Survey.form_type == "A")
    ).all()
    return summarize_responses(rows, survey_count)


def _export_value(response: SurveyResponse | None, value_format: str) -> str:
    if response is None:
        return ""
    if response.status == "not_applicable":
        return "N/A"
    if response.status != "answered":
        return f"[{response.status.upper()}]"
    return response.answer_code if value_format == "codes" else (response.answer_label or "")


@app.get("/api/export.csv")
def export_csv(
    value_format: str = Query("labels", pattern="^(labels|codes)$"),
    session: Session = Depends(_database_dependency),
) -> StreamingResponse:
    surveys = session.scalars(
        select(Survey)
        .options(selectinload(Survey.upload), selectinload(Survey.responses))
        .order_by(Survey.created_at, Survey.id)
    ).all()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "upload_id",
            "archivo",
            "id_respondiente",
            "estado",
            "atiende_clientes",
            "es_jefe",
            "respuestas_detectadas",
            "respuestas_esperadas",
        ]
        + [f"P{number}" for number in range(1, 124)]
    )
    for survey in surveys:
        by_number = {response.question_number: response for response in survey.responses}
        writer.writerow(
            [
                survey.upload_id,
                survey.upload.original_filename,
                survey.respondent_identifier or "",
                survey.upload.status,
                (
                    "SI"
                    if survey.serves_customers
                    else "NO" if survey.serves_customers is False else ""
                ),
                "SI" if survey.is_manager else "NO" if survey.is_manager is False else "",
                survey.answered_count,
                survey.expected_count,
            ]
            + [
                _export_value(by_number.get(number), value_format)
                for number in range(1, 124)
            ]
        )
    data = "\ufeff" + output.getvalue()
    return StreamingResponse(
        iter([data.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=encuestas_salud.csv"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
