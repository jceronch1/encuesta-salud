from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import SurveyResponse, Upload
from app.omr import REVIEW_STATUSES
from app.questionnaire import ANSWER_OPTIONS, applicability, expected_question_numbers


IDENTIFIER_WARNING = "No se pudo leer el ID del respondiente"
MANUAL_SURVEY_FIELDS_KEY = "manual_survey_fields"


def answer_option(answer_code: str) -> tuple[str, str, int] | None:
    normalized = answer_code.strip().upper()
    return next((option for option in ANSWER_OPTIONS if option[0] == normalized), None)


def detected_answer_codes(raw_metadata: dict[str, Any] | None) -> list[str]:
    indexes = (raw_metadata or {}).get("option_indexes", [])
    if not isinstance(indexes, list):
        return []
    return [
        ANSWER_OPTIONS[index][0]
        for index in indexes
        if isinstance(index, int) and 0 <= index < len(ANSWER_OPTIONS)
    ]


def detected_answer_labels(raw_metadata: dict[str, Any] | None) -> list[str]:
    codes = set(detected_answer_codes(raw_metadata))
    return [label for code, label, _position in ANSWER_OPTIONS if code in codes]


def apply_manual_answer(
    response: SurveyResponse,
    answer_code: str,
    corrected_at: datetime,
    *,
    source: str = "manual_review",
    append_history: bool = True,
) -> None:
    option = answer_option(answer_code)
    if option is None:
        raise ValueError("Codigo de respuesta invalido")

    metadata = dict(response.raw_metadata or {})
    if append_history:
        history = list(metadata.get("manual_history", []))
        history.append(
            {
                "corrected_at": corrected_at.isoformat(timespec="seconds") + "Z",
                "previous_status": response.status,
                "previous_answer_code": response.answer_code,
                "selected_answer_code": option[0],
                "source": source,
            }
        )
        metadata["manual_history"] = history
    else:
        metadata["manual_correction_reapplied"] = True

    response.status = "answered"
    response.answer_code = option[0]
    response.answer_label = option[1]
    response.answer_position = option[2]
    response.confidence = None
    response.extraction_method = source
    response.raw_metadata = metadata


def manual_identifier_record(upload: Upload) -> dict[str, Any] | None:
    """Return the persisted manual identifier record, if this survey has one."""
    survey = upload.survey
    if survey is None:
        return None
    first_response = next(
        (response for response in survey.responses if response.question_number == 1),
        None,
    )
    if first_response is None:
        return None
    fields = (first_response.raw_metadata or {}).get(MANUAL_SURVEY_FIELDS_KEY)
    if not isinstance(fields, dict):
        return None
    record = fields.get("respondent_identifier")
    if not isinstance(record, dict):
        return None
    value = record.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    return dict(record)


def apply_manual_identifier(
    upload: Upload,
    identifier: str,
    corrected_at: datetime,
    *,
    append_history: bool = True,
    preserved_record: dict[str, Any] | None = None,
) -> None:
    """Persist a manual identifier without changing any normalized answer."""
    survey = upload.survey
    if survey is None:
        raise ValueError("La carga no tiene una encuesta procesada")

    normalized = identifier.strip()
    previous_value = survey.respondent_identifier
    survey.respondent_identifier = normalized

    first_response = next(
        (response for response in survey.responses if response.question_number == 1),
        None,
    )
    if first_response is not None:
        metadata = dict(first_response.raw_metadata or {})
        fields = dict(metadata.get(MANUAL_SURVEY_FIELDS_KEY) or {})
        record = dict(preserved_record or fields.get("respondent_identifier") or {})
        history = list(record.get("history") or [])
        if append_history:
            history.append(
                {
                    "corrected_at": corrected_at.isoformat(timespec="seconds") + "Z",
                    "previous_value": previous_value,
                    "selected_value": normalized,
                    "source": "manual_review",
                }
            )
        record.update(
            {
                "value": normalized,
                "source": "manual_review",
                "history": history,
            }
        )
        if not append_history:
            record["reapplied_after_processing"] = True
        fields["respondent_identifier"] = record
        metadata[MANUAL_SURVEY_FIELDS_KEY] = fields
        # Assign fresh dictionaries so SQLAlchemy detects the JSON mutation.
        first_response.raw_metadata = metadata

    upload.warnings_json = [
        warning
        for warning in (upload.warnings_json or [])
        if warning != IDENTIFIER_WARNING
    ]
    upload.warning_count = len(upload.warnings_json)


def _is_review_warning(warning: str) -> bool:
    return warning.startswith("Hay ") and " respuestas para revisar:" in warning


def review_question_numbers(upload: Upload) -> list[int]:
    survey = upload.survey
    if survey is None:
        return []
    return [
        response.question_number
        for response in survey.responses
        if response.status in REVIEW_STATUSES
        and applicability(
            response.question_number,
            survey.serves_customers,
            survey.is_manager,
        )
        == "expected"
    ]


def recalculate_upload_review_state(upload: Upload) -> list[int]:
    survey = upload.survey
    if survey is None:
        return []

    survey.answered_count = sum(
        response.status == "answered" for response in survey.responses
    )
    survey.expected_count = len(
        expected_question_numbers(survey.serves_customers, survey.is_manager)
    )
    upload.detected_answers = survey.answered_count
    upload.expected_answers = survey.expected_count

    review_numbers = review_question_numbers(upload)
    warnings = [
        warning
        for warning in (upload.warnings_json or [])
        if not _is_review_warning(warning) and warning != IDENTIFIER_WARNING
    ]
    missing_identifier = not bool((survey.respondent_identifier or "").strip())
    if missing_identifier:
        warnings.append(IDENTIFIER_WARNING)
    if review_numbers:
        preview = ", ".join(str(number) for number in review_numbers[:12])
        suffix = "..." if len(review_numbers) > 12 else ""
        warnings.append(
            f"Hay {len(review_numbers)} respuestas para revisar: {preview}{suffix}"
        )
    upload.warnings_json = warnings
    upload.warning_count = len(warnings)
    upload.status = "needs_review" if review_numbers or missing_identifier else "completed"
    return review_numbers
