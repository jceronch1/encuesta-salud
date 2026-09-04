from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.processing as processing
from app.database import Base
from app.main import (
    RespondentIdentifierRequest,
    ResponseCorrectionRequest,
    correct_response,
    update_respondent_identifier,
)
from app.models import Survey, SurveyResponse, Upload, utc_now
from app.review import (
    IDENTIFIER_WARNING,
    apply_manual_answer,
    apply_manual_identifier,
    detected_answer_codes,
    manual_identifier_record,
    recalculate_upload_review_state,
)


def test_manual_review_keeps_candidates_and_resolves_upload() -> None:
    upload = Upload(
        original_filename="scan.pdf",
        stored_path="scan.pdf",
        sha256="a" * 64,
        file_size=123,
        status="needs_review",
        warnings_json=["Hay 1 respuestas para revisar: 27"],
    )
    survey = Survey(upload=upload, form_type="A", respondent_identifier="TEST-1")
    response = SurveyResponse(
        question_number=27,
        question_text="En el trabajo me dan ordenes contradictorias",
        status="multiple",
        raw_metadata={"option_indexes": [2, 3]},
    )
    survey.responses.append(response)

    assert detected_answer_codes(response.raw_metadata) == ["C", "D"]
    apply_manual_answer(response, "D", utc_now())
    review_numbers = recalculate_upload_review_state(upload)

    assert response.status == "answered"
    assert response.answer_code == "D"
    assert response.answer_label == "Casi nunca"
    assert response.extraction_method == "manual_review"
    assert response.raw_metadata["option_indexes"] == [2, 3]
    assert response.raw_metadata["manual_history"][0]["previous_status"] == "multiple"
    assert review_numbers == []
    assert upload.status == "completed"
    assert upload.warnings_json == []


def test_correction_endpoint_updates_normalized_data_and_keeps_history() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        upload = Upload(
            original_filename="scan.pdf",
            stored_path="scan.pdf",
            sha256="b" * 64,
            file_size=123,
            status="needs_review",
            warnings_json=["Hay 1 respuestas para revisar: 27"],
        )
        survey = Survey(upload=upload, form_type="A", respondent_identifier="TEST-2")
        for number in range(1, 124):
            survey.responses.append(
                SurveyResponse(
                    question_number=number,
                    question_text=f"Pregunta {number}",
                    status="multiple" if number == 27 else "answered",
                    answer_code=None if number == 27 else "A",
                    answer_label=None if number == 27 else "Siempre",
                    answer_position=None if number == 27 else 1,
                    raw_metadata={"option_indexes": [2, 3]} if number == 27 else {},
                )
            )
        session.add(upload)
        session.commit()

        payload = correct_response(
            upload.id,
            27,
            ResponseCorrectionRequest(answer_code="D"),
            session,
        )

        corrected = next(
            item
            for item in payload["survey"]["responses"]
            if item["question_number"] == 27
        )
        assert payload["status"] == "completed"
        assert payload["detected_answers"] == 123
        assert corrected["answer_code"] == "D"
        assert corrected["detected_answer_codes"] == ["C", "D"]
        assert corrected["manually_reviewed"] is True

        stored = session.scalar(
            select(SurveyResponse).where(SurveyResponse.question_number == 27)
        )
        assert stored.raw_metadata["manual_history"][0]["selected_answer_code"] == "D"


def test_identifier_endpoint_resolves_only_the_identifier_warning() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        upload = Upload(
            original_filename="scan.pdf",
            stored_path="scan.pdf",
            sha256="c" * 64,
            file_size=123,
            status="needs_review",
            warnings_json=[
                "El PDF no tiene capa de texto; las marcas se leyeron desde el escaneo",
                IDENTIFIER_WARNING,
                "No se pudo determinar el filtro de jefatura",
                "Hay 1 respuestas para revisar: 27",
            ],
        )
        survey = Survey(upload=upload, form_type="A")
        for number in range(1, 124):
            survey.responses.append(
                SurveyResponse(
                    question_number=number,
                    question_text=f"Pregunta {number}",
                    status="multiple" if number == 27 else "answered",
                    answer_code=None if number == 27 else "A",
                    answer_label=None if number == 27 else "Siempre",
                    answer_position=None if number == 27 else 1,
                    raw_metadata={"option_indexes": [2, 3]} if number == 27 else {},
                )
            )
        session.add(upload)
        session.commit()

        payload = update_respondent_identifier(
            upload.id,
            RespondentIdentifierRequest(respondent_identifier=" 78534624 "),
            session,
        )

        assert payload["survey"]["respondent_identifier"] == "78534624"
        assert payload["survey"]["respondent_identifier_manual"] is True
        assert payload["status"] == "needs_review"
        assert IDENTIFIER_WARNING not in payload["warnings"]
        assert "No se pudo determinar el filtro de jefatura" in payload["warnings"]
        assert "Hay 1 respuestas para revisar: 27" in payload["warnings"]

        first_response = session.scalar(
            select(SurveyResponse).where(SurveyResponse.question_number == 1)
        )
        record = first_response.raw_metadata["manual_survey_fields"][
            "respondent_identifier"
        ]
        assert record["value"] == "78534624"
        assert record["history"][0]["previous_value"] is None
        assert record["history"][0]["selected_value"] == "78534624"


@pytest.mark.parametrize(
    "identifier",
    ["", "ID con espacios", "=FORMULA", "A" * 121],
)
def test_identifier_endpoint_rejects_invalid_values(identifier: str) -> None:
    with pytest.raises(HTTPException) as raised:
        update_respondent_identifier(
            1,
            RespondentIdentifierRequest(respondent_identifier=identifier),
            None,  # Validation happens before the database is accessed.
        )
    assert raised.value.status_code == 400


def test_manual_identifier_record_can_be_reapplied_after_processing() -> None:
    upload = Upload(
        original_filename="scan.pdf",
        stored_path="scan.pdf",
        sha256="d" * 64,
        file_size=123,
        status="needs_review",
        warnings_json=[IDENTIFIER_WARNING],
    )
    original_survey = Survey(upload=upload, form_type="A")
    original_survey.responses.append(
        SurveyResponse(
            question_number=1,
            question_text="Pregunta 1",
            status="answered",
            answer_code="A",
            answer_label="Siempre",
            answer_position=1,
            raw_metadata={},
        )
    )
    apply_manual_identifier(upload, "78534624", utc_now())
    preserved = manual_identifier_record(upload)

    replacement = Survey(upload=upload, form_type="A")
    replacement.responses.append(
        SurveyResponse(
            question_number=1,
            question_text="Pregunta 1",
            status="answered",
            answer_code="A",
            answer_label="Siempre",
            answer_position=1,
            raw_metadata={},
        )
    )
    upload.survey = replacement
    upload.warnings_json = [IDENTIFIER_WARNING]
    apply_manual_identifier(
        upload,
        preserved["value"],
        utc_now(),
        append_history=False,
        preserved_record=preserved,
    )

    reapplied = manual_identifier_record(upload)
    assert replacement.respondent_identifier == "78534624"
    assert reapplied["history"] == preserved["history"]
    assert reapplied["reapplied_after_processing"] is True
    assert IDENTIFIER_WARNING not in upload.warnings_json


def test_reprocess_preserves_a_manually_entered_identifier(monkeypatch) -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with session_factory() as session:
        upload = Upload(
            original_filename="scan.pdf",
            stored_path="scan.pdf",
            sha256="e" * 64,
            file_size=123,
            status="needs_review",
            warnings_json=[IDENTIFIER_WARNING],
        )
        survey = Survey(upload=upload, form_type="A")
        survey.responses.append(
            SurveyResponse(
                question_number=1,
                question_text="Pregunta 1",
                status="answered",
                answer_code="A",
                answer_label="Siempre",
                answer_position=1,
                extraction_method="omrchecker_raster_fallback",
                raw_metadata={},
            )
        )
        session.add(upload)
        session.flush()
        apply_manual_identifier(upload, "78534624", utc_now())
        session.commit()
        upload_id = upload.id

    extracted = SimpleNamespace(
        respondent_identifier=None,
        form_type="A",
        serves_customers=None,
        is_manager=None,
        answered_count=1,
        expected_count=123,
        page_count=4,
        extraction_method="omrchecker_raster_fallback",
        warnings=[IDENTIFIER_WARNING],
        responses=[
            SimpleNamespace(
                question_number=1,
                question_text="Pregunta 1",
                status="answered",
                answer_code="B",
                answer_label="Casi siempre",
                answer_position=2,
                page_number=1,
                confidence=0.95,
                extraction_method="omrchecker_raster_fallback",
                raw_metadata={},
            )
        ],
    )
    monkeypatch.setattr(processing, "SessionLocal", session_factory)
    monkeypatch.setattr(processing, "ensure_schema", lambda: None)
    monkeypatch.setattr(processing, "extract_survey", lambda _path: extracted)

    processing.process_upload(upload_id)

    with session_factory() as session:
        stored = session.scalar(
            select(Upload)
            .where(Upload.id == upload_id)
        )
        assert stored.status == "completed"
        assert stored.survey.respondent_identifier == "78534624"
        assert IDENTIFIER_WARNING not in stored.warnings_json
        assert manual_identifier_record(stored)["value"] == "78534624"
