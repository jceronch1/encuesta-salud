from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from dotmap import DotMap

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF < 1.24 compatibility
    import fitz  # type: ignore[no-redef]

from app.questionnaire import (
    ANSWER_OPTIONS,
    QUESTION_TEXTS,
    applicability,
    expected_question_numbers,
)
ANSWER_CENTER_RATIOS = (
    309.005 / 595.28,
    354.355 / 595.28,
    408.215 / 595.28,
    462.075 / 595.28,
    507.425 / 595.28,
)
ANSWER_CELL_BOUNDARY_RATIOS = tuple(
    value / 595.28
    for value in (289.1339, 328.8189, 379.8425, 436.5354, 487.5591, 527.2441)
)
REVIEW_STATUSES = {"blank", "multiple", "uncertain"}


class SurveyExtractionError(ValueError):
    """Raised when a file is not a supported questionnaire PDF."""


@dataclass(slots=True)
class AnswerDetection:
    question_number: int
    option_index: int | None
    page_number: int
    confidence: float
    status: str = "answered"
    method: str = "pdf_vector_geometry"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def option(self) -> tuple[str, str, int] | None:
        if self.option_index is None:
            return None
        return ANSWER_OPTIONS[self.option_index]


@dataclass(slots=True)
class NormalizedResponse:
    question_number: int
    question_text: str
    status: str
    answer_code: str | None
    answer_label: str | None
    answer_position: int | None
    page_number: int | None
    confidence: float | None
    extraction_method: str | None
    raw_metadata: dict[str, Any] | None


@dataclass(slots=True)
class ExtractionResult:
    respondent_identifier: str | None
    form_type: str
    page_count: int
    serves_customers: bool | None
    is_manager: bool | None
    responses: list[NormalizedResponse]
    warnings: list[str]
    extraction_method: str

    @property
    def answered_count(self) -> int:
        return sum(response.status == "answered" for response in self.responses)

    @property
    def expected_count(self) -> int:
        return len(expected_question_numbers(self.serves_customers, self.is_manager))

    @property
    def has_review_items(self) -> bool:
        return any(
            response.status in REVIEW_STATUSES
            for response in self.responses
            if applicability(
                response.question_number, self.serves_customers, self.is_manager
            )
            == "expected"
        )


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    asciiish = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", asciiish).strip().upper()


def _extract_identifier(text: str) -> str | None:
    patterns = (
        r"\(ID\)\s*:\s*([A-Za-z0-9._-]+)",
        r"IDENTIFICACION[^\n:]*\(ID\)[^\n:]*:?\s*([A-Za-z0-9._-]+)",
    )
    folded = _fold(text)
    for pattern in patterns:
        match = re.search(pattern, folded, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_gate(text: str, prompt_pattern: str) -> bool | None:
    folded = _fold(text)
    match = re.search(
        rf"{prompt_pattern}.{{0,100}}?\b(SI|NO)\s*\(X\)", folded, flags=re.DOTALL
    )
    if not match:
        return None
    return match.group(1) == "SI"


def _answer_index_for_x(x_center: float, page_width: float) -> tuple[int | None, float]:
    ratios = np.asarray(ANSWER_CENTER_RATIOS, dtype=float)
    distances = np.abs(ratios - (x_center / page_width))
    index = int(np.argmin(distances))
    distance = float(distances[index])
    # The generated form is exact. More than 2.5% of page width means the mark
    # does not belong to one of the answer columns.
    if distance > 0.025:
        return None, 0.0
    confidence = max(0.0, 1.0 - distance / 0.025)
    return index, round(confidence, 4)


def _vector_detections(document: fitz.Document) -> dict[int, AnswerDetection]:
    detections: dict[int, AnswerDetection] = {}
    for page_index, page in enumerate(document):
        words = page.get_text("words")
        question_words = []
        answer_marks = []

        for word in words:
            x0, y0, x1, y1, token = word[:5]
            clean = str(token).strip()
            if clean.isdigit() and x0 < page.rect.width * 0.105:
                number = int(clean)
                if 1 <= number <= 123:
                    question_words.append((number, (y0 + y1) / 2))
            if clean.upper() == "X" and x0 > page.rect.width * 0.45:
                answer_marks.append(((x0 + x1) / 2, (y0 + y1) / 2, word))

        for question_number, question_y in question_words:
            nearby = [
                mark
                for mark in answer_marks
                if abs(mark[1] - question_y) <= max(4.0, page.rect.height * 0.008)
            ]
            if not nearby:
                continue

            mapped = []
            for x_center, y_center, raw_word in nearby:
                option_index, confidence = _answer_index_for_x(x_center, page.rect.width)
                if option_index is not None:
                    mapped.append((option_index, confidence, x_center, y_center, raw_word))
            if not mapped:
                continue

            unique_options = sorted({item[0] for item in mapped})
            if len(unique_options) > 1:
                detections[question_number] = AnswerDetection(
                    question_number=question_number,
                    option_index=None,
                    page_number=page_index + 1,
                    confidence=min(item[1] for item in mapped),
                    status="multiple",
                    metadata={"option_indexes": unique_options},
                )
                continue

            best = max(mapped, key=lambda item: item[1])
            detections[question_number] = AnswerDetection(
                question_number=question_number,
                option_index=best[0],
                page_number=page_index + 1,
                confidence=best[1],
                metadata={
                    "x": round(best[2], 3),
                    "y": round(best[3], 3),
                },
            )
    return detections


def _cluster_positions(indexes: np.ndarray, max_gap: int = 3) -> list[int]:
    if indexes.size == 0:
        return []
    groups: list[list[int]] = [[int(indexes[0])]]
    for value in indexes[1:]:
        value = int(value)
        if value - groups[-1][-1] <= max_gap:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [int(round(float(np.mean(group)))) for group in groups]


def _find_table_groups(gray: np.ndarray) -> list[list[int]]:
    height, width = gray.shape[:2]
    block_size = max(15, int(round(width / 68)))
    if block_size % 2 == 0:
        block_size += 1
    inverted = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        12,
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, width // 12), 1))
    horizontal = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, kernel)
    left = int(width * 0.055)
    right = int(width * 0.9)
    projection = np.count_nonzero(horizontal[:, left:right], axis=1)
    candidates = np.flatnonzero(projection > (right - left) * 0.25)
    lines = _cluster_positions(candidates, max_gap=max(4, int(height * 0.0045)))
    if len(lines) < 2:
        return []

    typical_gap = float(np.median(np.diff(lines)))
    if typical_gap <= 0:
        return []

    # A genuinely separate conditional table has a much larger gap than a
    # wrapped question. Scans can lose a horizontal rule, so split only after
    # a gap large enough to contain more than two ordinary rows.
    split_gap = typical_gap * 3.2
    groups: list[list[int]] = [[lines[0]]]
    for y in lines[1:]:
        if y - groups[-1][-1] > split_gap:
            groups.append([y])
        else:
            groups[-1].append(y)

    repaired_groups: list[list[int]] = []
    for group in groups:
        if len(group) < 2:
            continue
        repaired = [group[0]]
        for top, bottom in zip(group, group[1:]):
            gap = bottom - top
            missing = (
                max(0, round(gap / typical_gap) - 1)
                if gap > typical_gap * 1.8
                else 0
            )
            repaired.extend(
                round(top + gap * (index + 1) / (missing + 1))
                for index in range(missing)
            )
            repaired.append(bottom)
        repaired_groups.append(repaired)
    return repaired_groups


def _find_answer_boundaries(gray: np.ndarray, group: list[int]) -> list[int]:
    height, width = gray.shape[:2]
    block_size = max(15, int(round(width / 68)))
    if block_size % 2 == 0:
        block_size += 1
    inverted = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        12,
    )
    top, bottom = group[0], group[-1]
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(15, (bottom - top) // 60))
    )
    vertical = cv2.morphologyEx(inverted, cv2.MORPH_OPEN, vertical_kernel)
    projection = np.count_nonzero(vertical[top:bottom, :], axis=0)
    candidates = np.flatnonzero(projection > (bottom - top) * 0.12)
    lines = _cluster_positions(candidates, max_gap=8)
    answer_lines = [x for x in lines if x > width * 0.45]
    if len(answer_lines) >= 6:
        return answer_lines[-6:]

    # The official form has fixed answer-column ratios. This fallback keeps a
    # damaged vertical rule from shifting all subsequent answers.
    return [round(ratio * width) for ratio in ANSWER_CELL_BOUNDARY_RATIOS]


def _score_answer_cells(
    gray: np.ndarray,
    top: int,
    bottom: int,
    boundaries: list[int],
) -> list[float]:
    """Return resolution-independent ink-component ratios for five cells."""
    scores: list[float] = []
    for left, right in zip(boundaries, boundaries[1:]):
        y_padding = int((bottom - top) * 0.25)
        x_padding = int((right - left) * 0.12)
        crop = gray[
            max(0, top + y_padding):min(gray.shape[0], bottom - y_padding),
            max(0, left + x_padding):min(gray.shape[1], right - x_padding),
        ]
        if not crop.size:
            scores.append(0.0)
            continue
        dark = (crop < 180).astype(np.uint8)
        component_count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
            dark, connectivity=8
        )
        largest = (
            int(np.max(stats[1:, cv2.CC_STAT_AREA]))
            if component_count > 1
            else 0
        )
        scores.append(largest / float(crop.size))
    return scores


def _raster_detections(
    pdf_path: Path,
    *,
    native_dpi: bool = False,
) -> dict[int, AnswerDetection]:
    # Image-only PDFs already contain a native scan and should not be inflated.
    # Vector PDFs with an incomplete text layer still need 200 DPI rendering.
    os.environ.setdefault("MPLBACKEND", "Agg")
    from src.utils.image import ImageUtils

    config = DotMap(
        {
            "pdf_params": {
                "pdf_dpi": "auto" if native_dpi else 200,
                "pdf_page": None,
            }
        },
        _dynamic=False,
    )
    rendered_pages = ImageUtils.load_omr_image(pdf_path, config)
    detections: dict[int, AnswerDetection] = {}
    next_question = 1

    for page_index, (_, gray) in enumerate(rendered_pages):
        if gray is None:
            continue
        for group in _find_table_groups(gray):
            boundaries = _find_answer_boundaries(gray, group)
            # Every table starts with one header interval.
            for row_index, (top, bottom) in enumerate(zip(group, group[1:])):
                if row_index == 0:
                    continue
                if next_question > 123:
                    break

                scores = _score_answer_cells(gray, top, bottom, boundaries)
                ordered = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
                top_index, top_score = ordered[0]
                second_score = ordered[1][1]
                baseline = float(np.median(scores))
                marked = [
                    index for index, score in enumerate(scores) if score - baseline >= 0.04
                ]
                metadata = {
                    "ink_component_ratios": [round(score, 4) for score in scores],
                    "row_bounds": [top, bottom],
                    "answer_boundaries": boundaries,
                }

                if len(marked) > 1:
                    metadata["option_indexes"] = marked
                    detection = AnswerDetection(
                        question_number=next_question,
                        option_index=None,
                        page_number=page_index + 1,
                        confidence=round(
                            min(
                                score - baseline
                                for score in scores
                                if score - baseline >= 0.04
                            ),
                            4,
                        ),
                        status="multiple",
                        method="omrchecker_raster_fallback",
                        metadata=metadata,
                    )
                elif not marked:
                    status = "blank" if top_score - baseline < 0.02 else "uncertain"
                    detection = AnswerDetection(
                        question_number=next_question,
                        option_index=None,
                        page_number=page_index + 1,
                        confidence=round(max(0.0, top_score - baseline), 4),
                        status=status,
                        method="omrchecker_raster_fallback",
                        metadata=metadata,
                    )
                else:
                    separation = min(1.0, max(0.0, top_score - second_score) / 0.08)
                    detection = AnswerDetection(
                        question_number=next_question,
                        option_index=top_index,
                        page_number=page_index + 1,
                        confidence=round(0.55 + 0.4 * separation, 4),
                        method="omrchecker_raster_fallback",
                        metadata=metadata,
                    )
                detections[next_question] = detection
                next_question += 1

    return detections


def _normalize_responses(
    detections: dict[int, AnswerDetection],
    serves_customers: bool | None,
    is_manager: bool | None,
) -> list[NormalizedResponse]:
    responses: list[NormalizedResponse] = []
    for question_number in range(1, 124):
        question_applicability = applicability(
            question_number, serves_customers, is_manager
        )
        detection = detections.get(question_number)

        if question_applicability == "not_applicable":
            responses.append(
                NormalizedResponse(
                    question_number=question_number,
                    question_text=QUESTION_TEXTS[question_number],
                    status="not_applicable",
                    answer_code=None,
                    answer_label=None,
                    answer_position=None,
                    page_number=None,
                    confidence=None,
                    extraction_method=None,
                    raw_metadata=None,
                )
            )
            continue

        if detection is None:
            responses.append(
                NormalizedResponse(
                    question_number=question_number,
                    question_text=QUESTION_TEXTS[question_number],
                    status="blank",
                    answer_code=None,
                    answer_label=None,
                    answer_position=None,
                    page_number=None,
                    confidence=None,
                    extraction_method=None,
                    raw_metadata=None,
                )
            )
            continue

        option = detection.option
        responses.append(
            NormalizedResponse(
                question_number=question_number,
                question_text=QUESTION_TEXTS[question_number],
                status=detection.status,
                answer_code=option[0] if option else None,
                answer_label=option[1] if option else None,
                answer_position=option[2] if option else None,
                page_number=detection.page_number,
                confidence=detection.confidence,
                extraction_method=detection.method,
                raw_metadata=detection.metadata,
            )
        )
    return responses


def extract_survey(pdf_path: str | Path) -> ExtractionResult:
    path = Path(pdf_path)
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise SurveyExtractionError("El archivo no es un PDF legible") from exc

    try:
        if document.needs_pass:
            raise SurveyExtractionError("El PDF esta protegido con contrasena")
        if document.page_count == 0:
            raise SurveyExtractionError("El PDF no contiene paginas")
        if document.page_count > 20:
            raise SurveyExtractionError(
                "El PDF tiene demasiadas paginas para un cuestionario Forma A"
            )

        full_text = "\n".join(page.get_text() for page in document)
        folded_text = _fold(full_text)
        has_form_header = (
            "FORMA A" in folded_text and "RIESGO PSICOSOCIAL" in folded_text
        )

        respondent_identifier = _extract_identifier(full_text)
        serves_customers = _extract_gate(
            full_text, r"BRINDAR SERVICIO A CLIENTES O USUARIOS"
        )
        is_manager = _extract_gate(
            full_text, r"SOY JEFE DE OTRAS PERSONAS EN MI TRABAJO"
        )
        vector = _vector_detections(document)
        page_count = document.page_count
    finally:
        document.close()

    expected = expected_question_numbers(serves_customers, is_manager)
    usable_vector = sum(
        number in expected and detection.status == "answered"
        for number, detection in vector.items()
    )
    detections = dict(vector)
    extraction_method = "pdf_vector_geometry"

    # Use the raster route only when the text layer is incomplete. Vector
    # detections always win because their page coordinates are deterministic.
    raster: dict[int, AnswerDetection] = {}
    if not has_form_header or usable_vector < max(1, int(len(expected) * 0.9)):
        raster = _raster_detections(path, native_dpi=not bool(full_text.strip()))
        if not has_form_header and len(raster) < 105:
            raise SurveyExtractionError(
                "El PDF no corresponde al cuestionario intralaboral Forma A"
            )
        for question_number, detection in raster.items():
            detections.setdefault(question_number, detection)
        extraction_method = (
            "hybrid_vector_raster" if vector else "omrchecker_raster_fallback"
        )

    responses = _normalize_responses(detections, serves_customers, is_manager)
    warnings: list[str] = []
    if not full_text.strip():
        warnings.append(
            "El PDF no tiene capa de texto; las marcas se leyeron desde el escaneo"
        )
    if respondent_identifier is None:
        warnings.append("No se pudo leer el ID del respondiente")
    if serves_customers is None:
        warnings.append("No se pudo determinar el filtro de atencion a clientes")
    if is_manager is None:
        warnings.append("No se pudo determinar el filtro de jefatura")

    review_numbers = [
        response.question_number
        for response in responses
        if response.question_number in expected
        and response.status in REVIEW_STATUSES
    ]
    if review_numbers:
        preview = ", ".join(str(number) for number in review_numbers[:12])
        suffix = "..." if len(review_numbers) > 12 else ""
        warnings.append(
            f"Hay {len(review_numbers)} respuestas para revisar: {preview}{suffix}"
        )

    return ExtractionResult(
        respondent_identifier=respondent_identifier,
        form_type="A",
        page_count=page_count,
        serves_customers=serves_customers,
        is_manager=is_manager,
        responses=responses,
        warnings=warnings,
        extraction_method=extraction_method,
    )
