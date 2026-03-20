from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app import db as db_module
from app.models import DatasetVersion
from app.services.reports import list_reports
from app.services.runs import (
    create_sample_compare_job,
    get_run_or_404,
    list_run_artifacts,
    process_next_queued_job,
)


def test_sample_compare_job_processing_generates_artifacts_and_report(
    session_factory: sessionmaker[Session],
    monkeypatch,
) -> None:
    fake_payload = {
        "sample": {
            "sample_id": "sample-001",
            "split": "test",
            "diagram_type": "flowchart",
        },
        "predictions": [
            {
                "provider": "gold_reference",
                "model_name": "gold_reference",
                "generated_code": "flowchart TD\nA --> B",
                "metrics": {
                    "line_f1": 1.0,
                    "compile_success": True,
                },
            }
        ],
    }

    monkeypatch.setattr(db_module, "SessionLocal", session_factory)
    monkeypatch.setattr("app.services.runs.run_sample_compare", lambda **_: fake_payload)

    with session_factory() as db:
        db.add(
            DatasetVersion(
                slug="test-dataset",
                display_name="Test Dataset",
                dataset_dir="/tmp/test-dataset",
                split_dir="/tmp/test-split",
                sample_count=1,
                train_count=0,
                validation_count=0,
                test_count=1,
                is_default=True,
            )
        )
        job = create_sample_compare_job(
            db,
            title="sample compare integration",
            dataset_version_slug="test-dataset",
            split="test",
            sample_id="sample-001",
            predictors=[{"provider": "gold_reference", "model": "gold_reference", "options": {}}],
        )
        run_id = job.id
        db.commit()

    processed_run_id = process_next_queued_job()
    assert processed_run_id == run_id

    with session_factory() as db:
        job = get_run_or_404(db, run_id)
        assert job.status == "succeeded"
        assert job.result_payload["sample"]["sample_id"] == "sample-001"

        artifacts = list_run_artifacts(db, run_id)
        assert len(artifacts) == 2
        assert all(Path(item.path).exists() for item in artifacts)

        reports = list_reports(db)
        assert any(item.related_run_id == run_id and item.report_type == "run_sample_compare" for item in reports)
