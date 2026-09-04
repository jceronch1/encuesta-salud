from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

from app.omr import SurveyExtractionError, extract_survey
from app.questionnaire import QUESTION_TEXTS, applicability, expected_question_numbers


DEFAULT_SAMPLE = Path(
    r"C:\Users\usuario\Downloads\Cuestionario_Respuestas_Aleatorias (1).pdf"
)
SCANNED_SAMPLE = Path(r"C:\Users\usuario\Downloads\Scan_20260831_172406.pdf")


def sample_path() -> Path:
    return Path(os.getenv("SAMPLE_PDF", DEFAULT_SAMPLE))


@pytest.mark.skipif(not sample_path().is_file(), reason="PDF de aceptacion no disponible")
def test_attached_questionnaire_is_read_completely() -> None:
    result = extract_survey(sample_path())

    assert result.respondent_identifier == "653118"
    assert result.page_count == 4
    assert result.serves_customers is True
    assert result.is_manager is False
    assert result.answered_count == result.expected_count == 114
    assert result.extraction_method == "pdf_vector_geometry"
    assert not result.warnings

    answered = [response for response in result.responses if response.status == "answered"]
    assert Counter(response.answer_label for response in answered) == {
        "Siempre": 21,
        "Casi siempre": 16,
        "Algunas veces": 26,
        "Casi nunca": 24,
        "Nunca": 27,
    }
    assert result.responses[0].answer_code == "C"
    assert result.responses[113].answer_code == "B"
    assert all(
        response.status == "not_applicable" for response in result.responses[114:123]
    )


def test_questionnaire_catalog_and_conditions_cover_123_questions() -> None:
    assert set(QUESTION_TEXTS) == set(range(1, 124))
    assert len(expected_question_numbers(True, True)) == 123
    assert len(expected_question_numbers(True, False)) == 114
    assert len(expected_question_numbers(False, True)) == 114
    assert len(expected_question_numbers(False, False)) == 105
    assert applicability(106, False, True) == "not_applicable"
    assert applicability(115, True, False) == "not_applicable"


@pytest.mark.skipif(not SCANNED_SAMPLE.is_file(), reason="Escaneo de aceptacion no disponible")
def test_image_only_scan_preserves_every_multiple_mark_for_manual_review() -> None:
    result = extract_survey(SCANNED_SAMPLE)

    assert result.page_count == 4
    assert result.extraction_method == "omrchecker_raster_fallback"
    assert result.answered_count == 121
    assert result.expected_count == 123
    assert result.has_review_items

    question_27 = result.responses[26]
    assert question_27.status == "multiple"
    assert question_27.answer_code is None
    assert question_27.raw_metadata["option_indexes"] == [2, 3]

    # The same general rule also catches another duplicated row in this scan.
    question_36 = result.responses[35]
    assert question_36.status == "multiple"
    assert question_36.raw_metadata["option_indexes"] == [0, 1]
    assert "Hay 2 respuestas para revisar: 27, 36" in result.warnings


def test_rejects_non_pdf(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.pdf"
    invalid.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(SurveyExtractionError, match="PDF legible"):
        extract_survey(invalid)
