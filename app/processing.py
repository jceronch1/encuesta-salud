from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal, ensure_schema
from app.models import Survey, SurveyResponse, Upload, utc_now
from app.omr import SurveyExtractionError, extract_survey
from app.review import (
    apply_manual_answer,
    apply_manual_identifier,
    manual_identifier_record,
    recalculate_upload_review_state,
)


logger = logging.getLogger(__name__)


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, SurveyExtractionError):
        return str(exc)[:2000]
    return "No fue posible procesar el PDF. Revise que el archivo no este danado."


def process_upload(upload_id: int) -> None:
    ensure_schema()
    session = SessionLocal()
    try:
        upload = session.get(Upload, upload_id)
        if upload is None:
            return
        upload.status = "processing"
        upload.started_at = utc_now()
        upload.error_message = None
        session.commit()

        result = extract_survey(Path(upload.stored_path))

        manual_corrections = {}
        preserved_identifier = None
        if upload.survey is not None:
            preserved_identifier = manual_identifier_record(upload)
            manual_corrections = {
                response.question_number: {
                    "answer_code": response.answer_code,
                    "raw_metadata": dict(response.raw_metadata or {}),
                }
                for response in upload.survey.responses
                if response.extraction_method == "manual_review"
                and response.answer_code is not None
            }

        # Reprocessing is idempotent: replace the normalized survey atomically.
        if upload.survey is not None:
            session.delete(upload.survey)
            session.flush()

        survey = Survey(
            upload=upload,
            respondent_identifier=(
                preserved_identifier["value"]
                if preserved_identifier is not None
                else result.respondent_identifier
            ),
            form_type=result.form_type,
            serves_customers=result.serves_customers,
            is_manager=result.is_manager,
            answered_count=result.answered_count,
            expected_count=result.expected_count,
        )
        session.add(survey)
        session.flush()

        for response in result.responses:
            stored_response = SurveyResponse(
                question_number=response.question_number,
                question_text=response.question_text,
                status=response.status,
                answer_code=response.answer_code,
                answer_label=response.answer_label,
                answer_position=response.answer_position,
                page_number=response.page_number,
                confidence=response.confidence,
                extraction_method=response.extraction_method,
                raw_metadata=response.raw_metadata,
            )
            correction = manual_corrections.get(response.question_number)
            if correction is not None and response.status != "not_applicable":
                metadata = dict(stored_response.raw_metadata or {})
                history = correction["raw_metadata"].get("manual_history")
                if isinstance(history, list):
                    metadata["manual_history"] = history
                stored_response.raw_metadata = metadata
                apply_manual_answer(
                    stored_response,
                    correction["answer_code"],
                    utc_now(),
                    source="manual_review",
                    append_history=False,
                )
            survey.responses.append(stored_response)

        upload.page_count = result.page_count
        upload.extraction_method = result.extraction_method
        upload.warnings_json = result.warnings
        if preserved_identifier is not None:
            apply_manual_identifier(
                upload,
                preserved_identifier["value"],
                utc_now(),
                append_history=False,
                preserved_record=preserved_identifier,
            )
        recalculate_upload_review_state(upload)
        upload.completed_at = utc_now()
        session.commit()
    except Exception as exc:  # worker boundary: persist failure, never kill the queue
        session.rollback()
        logger.exception("Upload %s failed", upload_id)
        failed_upload = session.get(Upload, upload_id)
        if failed_upload is not None:
            failed_upload.status = "error"
            failed_upload.error_message = _safe_error_message(exc)
            failed_upload.completed_at = utc_now()
            session.commit()
    finally:
        session.close()


class ProcessingManager:
    def __init__(self) -> None:
        settings = get_settings()
        self._executor = ThreadPoolExecutor(
            max_workers=settings.processing_workers,
            thread_name_prefix="survey-omr",
        )
        self._lock = threading.Lock()
        self._futures: dict[int, Future[None]] = {}

    def submit(self, upload_id: int) -> None:
        with self._lock:
            existing = self._futures.get(upload_id)
            if existing is not None and not existing.done():
                return
            future = self._executor.submit(process_upload, upload_id)
            self._futures[upload_id] = future
            future.add_done_callback(
                lambda _future, item_id=upload_id: self._discard(item_id)
            )

    def _discard(self, upload_id: int) -> None:
        with self._lock:
            self._futures.pop(upload_id, None)

    def recover_pending(self) -> None:
        ensure_schema()
        with SessionLocal() as session:
            pending = session.scalars(
                select(Upload).where(Upload.status.in_(("queued", "processing")))
            ).all()
            for upload in pending:
                upload.status = "queued"
            session.commit()
            ids = [upload.id for upload in pending]
        for upload_id in ids:
            self.submit(upload_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


processing_manager = ProcessingManager()
