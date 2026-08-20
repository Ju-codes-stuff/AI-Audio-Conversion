"""
Initial database schema migration.
Creates all tables for Phases 1, 2, and 3.

Run with: alembic upgrade head
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("phone_number", sa.String(20), unique=True, nullable=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="hi"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_phone_number", "users", ["phone_number"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── departments ───────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("parent_id", UUID(as_uuid=False), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_departments_code", "departments", ["code"])

    # ── categories ────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("department_id", UUID(as_uuid=False), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── government_connectors ─────────────────────────────────
    op.create_table(
        "government_connectors",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("connector_name", sa.String(255), nullable=False),
        sa.Column("connector_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("auth_type", sa.String(30), nullable=False, server_default="NONE"),
        sa.Column("auth_config", JSONB, nullable=True),
        sa.Column("status_map", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── government_services ───────────────────────────────────
    op.create_table(
        "government_services",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("service_code", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category_code", sa.String(50), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("department_id", UUID(as_uuid=False), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("connector_id", UUID(as_uuid=False), sa.ForeignKey("government_connectors.id"), nullable=True),
        sa.Column("portal_url", sa.String(500), nullable=True),
        sa.Column("submission_method", sa.String(20), nullable=False, server_default="API"),
        sa.Column("required_fields", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_government_services_category_code", "government_services", ["category_code"])
    op.create_index("ix_government_services_state", "government_services", ["state"])

    # ── grievances ────────────────────────────────────────────
    op.create_table(
        "grievances",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("grievance_id", sa.String(30), unique=True, nullable=True),
        sa.Column("year_sequence", sa.Integer, nullable=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="CREATED"),
        sa.Column("priority", sa.String(20), nullable=True),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("language_name", sa.String(100), nullable=True),
        sa.Column("audio_storage_key", sa.String(500), nullable=True),
        sa.Column("audio_duration_seconds", sa.Integer, nullable=True),
        sa.Column("raw_transcript", sa.Text, nullable=True),
        sa.Column("english_text", sa.Text, nullable=True),
        sa.Column("structured_data", JSONB, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("department_id", UUID(as_uuid=False), sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("location_state", sa.String(100), nullable=True),
        sa.Column("location_district", sa.String(100), nullable=True),
        sa.Column("location_city", sa.String(100), nullable=True),
        sa.Column("location_raw", sa.String(500), nullable=True),
        sa.Column("government_reference_id", sa.String(200), nullable=True),
        sa.Column("connector_id", UUID(as_uuid=False), sa.ForeignKey("government_connectors.id"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_grievances_user_id", "grievances", ["user_id"])
    op.create_index("ix_grievances_grievance_id", "grievances", ["grievance_id"])
    op.create_index("ix_grievances_status", "grievances", ["status"])

    # ── transcripts ───────────────────────────────────────────
    op.create_table(
        "transcripts",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("grievance_id", UUID(as_uuid=False), sa.ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("language_code", sa.String(10), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("asr_model_version", sa.String(100), nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("is_mock", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_transcripts_grievance_id", "transcripts", ["grievance_id"])

    # ── translations ──────────────────────────────────────────
    op.create_table(
        "translations",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("grievance_id", UUID(as_uuid=False), sa.ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_language", sa.String(20), nullable=False),
        sa.Column("target_language", sa.String(20), nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("translated_text", sa.Text, nullable=False),
        sa.Column("translation_model_version", sa.String(100), nullable=True),
        sa.Column("processing_time_ms", sa.Integer, nullable=True),
        sa.Column("is_mock", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_translations_grievance_id", "translations", ["grievance_id"])

    # ── status_history ────────────────────────────────────────
    op.create_table(
        "status_history",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("grievance_id", UUID(as_uuid=False), sa.ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30), nullable=True),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("changed_by_user_id", UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_status_history_grievance_id", "status_history", ["grievance_id"])
    op.create_index("ix_status_history_created_at", "status_history", ["created_at"])

    # ── notifications ─────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grievance_id", UUID(as_uuid=False), sa.ForeignKey("grievances.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_grievance_id", "notifications", ["grievance_id"])

    # ── reference_id_mappings ─────────────────────────────────
    op.create_table(
        "reference_id_mappings",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("grievance_id", UUID(as_uuid=False), sa.ForeignKey("grievances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform_id", sa.String(30), nullable=False),
        sa.Column("government_reference_id", sa.String(200), nullable=False),
        sa.Column("connector_id", UUID(as_uuid=False), sa.ForeignKey("government_connectors.id"), nullable=False),
        sa.Column("mapped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reference_id_mappings_grievance_id", "reference_id_mappings", ["grievance_id"])
    op.create_index("ix_reference_id_mappings_government_reference_id", "reference_id_mappings", ["government_reference_id"])


def downgrade() -> None:
    op.drop_table("reference_id_mappings")
    op.drop_table("notifications")
    op.drop_table("status_history")
    op.drop_table("translations")
    op.drop_table("transcripts")
    op.drop_table("grievances")
    op.drop_table("government_services")
    op.drop_table("government_connectors")
    op.drop_table("categories")
    op.drop_table("departments")
    op.drop_table("users")
