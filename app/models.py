from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Upload(Base):
    __tablename__ = "survey_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(700), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    page_count: Mapped[int | None] = mapped_column(SmallInteger)
    extraction_method: Mapped[str | None] = mapped_column(String(40))
    detected_answers: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    expected_answers: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    warnings_json: Mapped[list[str] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    survey: Mapped["Survey | None"] = relationship(
        back_populates="upload", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (Index("ix_survey_uploads_status_created", "status", "created_at"),)


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("survey_uploads.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    respondent_identifier: Mapped[str | None] = mapped_column(String(120), index=True)
    form_type: Mapped[str] = mapped_column(String(10), nullable=False, default="A")
    serves_customers: Mapped[bool | None] = mapped_column(Boolean)
    is_manager: Mapped[bool | None] = mapped_column(Boolean)
    answered_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    expected_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    upload: Mapped[Upload] = relationship(back_populates="survey")
    responses: Mapped[list["SurveyResponse"]] = relationship(
        back_populates="survey",
        cascade="all, delete-orphan",
        order_by="SurveyResponse.question_number",
    )


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(
        ForeignKey("surveys.id", ondelete="CASCADE"), nullable=False
    )
    question_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    answer_code: Mapped[str | None] = mapped_column(String(24))
    answer_label: Mapped[str | None] = mapped_column(String(40))
    answer_position: Mapped[int | None] = mapped_column(SmallInteger)
    page_number: Mapped[int | None] = mapped_column(SmallInteger)
    confidence: Mapped[float | None] = mapped_column(Float)
    extraction_method: Mapped[str | None] = mapped_column(String(40))
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    survey: Mapped[Survey] = relationship(back_populates="responses")

    __table_args__ = (
        UniqueConstraint("survey_id", "question_number", name="uq_survey_question"),
        Index("ix_survey_responses_question_answer", "question_number", "answer_code"),
    )
