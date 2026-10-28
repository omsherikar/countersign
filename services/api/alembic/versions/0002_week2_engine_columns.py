"""engine columns: upload progress and counts, cohort and dates on enrolments, programme mode

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28 18:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


programmes_mode = postgresql.ENUM('PHYSICAL', 'ODL', 'ONLINE', name='programmes_mode', create_type=False)
upload_batches_stage = postgresql.ENUM(
    'PARSE', 'VALIDATE', 'FILE_DUPLICATES', 'UPSERT', 'LEDGER', 'CHECKS', 'DUPLICATES', 'FLAGS', 'DONE',
    name='upload_batches_stage', create_type=False,
)
upload_batches_source = postgresql.ENUM('FILE', 'API', 'SEED', name='upload_batches_source', create_type=False)
upload_row_errors_level = postgresql.ENUM('ERROR', 'WARNING', name='upload_row_errors_level', create_type=False)
NEW_ENUMS = (programmes_mode, upload_batches_stage, upload_batches_source, upload_row_errors_level)

# cohort_year(academic_year, year_of_study), the same arithmetic as app.core.cohort.cohort_year_sql
COHORT_YEAR_SQL = (
    "concat("
    "(substr(academic_year, 1, 4)::int - (year_of_study - 1))::text, '-', "
    "lpad(((substr(academic_year, 1, 4)::int - (year_of_study - 1) + 1) % 100)::text, 2, '0'))"
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in NEW_ENUMS:
        enum_type.create(bind, checkfirst=True)
    op.execute("ALTER TYPE upload_batches_status RENAME VALUE 'CHECKING' TO 'PROCESSING'")

    # programmes
    op.add_column('programmes', sa.Column('mode', programmes_mode, server_default='PHYSICAL', nullable=False))

    # upload_batches
    op.alter_column('upload_batches', 'rows_total', new_column_name='total_rows')
    op.add_column('upload_batches', sa.Column('source', upload_batches_source, server_default='FILE', nullable=False))
    op.add_column('upload_batches', sa.Column('stage', upload_batches_stage, nullable=True))
    op.add_column('upload_batches', sa.Column('stage_total', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('upload_batches', sa.Column('processed_rows', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('upload_batches', sa.Column('counts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column('upload_batches', sa.Column('error', sa.String(), nullable=True))
    op.add_column('upload_batches', sa.Column('ignored_columns', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::text[]"), nullable=False))
    op.add_column('upload_batches', sa.Column('file_sha256', sa.String(), nullable=True))
    op.add_column('upload_batches', sa.Column('declared_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('upload_batches', sa.Column('declaration_text', sa.String(), nullable=True))
    # Every batch before this revision was written by the seed importer.
    op.execute(
        "UPDATE upload_batches SET source = 'SEED', "
        "stage = CASE WHEN status = 'DONE' THEN 'DONE'::upload_batches_stage END, "
        "counts = jsonb_build_object('rows', total_rows, 'accepted', rows_ok, 'errors', rows_error)"
    )
    op.drop_column('upload_batches', 'rows_ok')
    op.drop_column('upload_batches', 'rows_error')
    op.drop_column('upload_batches', 'progress_pct')
    op.create_index('ix_upload_batches_institution_year_created', 'upload_batches', ['institution_id', 'academic_year', 'created_at'], unique=False)

    # upload_row_errors
    op.add_column('upload_row_errors', sa.Column('level', upload_row_errors_level, server_default='ERROR', nullable=False))
    op.add_column('upload_row_errors', sa.Column('value_masked', sa.String(), nullable=True))
    op.create_index('ix_upload_row_errors_batch_id_row_no', 'upload_row_errors', ['batch_id', 'row_no'], unique=False)

    # students
    op.add_column('students', sa.Column('name_key', sa.String(), nullable=True))
    op.add_column('students', sa.Column('passport_encrypted', sa.LargeBinary(), nullable=True))
    op.create_index('ix_students_name_key', 'students', ['name_key'], unique=False)
    op.create_index('ix_students_passport_hmac', 'students', ['passport_hmac'], unique=False)

    # enrolments
    op.add_column('enrolments', sa.Column('cohort_year', sa.String(), nullable=True))
    op.add_column('enrolments', sa.Column('admission_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=True))
    op.add_column('enrolments', sa.Column('status_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=True))
    op.add_column('enrolments', sa.Column('apaar_problem', sa.String(), nullable=True))
    op.execute(
        f"UPDATE enrolments SET cohort_year = {COHORT_YEAR_SQL}, "
        "admission_date = uploaded_at::date, status_date = uploaded_at::date"
    )
    op.alter_column('enrolments', 'cohort_year', nullable=False)
    op.alter_column('enrolments', 'admission_date', nullable=False)
    op.alter_column('enrolments', 'status_date', nullable=False)
    op.create_index('ix_enrolments_programme_cohort_status', 'enrolments', ['programme_id', 'cohort_year', 'status'], unique=False)
    op.create_index('uq_enrolments_seat_id', 'enrolments', ['seat_id'], unique=True, postgresql_where=sa.text('seat_id IS NOT NULL'))

    # seat_events
    op.add_column('seat_events', sa.Column('effective_date', sa.Date(), nullable=True))

    # checks
    op.create_index('ix_checks_type_status', 'checks', ['type', 'status'], unique=False)

    # flags
    op.add_column('flags', sa.Column('academic_year', sa.String(), nullable=True))
    op.create_index('ix_flags_academic_year_status', 'flags', ['academic_year', 'status'], unique=False)
    op.create_index('ix_flags_related_enrolment_ids', 'flags', ['related_enrolment_ids'], unique=False, postgresql_using='gin')


def downgrade() -> None:
    op.drop_index('ix_flags_related_enrolment_ids', table_name='flags', postgresql_using='gin')
    op.drop_index('ix_flags_academic_year_status', table_name='flags')
    op.drop_column('flags', 'academic_year')

    op.drop_index('ix_checks_type_status', table_name='checks')

    op.drop_column('seat_events', 'effective_date')

    op.drop_index('uq_enrolments_seat_id', table_name='enrolments', postgresql_where=sa.text('seat_id IS NOT NULL'))
    op.drop_index('ix_enrolments_programme_cohort_status', table_name='enrolments')
    op.drop_column('enrolments', 'apaar_problem')
    op.drop_column('enrolments', 'status_date')
    op.drop_column('enrolments', 'admission_date')
    op.drop_column('enrolments', 'cohort_year')

    op.drop_index('ix_students_passport_hmac', table_name='students')
    op.drop_index('ix_students_name_key', table_name='students')
    op.drop_column('students', 'passport_encrypted')
    op.drop_column('students', 'name_key')

    op.drop_index('ix_upload_row_errors_batch_id_row_no', table_name='upload_row_errors')
    op.drop_column('upload_row_errors', 'value_masked')
    op.drop_column('upload_row_errors', 'level')

    op.drop_index('ix_upload_batches_institution_year_created', table_name='upload_batches')
    op.add_column('upload_batches', sa.Column('rows_ok', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('upload_batches', sa.Column('rows_error', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('upload_batches', sa.Column('progress_pct', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.execute(
        "UPDATE upload_batches SET "
        "rows_ok = COALESCE((counts->>'accepted')::int, 0), "
        "rows_error = COALESCE((counts->>'errors')::int, 0), "
        "progress_pct = CASE WHEN status = 'DONE' THEN 100 ELSE 0 END"
    )
    for column in ('rows_ok', 'rows_error', 'progress_pct'):
        op.alter_column('upload_batches', column, server_default=None)
    op.drop_column('upload_batches', 'declaration_text')
    op.drop_column('upload_batches', 'declared_at')
    op.drop_column('upload_batches', 'file_sha256')
    op.drop_column('upload_batches', 'ignored_columns')
    op.drop_column('upload_batches', 'error')
    op.drop_column('upload_batches', 'counts')
    op.drop_column('upload_batches', 'processed_rows')
    op.drop_column('upload_batches', 'stage_total')
    op.drop_column('upload_batches', 'stage')
    op.drop_column('upload_batches', 'source')
    op.alter_column('upload_batches', 'total_rows', new_column_name='rows_total')

    op.drop_column('programmes', 'mode')

    op.execute("ALTER TYPE upload_batches_status RENAME VALUE 'PROCESSING' TO 'CHECKING'")
    bind = op.get_bind()
    for enum_type in reversed(NEW_ENUMS):
        enum_type.drop(bind, checkfirst=True)
