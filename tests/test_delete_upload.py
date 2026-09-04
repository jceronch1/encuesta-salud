from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.database import Base
from app.main import delete_upload
from app.models import Survey, SurveyResponse, Upload


def _engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.mark.parametrize("answered_count", [0, 2])
def test_delete_upload_removes_blank_or_answered_survey_and_pdf(
    tmp_path, monkeypatch, answered_count: int
) -> None:
    upload_root = tmp_path / "uploads"
    stored_pdf = upload_root / "2026" / "09" / f"survey-{answered_count}.pdf"
    stored_pdf.parent.mkdir(parents=True)
    stored_pdf.write_bytes(b"%PDF-test")
    monkeypatch.setattr(
        main_module, "settings", SimpleNamespace(upload_dir=upload_root)
    )

    with Session(_engine(), expire_on_commit=False) as session:
        upload = Upload(
            original_filename="blank.pdf" if answered_count == 0 else "answered.pdf",
            stored_path=str(stored_pdf),
            sha256=("a" if answered_count == 0 else "b") * 64,
            file_size=9,
            status="needs_review" if answered_count == 0 else "completed",
        )
        survey = Survey(
            upload=upload,
            form_type="A",
            respondent_identifier="TEST-DELETE",
            answered_count=answered_count,
            expected_count=2,
        )
        for number in range(1, 3):
            answered = number <= answered_count
            survey.responses.append(
                SurveyResponse(
                    question_number=number,
                    question_text=f"Pregunta {number}",
                    status="answered" if answered else "blank",
                    answer_code="A" if answered else None,
                    answer_label="Siempre" if answered else None,
                    answer_position=1 if answered else None,
                    raw_metadata={},
                )
            )
        session.add(upload)
        session.commit()
        upload_id = upload.id

        result = delete_upload(upload_id, session)

        assert result == {
            "deleted": True,
            "upload_id": upload_id,
            "file_deleted": True,
        }
        assert session.get(Upload, upload_id) is None
        assert session.scalar(select(func.count(Survey.id))) == 0
        assert session.scalar(select(func.count(SurveyResponse.id))) == 0
        assert not stored_pdf.exists()


@pytest.mark.parametrize("active_status", ["queued", "processing"])
def test_delete_upload_rejects_active_processing(
    tmp_path, monkeypatch, active_status: str
) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    stored_pdf = upload_root / "active.pdf"
    stored_pdf.write_bytes(b"%PDF-test")
    monkeypatch.setattr(
        main_module, "settings", SimpleNamespace(upload_dir=upload_root)
    )

    with Session(_engine(), expire_on_commit=False) as session:
        upload = Upload(
            original_filename="active.pdf",
            stored_path=str(stored_pdf),
            sha256=("c" if active_status == "queued" else "d") * 64,
            file_size=9,
            status=active_status,
        )
        session.add(upload)
        session.commit()

        with pytest.raises(HTTPException) as raised:
            delete_upload(upload.id, session)

        assert raised.value.status_code == 409
        assert session.get(Upload, upload.id) is not None
        assert stored_pdf.exists()


def test_delete_upload_never_unlinks_a_path_outside_upload_storage(
    tmp_path, monkeypatch
) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside_pdf = tmp_path / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-test")
    monkeypatch.setattr(
        main_module, "settings", SimpleNamespace(upload_dir=upload_root)
    )

    with Session(_engine(), expire_on_commit=False) as session:
        upload = Upload(
            original_filename="outside.pdf",
            stored_path=str(outside_pdf),
            sha256="e" * 64,
            file_size=9,
            status="completed",
        )
        session.add(upload)
        session.commit()

        result = delete_upload(upload.id, session)

        assert result["deleted"] is True
        assert result["file_deleted"] is False
        assert session.get(Upload, upload.id) is None
        assert outside_pdf.exists()


def test_delete_upload_reports_when_windows_cannot_unlink_pdf(
    tmp_path, monkeypatch
) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    stored_pdf = upload_root / "locked.pdf"
    stored_pdf.write_bytes(b"%PDF-test")
    monkeypatch.setattr(
        main_module, "settings", SimpleNamespace(upload_dir=upload_root)
    )
    original_unlink = type(stored_pdf).unlink

    def fail_for_locked_pdf(path, *args, **kwargs):
        if path == stored_pdf:
            raise OSError("locked for test")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(stored_pdf), "unlink", fail_for_locked_pdf)

    with Session(_engine(), expire_on_commit=False) as session:
        upload = Upload(
            original_filename="locked.pdf",
            stored_path=str(stored_pdf),
            sha256="f" * 64,
            file_size=9,
            status="completed",
        )
        session.add(upload)
        session.commit()
        upload_id = upload.id

        result = delete_upload(upload_id, session)

        assert result == {
            "deleted": True,
            "upload_id": upload_id,
            "file_deleted": False,
        }
        assert session.get(Upload, upload_id) is None
        assert stored_pdf.exists()


def test_delete_upload_returns_not_found_for_unknown_id(tmp_path, monkeypatch) -> None:
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(
        main_module, "settings", SimpleNamespace(upload_dir=upload_root)
    )

    with Session(_engine(), expire_on_commit=False) as session:
        with pytest.raises(HTTPException) as raised:
            delete_upload(999, session)

    assert raised.value.status_code == 404
