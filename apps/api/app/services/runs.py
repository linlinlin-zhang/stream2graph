from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_scope, utc_now
from app.legacy import (
    run_eval_suite_subprocess,
    run_sample_compare,
    write_json_artifact,
    write_markdown_artifact,
)
from app.models import RunArtifact, RunJob
from app.services.catalog import get_dataset_version_or_404
from app.services.reports import create_report


def create_sample_compare_job(
    db: Session,
    *,
    title: str,
    dataset_version_slug: str,
    split: str,
    sample_id: str,
    predictors: list[dict[str, Any]],
) -> RunJob:
    predictor_names = [str(item.get("provider", "")) for item in predictors]
    job = RunJob(
        job_type="sample_compare",
        title=title,
        status="queued",
        dataset_version_slug=dataset_version_slug,
        split=split,
        provider_name=", ".join(predictor_names),
        config_snapshot={
            "dataset_version_slug": dataset_version_slug,
            "split": split,
            "sample_id": sample_id,
            "predictors": predictors,
        },
        progress_json={"message": "已入队，等待 worker 执行"},
    )
    db.add(job)
    db.flush()
    return job


def create_benchmark_job(
    db: Session,
    *,
    title: str,
    dataset_version_slug: str,
    split: str,
    config_json: dict[str, Any],
) -> RunJob:
    job = RunJob(
        job_type="benchmark_suite",
        title=title,
        status="queued",
        dataset_version_slug=dataset_version_slug,
        split=split,
        config_snapshot={"config_json": config_json},
        progress_json={"message": "已入队，等待 worker 执行"},
    )
    db.add(job)
    db.flush()
    return job


def list_runs(db: Session) -> list[RunJob]:
    return db.scalars(select(RunJob).order_by(RunJob.created_at.desc())).all()


def get_run_or_404(db: Session, run_id: str) -> RunJob:
    job = db.get(RunJob, run_id)
    if job is None:
        raise ValueError(f"run not found: {run_id}")
    return job


def list_run_artifacts(db: Session, run_id: str) -> list[RunArtifact]:
    return db.scalars(select(RunArtifact).where(RunArtifact.run_id == run_id).order_by(RunArtifact.created_at.asc())).all()


def _add_artifact(db: Session, run_id: str, artifact_type: str, label: str, path: Path, fmt: str, meta: dict[str, Any] | None = None) -> None:
    db.add(
        RunArtifact(
            run_id=run_id,
            artifact_type=artifact_type,
            label=label,
            path=str(path),
            format=fmt,
            meta_json=meta or {},
        )
    )


def _run_dir(run_id: str) -> Path:
    settings = get_settings()
    path = settings.artifact_root / "runs" / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def claim_next_job(db: Session) -> RunJob | None:
    job = db.scalars(
        select(RunJob).where(RunJob.status == "queued").order_by(RunJob.created_at.asc()).limit(1)
    ).first()
    if job is None:
        return None
    job.status = "running"
    job.started_at = utc_now()
    job.updated_at = utc_now()
    job.progress_json = {"message": "任务开始执行"}
    db.flush()
    return job


def _complete_job(db: Session, job: RunJob, payload: dict[str, Any], summary: dict[str, Any]) -> None:
    job.status = "succeeded"
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    job.result_payload = payload
    job.progress_json = {"message": "任务完成"}
    create_report(
        db,
        report_type=f"run_{job.job_type}",
        title=job.title,
        summary=summary,
        payload=payload,
        related_run_id=job.id,
    )


def _fail_job(job: RunJob, exc: Exception) -> None:
    job.status = "failed"
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    job.error_message = str(exc)
    job.progress_json = {"message": "任务失败", "error": str(exc)}


def process_run_job(run_id: str) -> None:
    settings = get_settings()
    with session_scope() as db:
        job = get_run_or_404(db, run_id)
        if job.status not in {"queued", "running"}:
            return
        if job.status == "queued":
            job.status = "running"
            job.started_at = utc_now()
        run_dir = _run_dir(job.id)
        job.artifact_root = str(run_dir)
        job.updated_at = utc_now()
        db.flush()

        try:
            if job.job_type == "sample_compare":
                dataset = get_dataset_version_or_404(db, job.dataset_version_slug or "")
                payload = run_sample_compare(
                    dataset_dir=dataset.dataset_dir,
                    split_dir=dataset.split_dir,
                    split=str(job.config_snapshot["split"]),
                    sample_id=str(job.config_snapshot["sample_id"]),
                    predictors=list(job.config_snapshot["predictors"]),
                    compile_command=settings.mermaid_compile_command,
                )
                json_path = run_dir / "sample_compare.json"
                md_path = run_dir / "sample_compare.md"
                write_json_artifact(json_path, payload)
                write_markdown_artifact(
                    md_path,
                    [
                        f"# {job.title}",
                        "",
                        f"- Run ID: {job.id}",
                        f"- Sample ID: {payload['sample']['sample_id']}",
                        f"- Diagram Type: {payload['sample']['diagram_type']}",
                        "",
                        "## Predictions",
                        "",
                        *[
                            f"- {row['provider']} / {row['model_name']} | line_f1={row['metrics'].get('line_f1')} | compile={row['metrics'].get('compile_success')}"
                            for row in payload["predictions"]
                        ],
                    ],
                )
                _add_artifact(db, job.id, "result", "sample compare json", json_path, "json")
                _add_artifact(db, job.id, "result", "sample compare markdown", md_path, "md")
                _complete_job(
                    db,
                    job,
                    payload,
                    {
                        "sample_id": payload["sample"]["sample_id"],
                        "predictor_count": len(payload["predictions"]),
                    },
                )
            elif job.job_type == "benchmark_suite":
                suite_dir = run_dir / "suite"
                suite_result = run_eval_suite_subprocess(job.config_snapshot["config_json"], suite_dir)
                payload = {"suite": suite_result}
                _add_artifact(db, job.id, "config", "suite config", Path(suite_result["config_path"]), "json")
                _add_artifact(db, job.id, "log", "suite stdout", Path(suite_result["stdout_path"]), "log")
                _add_artifact(db, job.id, "log", "suite stderr", Path(suite_result["stderr_path"]), "log")
                manifest_json = suite_dir / "suite_manifest.json"
                manifest_md = suite_dir / "suite_manifest.md"
                if manifest_json.exists():
                    payload["manifest"] = json.loads(manifest_json.read_text(encoding="utf-8"))
                    _add_artifact(db, job.id, "report", "suite manifest json", manifest_json, "json")
                if manifest_md.exists():
                    _add_artifact(db, job.id, "report", "suite manifest markdown", manifest_md, "md")
                if suite_result["returncode"] != 0:
                    raise RuntimeError(f"benchmark suite failed with code {suite_result['returncode']}")
                _complete_job(
                    db,
                    job,
                    payload,
                    {
                        "duration_seconds": suite_result["duration_seconds"],
                        "returncode": suite_result["returncode"],
                    },
                )
            else:
                raise ValueError(f"unsupported job_type: {job.job_type}")
        except Exception as exc:
            _fail_job(job, exc)
        finally:
            db.flush()


def process_next_queued_job() -> str | None:
    with session_scope() as db:
        job = claim_next_job(db)
        if job is None:
            return None
        run_id = job.id
    process_run_job(run_id)
    return run_id
