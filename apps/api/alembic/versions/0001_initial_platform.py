"""initial platform schema

Revision ID: 0001_initial_platform
Revises:
Create Date: 2026-03-18 22:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("slug", sa.String(length=255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("dataset_dir", sa.Text(), nullable=False),
        sa.Column("split_dir", sa.Text(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("train_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("validation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("test_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "run_jobs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dataset_version_slug", sa.String(length=255), nullable=True),
        sa.Column("split", sa.String(length=32), nullable=True),
        sa.Column("provider_name", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("progress_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("result_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("artifact_root", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_run_jobs_status_created", "run_jobs", ["status", "created_at"])

    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("run_id", sa.String(length=32), sa.ForeignKey("run_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "realtime_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("dataset_version_slug", sa.String(length=255), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pipeline_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evaluation_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "realtime_chunks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("realtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expected_intent", sa.String(length=64), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_realtime_chunks_session_sequence", "realtime_chunks", ["session_id", "sequence_no"])

    op.create_table(
        "realtime_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("realtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_index", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_realtime_events_session_index", "realtime_events", ["session_id", "event_index"])

    op.create_table(
        "realtime_snapshots",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("session_id", sa.String(length=32), sa.ForeignKey("realtime_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pipeline_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("evaluation_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_tasks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dataset_version_slug", sa.String(length=255), nullable=True),
        sa.Column("split", sa.String(length=32), nullable=True),
        sa.Column("sample_id", sa.String(length=255), nullable=True),
        sa.Column("materials_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("system_outputs_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("default_condition", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("participant_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("task_id", sa.String(length=32), sa.ForeignKey("study_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.String(length=255), nullable=False),
        sa.Column("study_condition", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_transcript", sa.Text(), nullable=True),
        sa.Column("system_output", sa.Text(), nullable=True),
        sa.Column("draft_output", sa.Text(), nullable=True),
        sa.Column("final_output", sa.Text(), nullable=True),
        sa.Column("compile_success", sa.Boolean(), nullable=True),
        sa.Column("auto_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_events",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("study_session_id", sa.String(length=32), sa.ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "study_submissions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("study_session_id", sa.String(length=32), sa.ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("final_output", sa.Text(), nullable=False),
        sa.Column("compile_success", sa.Boolean(), nullable=True),
        sa.Column("auto_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "survey_responses",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("study_session_id", sa.String(length=32), sa.ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("related_run_id", sa.String(length=32), sa.ForeignKey("run_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("related_session_id", sa.String(length=32), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("json_path", sa.Text(), nullable=True),
        sa.Column("csv_path", sa.Text(), nullable=True),
        sa.Column("markdown_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("survey_responses")
    op.drop_table("study_submissions")
    op.drop_table("study_events")
    op.drop_table("study_sessions")
    op.drop_table("study_tasks")
    op.drop_table("realtime_snapshots")
    op.drop_index("ix_realtime_events_session_index", table_name="realtime_events")
    op.drop_table("realtime_events")
    op.drop_index("ix_realtime_chunks_session_sequence", table_name="realtime_chunks")
    op.drop_table("realtime_chunks")
    op.drop_table("realtime_sessions")
    op.drop_table("run_artifacts")
    op.drop_index("ix_run_jobs_status_created", table_name="run_jobs")
    op.drop_table("run_jobs")
    op.drop_table("dataset_versions")
    op.drop_table("admin_users")
