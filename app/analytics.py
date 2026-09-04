from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.questionnaire import ANSWER_OPTIONS


OFFICIAL_MANUAL_URL = (
    "https://www.fondoriesgoslaborales.gov.co/wp-content/uploads/2025/06/"
    "2.-Manual-evaluacion-de-factores-de-riesgo-psicosociales-"
    "intralaboral-forma-AyB.pdf"
)


@dataclass(frozen=True, slots=True)
class DimensionDefinition:
    key: str
    label: str
    domain_key: str
    questions: tuple[int, ...]


DOMAIN_LABELS = {
    "leadership": "Liderazgo y relaciones sociales en el trabajo",
    "control": "Control sobre el trabajo",
    "demands": "Demandas del trabajo",
    "rewards": "Recompensas",
}


# Tabla 23 del Manual del usuario del cuestionario intralaboral, Forma A.
DIMENSIONS = (
    DimensionDefinition(
        "leadership_characteristics",
        "Características del liderazgo",
        "leadership",
        tuple(range(63, 76)),
    ),
    DimensionDefinition(
        "social_relations",
        "Relaciones sociales en el trabajo",
        "leadership",
        tuple(range(76, 90)),
    ),
    DimensionDefinition(
        "performance_feedback",
        "Retroalimentación del desempeño",
        "leadership",
        tuple(range(90, 95)),
    ),
    DimensionDefinition(
        "collaborator_relationship",
        "Relación con los colaboradores",
        "leadership",
        tuple(range(115, 124)),
    ),
    DimensionDefinition(
        "role_clarity",
        "Claridad de rol",
        "control",
        tuple(range(53, 60)),
    ),
    DimensionDefinition(
        "training",
        "Capacitación",
        "control",
        tuple(range(60, 63)),
    ),
    DimensionDefinition(
        "change_participation",
        "Participación y manejo del cambio",
        "control",
        (48, 49, 50, 51),
    ),
    DimensionDefinition(
        "skills_opportunities",
        "Oportunidades para el uso y desarrollo de habilidades y conocimientos",
        "control",
        (39, 40, 41, 42),
    ),
    DimensionDefinition(
        "work_control",
        "Control y autonomía sobre el trabajo",
        "control",
        (44, 45, 46),
    ),
    DimensionDefinition(
        "environmental_demands",
        "Demandas ambientales y de esfuerzo físico",
        "demands",
        tuple(range(1, 13)),
    ),
    DimensionDefinition(
        "emotional_demands",
        "Demandas emocionales",
        "demands",
        tuple(range(106, 115)),
    ),
    DimensionDefinition(
        "quantitative_demands",
        "Demandas cuantitativas",
        "demands",
        (13, 14, 15, 32, 43, 47),
    ),
    DimensionDefinition(
        "work_life_influence",
        "Influencia del trabajo sobre el entorno extralaboral",
        "demands",
        (35, 36, 37, 38),
    ),
    DimensionDefinition(
        "responsibility_demands",
        "Exigencias de responsabilidad del cargo",
        "demands",
        (19, 22, 23, 24, 25, 26),
    ),
    DimensionDefinition(
        "mental_load",
        "Demandas de carga mental",
        "demands",
        (16, 17, 18, 20, 21),
    ),
    DimensionDefinition(
        "role_consistency",
        "Consistencia del rol",
        "demands",
        (27, 28, 29, 30, 52),
    ),
    DimensionDefinition(
        "workday_demands",
        "Demandas de la jornada de trabajo",
        "demands",
        (31, 33, 34),
    ),
    DimensionDefinition(
        "belonging_rewards",
        "Recompensas derivadas de la pertenencia y del trabajo realizado",
        "rewards",
        (95, 102, 103, 104, 105),
    ),
    DimensionDefinition(
        "recognition_compensation",
        "Reconocimiento y compensación",
        "rewards",
        (96, 97, 98, 99, 100, 101),
    ),
)


QUESTION_TO_DIMENSION: dict[int, DimensionDefinition] = {}
for dimension in DIMENSIONS:
    for question_number in dimension.questions:
        if question_number in QUESTION_TO_DIMENSION:
            raise RuntimeError(f"La pregunta {question_number} aparece en dos dimensiones")
        QUESTION_TO_DIMENSION[question_number] = dimension

if set(QUESTION_TO_DIMENSION) != set(range(1, 124)):
    raise RuntimeError("El mapa oficial de dimensiones no cubre las 123 preguntas")


def _new_bucket() -> dict[str, Any]:
    return {
        "categories": {code: 0 for code, _label, _position in ANSWER_OPTIONS},
        "answered": 0,
        "review": 0,
        "not_applicable": 0,
        "records": 0,
    }


def _add_response(bucket: dict[str, Any], status: str, answer_code: str | None) -> None:
    bucket["records"] += 1
    if status == "not_applicable":
        bucket["not_applicable"] += 1
        return
    if status == "answered" and answer_code in bucket["categories"]:
        bucket["categories"][answer_code] += 1
        bucket["answered"] += 1
        return
    bucket["review"] += 1


def _percentage(value: int, denominator: int) -> float:
    return round(value / denominator * 100, 1) if denominator else 0.0


def _finalize_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    answered = int(bucket["answered"])
    review = int(bucket["review"])
    applicable = answered + review
    return {
        "answered": answered,
        "review": review,
        "not_applicable": int(bucket["not_applicable"]),
        "applicable": applicable,
        "coverage_percent": _percentage(answered, applicable) if applicable else None,
        "categories": [
            {
                "code": code,
                "label": label,
                "count": int(bucket["categories"][code]),
                "percent": _percentage(int(bucket["categories"][code]), answered),
            }
            for code, label, _position in ANSWER_OPTIONS
        ],
    }


def summarize_responses(
    records: Iterable[tuple[int, str, str | None]], survey_count: int
) -> dict[str, Any]:
    overall = _new_bucket()
    domain_buckets = {key: _new_bucket() for key in DOMAIN_LABELS}
    dimension_buckets = {definition.key: _new_bucket() for definition in DIMENSIONS}
    unmapped_records = 0

    for question_number, status, answer_code in records:
        dimension = QUESTION_TO_DIMENSION.get(int(question_number))
        if dimension is None:
            unmapped_records += 1
            continue
        _add_response(overall, status, answer_code)
        _add_response(domain_buckets[dimension.domain_key], status, answer_code)
        _add_response(dimension_buckets[dimension.key], status, answer_code)

    overall_summary = _finalize_bucket(overall)
    domains = []
    for key, label in DOMAIN_LABELS.items():
        domain = _finalize_bucket(domain_buckets[key])
        question_count = sum(
            len(definition.questions)
            for definition in DIMENSIONS
            if definition.domain_key == key
        )
        domain.update({"key": key, "label": label, "question_count": question_count})
        domains.append(domain)

    dimensions = []
    for definition in DIMENSIONS:
        dimension = _finalize_bucket(dimension_buckets[definition.key])
        dimension.update(
            {
                "key": definition.key,
                "label": definition.label,
                "domain_key": definition.domain_key,
                "question_count": len(definition.questions),
            }
        )
        dimensions.append(dimension)

    return {
        "survey_count": int(survey_count),
        "answered_count": overall_summary["answered"],
        "review_count": overall_summary["review"],
        "not_applicable_count": overall_summary["not_applicable"],
        "applicable_count": overall_summary["applicable"],
        "coverage_percent": overall_summary["coverage_percent"],
        "response_categories": overall_summary["categories"],
        "domains": domains,
        "dimensions": dimensions,
        "unmapped_records": unmapped_records,
        "methodology": (
            "Los porcentajes usan solo respuestas detectadas. Los valores no aplicables "
            "y los pendientes de revisión se muestran aparte. No representan nivel de riesgo."
        ),
        "source": {
            "label": "Manual del usuario, Tabla 23",
            "url": OFFICIAL_MANUAL_URL,
        },
    }
