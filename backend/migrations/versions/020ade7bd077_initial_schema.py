"""initial_schema

Revision ID: 020ade7bd077
Revises:
Create Date: 2026-05-10 21:13:17.655944

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '020ade7bd077'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("date_of_birth", sa.DateTime(), nullable=True),
        sa.Column("gender", sa.String(8), nullable=True),
        sa.Column("mrn", sa.String(64), nullable=True, unique=True),
        sa.Column("bed", sa.String(32), nullable=True),
        sa.Column("onset_minutes", sa.Integer(), nullable=True),
        sa.Column("diagnosis_history", sa.JSON(), nullable=True),
        sa.Column("doctor_id", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("patient_id", sa.String(32), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("relationship_label", sa.String(64), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("email", sa.String(160), nullable=True),
        sa.Column("notify_on_alert", sa.Boolean(), nullable=False, default=True),
        sa.Column("notify_weekly_report", sa.Boolean(), nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("device_type", sa.String(64), nullable=False),
        sa.Column("device_name", sa.String(120), nullable=False),
        sa.Column("mac_address", sa.String(48), nullable=True),
        sa.Column("serial_number", sa.String(64), nullable=True),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("fs", sa.Float(), nullable=False, default=256.0),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("patient_id", sa.String(32), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "eeg_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("patient_id", sa.String(32), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("device_id", sa.String(32), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("device_channels", sa.JSON(), nullable=True),
        sa.Column("fs", sa.Float(), nullable=False, default=256.0),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("total_windows", sa.Integer(), nullable=False, default=0),
        sa.Column("valid_windows", sa.Integer(), nullable=False, default=0),
        sa.Column("sqi_mean", sa.Float(), nullable=True),
        sa.Column("alert_count", sa.Integer(), nullable=False, default=0),
        sa.Column("raw_data_path", sa.String(512), nullable=True),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(32), sa.ForeignKey("eeg_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.String(32), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("timestamp_sec", sa.Float(), nullable=False),
        sa.Column("alert_class", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("probabilities_smooth", sa.JSON(), nullable=True),
        sa.Column("sqi_total", sa.Float(), nullable=True),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, default=False),
        sa.Column("acknowledged_by", sa.String(32), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )

    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("patient_id", sa.String(32), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("patient_name", sa.String(160), nullable=True),
        sa.Column("week_start", sa.String(10), nullable=False),
        sa.Column("week_label", sa.String(20), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False, default=0),
        sa.Column("alert_count", sa.Integer(), nullable=False, default=0),
        sa.Column("ack_count", sa.Integer(), nullable=False, default=0),
        sa.Column("escalation_count", sa.Integer(), nullable=False, default=0),
        sa.Column("sqi_mean", sa.Float(), nullable=True),
        sa.Column("pdf_path", sa.String(512), nullable=True),
        sa.Column("pdf_size_bytes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, default="pending"),
        sa.Column("recipient_emails", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("weekly_reports")
    op.drop_table("alerts")
    op.drop_table("eeg_sessions")
    op.drop_table("devices")
    op.drop_table("emergency_contacts")
    op.drop_table("patients")
