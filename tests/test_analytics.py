from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.analytics import DIMENSIONS, DOMAIN_LABELS, QUESTION_TO_DIMENSION, summarize_responses
from app.omr import extract_survey


DEFAULT_SAMPLE = Path(
    r"C:\Users\usuario\Downloads\Cuestionario_Respuestas_Aleatorias (1).pdf"
)


def sample_path() -> Path:
    return Path(os.getenv("SAMPLE_PDF", DEFAULT_SAMPLE))


def _category_counts(bucket: dict) -> dict[str, int]:
    return {item["code"]: item["count"] for item in bucket["categories"]}


def test_official_catalog_partitions_form_a_questions() -> None:
    assert len(DIMENSIONS) == 19
    assert set(QUESTION_TO_DIMENSION) == set(range(1, 124))
    assert list(DOMAIN_LABELS) == ["leadership", "control", "demands", "rewards"]

    totals = {
        domain_key: sum(
            len(dimension.questions)
            for dimension in DIMENSIONS
            if dimension.domain_key == domain_key
        )
        for domain_key in DOMAIN_LABELS
    }
    assert totals == {"leadership": 41, "control": 21, "demands": 50, "rewards": 11}


def test_review_and_not_applicable_are_outside_answer_percentages() -> None:
    summary = summarize_responses(
        [(1, "answered", "A"), (2, "blank", None), (106, "not_applicable", None)],
        survey_count=1,
    )

    assert summary["answered_count"] == 1
    assert summary["review_count"] == 1
    assert summary["not_applicable_count"] == 1
    assert summary["applicable_count"] == 2
    assert summary["coverage_percent"] == 50.0
    assert _category_counts({"categories": summary["response_categories"]}) == {
        "A": 1,
        "B": 0,
        "C": 0,
        "D": 0,
        "E": 0,
    }
    assert summary["response_categories"][0]["percent"] == 100.0
    emotional = next(
        dimension
        for dimension in summary["dimensions"]
        if dimension["key"] == "emotional_demands"
    )
    assert emotional["answered"] == emotional["review"] == 0
    assert emotional["not_applicable"] == 1
    assert emotional["coverage_percent"] is None


def test_invalid_answer_code_is_sent_to_review() -> None:
    summary = summarize_responses([(1, "answered", "Z")], survey_count=1)

    assert summary["answered_count"] == 0
    assert summary["review_count"] == 1
    assert summary["coverage_percent"] == 0.0


@pytest.mark.skipif(not sample_path().is_file(), reason="PDF de aceptacion no disponible")
def test_sample_pdf_statistics_reconcile_with_extraction() -> None:
    result = extract_survey(sample_path())
    records = [
        (response.question_number, response.status, response.answer_code)
        for response in result.responses
    ]
    summary = summarize_responses(records, survey_count=1)

    assert summary["survey_count"] == 1
    assert summary["answered_count"] == 114
    assert summary["review_count"] == 0
    assert summary["not_applicable_count"] == 9
    assert summary["coverage_percent"] == 100.0
    assert _category_counts({"categories": summary["response_categories"]}) == {
        "A": 21,
        "B": 16,
        "C": 26,
        "D": 24,
        "E": 27,
    }

    domains = {domain["key"]: domain for domain in summary["domains"]}
    assert {key: domain["answered"] for key, domain in domains.items()} == {
        "leadership": 32,
        "control": 21,
        "demands": 50,
        "rewards": 11,
    }
    assert domains["leadership"]["not_applicable"] == 9
    assert _category_counts(domains["leadership"]) == {
        "A": 6,
        "B": 5,
        "C": 5,
        "D": 8,
        "E": 8,
    }
    assert _category_counts(domains["control"]) == {
        "A": 4,
        "B": 4,
        "C": 4,
        "D": 5,
        "E": 4,
    }
    assert _category_counts(domains["demands"]) == {
        "A": 10,
        "B": 6,
        "C": 16,
        "D": 9,
        "E": 9,
    }
    assert _category_counts(domains["rewards"]) == {
        "A": 1,
        "B": 1,
        "C": 1,
        "D": 2,
        "E": 6,
    }

    buckets = [
        (summary["response_categories"], summary["answered_count"]),
        *[(domain["categories"], domain["answered"]) for domain in domains.values()],
    ]
    for categories, answered in buckets:
        assert sum(item["count"] for item in categories) == answered
        assert sum(item["percent"] for item in categories) == pytest.approx(
            100.0, abs=0.3
        )
