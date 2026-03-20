from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import utc_now
from app.models import StudyEvent, StudySession, StudySubmission, StudyTask, SurveyResponse
from app.services.catalog import get_dataset_version_or_404, get_sample_detail
from app.services.reports import create_report


def _participant_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def create_task(
    db: Session,
    *,
    title: str,
    description: str,
    dataset_version_slug: str | None,
    split: str | None,
    sample_id: str | None,
    default_condition: str,
    system_outputs: dict[str, str],
) -> StudyTask:
    materials: dict[str, Any] = {}
    if dataset_version_slug and split and sample_id:
        dataset = get_dataset_version_or_404(db, dataset_version_slug)
        sample = get_sample_detail(dataset, split, sample_id)
        materials = {
            "sample": sample,
            "input_transcript": "\n".join(
                [f"{turn.get('role', 'Unknown')}: {turn.get('utterance', '')}" for turn in sample["dialogue"]]
            ),
            "reference_code": sample["code"],
        }

    task = StudyTask(
        title=title,
        description=description,
        dataset_version_slug=dataset_version_slug,
        split=split,
        sample_id=sample_id,
        default_condition=default_condition,
        materials_json=materials,
        system_outputs_json=system_outputs,
    )
    db.add(task)
    db.flush()
    return task


def list_tasks(db: Session) -> list[StudyTask]:
    return db.scalars(select(StudyTask).order_by(StudyTask.created_at.desc())).all()


def get_task_or_404(db: Session, task_id: str) -> StudyTask:
    task = db.get(StudyTask, task_id)
    if task is None:
        raise ValueError(f"study task not found: {task_id}")
    return task


def create_study_session(
    db: Session,
    *,
    task: StudyTask,
    participant_id: str,
    study_condition: str,
    participant_code: str | None = None,
) -> StudySession:
    code = participant_code or _participant_code()
    session = StudySession(
        participant_code=code,
        task_id=task.id,
        participant_id=participant_id,
        study_condition=study_condition,
        status="pending",
        system_output=str(task.system_outputs_json.get(study_condition, "")) or None,
    )
    db.add(session)
    db.flush()
    return session


def list_study_sessions(db: Session) -> list[StudySession]:
    return db.scalars(select(StudySession).order_by(StudySession.created_at.desc())).all()


def get_session_by_code_or_404(db: Session, participant_code: str) -> StudySession:
    session = db.scalar(select(StudySession).where(StudySession.participant_code == participant_code))
    if session is None:
        raise ValueError(f"study session not found for code: {participant_code}")
    return session


def touch_session(session: StudySession) -> None:
    now = utc_now()
    if session.started_at is None:
        session.started_at = now
    session.last_active_at = now
    if session.status == "pending":
        session.status = "active"


def add_study_event(db: Session, *, session_id: str, event_type: str, payload: dict[str, Any]) -> StudyEvent:
    event = StudyEvent(study_session_id=session_id, event_type=event_type, payload=payload)
    db.add(event)
    db.flush()
    return event


def update_draft(
    db: Session,
    *,
    session: StudySession,
    draft_output: str,
    input_transcript: str | None,
) -> StudySession:
    touch_session(session)
    session.draft_output = draft_output
    if input_transcript is not None:
        session.input_transcript = input_transcript
    add_study_event(db, session_id=session.id, event_type="autosave", payload={"draft_length": len(draft_output)})
    return session


def submit_session(
    db: Session,
    *,
    session: StudySession,
    final_output: str,
    input_transcript: str | None,
) -> StudySession:
    if session.status == "submitted":
        raise ValueError("study session already submitted")
    touch_session(session)
    session.status = "submitted"
    session.final_output = final_output
    session.ended_at = utc_now()
    if input_transcript is not None:
        session.input_transcript = input_transcript

    reference_code = None
    if session.task_id:
        task = db.get(StudyTask, session.task_id)
        if task is not None:
            reference_code = task.materials_json.get("reference_code")

    compile_success = None
    auto_metrics: dict[str, Any] = {}
    if reference_code:
        from app.legacy import maybe_compile_mermaid
        from tools.eval.metrics import score_prediction

        auto_metrics = score_prediction(
            reference_code=str(reference_code),
            predicted_code=final_output,
            declared_diagram_type=str(task.materials_json.get("sample", {}).get("diagram_type", "unknown")),
        )
        compile_payload = maybe_compile_mermaid(final_output)
        if compile_payload is not None:
            auto_metrics["compile_payload"] = compile_payload
            compile_success = compile_payload.get("compile_success")
        else:
            compile_success = auto_metrics.get("compile_success")
    session.compile_success = compile_success
    session.auto_metrics = auto_metrics

    duration_seconds = None
    if session.started_at and session.ended_at:
        duration_seconds = int((_as_utc(session.ended_at) - _as_utc(session.started_at)).total_seconds())

    submission = StudySubmission(
        study_session_id=session.id,
        final_output=final_output,
        compile_success=compile_success,
        auto_metrics=auto_metrics,
        duration_seconds=duration_seconds,
    )
    db.add(submission)
    add_study_event(db, session_id=session.id, event_type="submit", payload={"duration_seconds": duration_seconds})
    create_report(
        db,
        report_type="study_session",
        title=f"study_{session.participant_code}",
        summary={
            "participant_code": session.participant_code,
            "condition": session.study_condition,
            "compile_success": compile_success,
        },
        payload={
            "session_id": session.id,
            "participant_code": session.participant_code,
            "participant_id": session.participant_id,
            "study_condition": session.study_condition,
            "final_output": final_output,
            "auto_metrics": auto_metrics,
        },
        related_session_id=session.id,
    )
    return session


def save_survey(db: Session, *, session: StudySession, payload: dict[str, Any]) -> SurveyResponse:
    response = db.scalar(select(SurveyResponse).where(SurveyResponse.study_session_id == session.id))
    if response is None:
        response = SurveyResponse(study_session_id=session.id, payload=payload)
        db.add(response)
    else:
        response.payload = payload
        response.submitted_at = utc_now()
    add_study_event(db, session_id=session.id, event_type="survey", payload=payload)
    db.flush()
    return response
