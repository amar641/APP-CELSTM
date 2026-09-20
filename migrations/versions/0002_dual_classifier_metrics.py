"""dual-classifier metrics — is_abnormal + denormalized model metrics on classification_results

Revision ID: 0002_dual_classifier_metrics
Revises: 0001_initial_schema
Create Date: 2026-09-13

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_dual_classifier_metrics"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "classification_results",
        sa.Column("is_abnormal", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("classification_results", sa.Column("model_precision", sa.Float(), nullable=True))
    op.add_column("classification_results", sa.Column("model_recall", sa.Float(), nullable=True))
    op.add_column("classification_results", sa.Column("model_accuracy", sa.Float(), nullable=True))
    op.add_column("classification_results", sa.Column("model_f1_macro", sa.Float(), nullable=True))
    op.create_index(
        "ix_classification_results_thermal_event_id",
        "classification_results",
        ["thermal_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_classification_results_thermal_event_id", table_name="classification_results")
    op.drop_column("classification_results", "model_f1_macro")
    op.drop_column("classification_results", "model_accuracy")
    op.drop_column("classification_results", "model_recall")
    op.drop_column("classification_results", "model_precision")
    op.drop_column("classification_results", "is_abnormal")
