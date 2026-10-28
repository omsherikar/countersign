"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-28 13:14:22.361728

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUM_TYPES = [
    'students_consent_status', 'students_gender', 'consents_purpose', 'consents_status',
    'data_requests_kind', 'data_requests_status', 'institutions_type', 'programmes_level',
    'programmes_discipline', 'programmes_shift', 'users_role', 'audit_log_action',
    'upload_batches_kind', 'upload_batches_status', 'seat_pools_seat_type', 'seats_status',
    'enrolments_admission_route', 'enrolments_category', 'enrolments_status', 'checks_type',
    'checks_status', 'credentials_kind', 'flags_type', 'flags_severity', 'flags_status',
    'notifications_channel', 'notifications_response', 'seat_events_kind', 'case_actions_action',
]


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS citext')
    op.create_table('regions',
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('hq_city', sa.String(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_regions')),
    sa.UniqueConstraint('code', name=op.f('uq_regions_code'))
    )
    op.create_table('students',
    sa.Column('apaar_hmac', sa.LargeBinary(), nullable=True),
    sa.Column('apaar_encrypted', sa.LargeBinary(), nullable=True),
    sa.Column('apaar_last4', sa.String(length=4), nullable=True),
    sa.Column('consent_status', sa.Enum('LINKED', 'REFUSED', 'PENDING', 'INTERNATIONAL', name='students_consent_status'), nullable=False),
    sa.Column('provisional_id', sa.String(), nullable=True),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('name_normalized', sa.String(), nullable=False),
    sa.Column('dob', sa.Date(), nullable=False),
    sa.Column('gender', sa.Enum('M', 'F', 'O', 'U', name='students_gender'), nullable=False),
    sa.Column('mobile_hmac', sa.LargeBinary(), nullable=True),
    sa.Column('mobile_last4', sa.String(length=4), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('address_hmac', sa.LargeBinary(), nullable=True),
    sa.Column('nationality', sa.String(length=2), nullable=False),
    sa.Column('passport_hmac', sa.LargeBinary(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_students')),
    sa.UniqueConstraint('apaar_hmac', name=op.f('uq_students_apaar_hmac')),
    sa.UniqueConstraint('provisional_id', name=op.f('uq_students_provisional_id'))
    )
    op.create_index('ix_students_address_hmac', 'students', ['address_hmac'], unique=False)
    op.create_index('ix_students_dob_name_normalized', 'students', ['dob', 'name_normalized'], unique=False)
    op.create_index('ix_students_email', 'students', ['email'], unique=False)
    op.create_index('ix_students_mobile_hmac', 'students', ['mobile_hmac'], unique=False)
    op.create_table('consents',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('purpose', sa.Enum('APAAR_LINK', 'NOTICE', 'CREDENTIAL_SHARE', name='consents_purpose'), nullable=False),
    sa.Column('status', sa.Enum('GIVEN', 'WITHDRAWN', 'REFUSED', name='consents_status'), nullable=False),
    sa.Column('notice_text', sa.String(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('channel', sa.String(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_consents_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_consents'))
    )
    op.create_index(op.f('ix_consents_student_id'), 'consents', ['student_id'], unique=False)
    op.create_table('data_requests',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('ACCESS', 'CORRECTION', 'ERASURE', name='data_requests_kind'), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'DONE', 'REJECTED', name='data_requests_status'), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_data_requests_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_data_requests'))
    )
    op.create_index(op.f('ix_data_requests_student_id'), 'data_requests', ['student_id'], unique=False)
    op.create_table('states',
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], name=op.f('fk_states_region_id_regions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_states')),
    sa.UniqueConstraint('code', name=op.f('uq_states_code'))
    )
    op.create_table('universities',
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('state_id', sa.UUID(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], name=op.f('fk_universities_state_id_states')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_universities')),
    sa.UniqueConstraint('code', name=op.f('uq_universities_code'))
    )
    op.create_table('institutions',
    sa.Column('aicte_permanent_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('type', sa.Enum('GOVERNMENT', 'GOVERNMENT_AIDED', 'PRIVATE_SELF_FINANCED', 'UNIVERSITY_DEPARTMENT', 'DEEMED', name='institutions_type'), nullable=False),
    sa.Column('state_id', sa.UUID(), nullable=False),
    sa.Column('region_id', sa.UUID(), nullable=False),
    sa.Column('university_id', sa.UUID(), nullable=True),
    sa.Column('address_city', sa.String(), nullable=True),
    sa.Column('established_year', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], name=op.f('fk_institutions_region_id_regions')),
    sa.ForeignKeyConstraint(['state_id'], ['states.id'], name=op.f('fk_institutions_state_id_states')),
    sa.ForeignKeyConstraint(['university_id'], ['universities.id'], name=op.f('fk_institutions_university_id_universities')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_institutions')),
    sa.UniqueConstraint('aicte_permanent_id', name=op.f('uq_institutions_aicte_permanent_id'))
    )
    op.create_index('ix_institutions_lower_name', 'institutions', [sa.literal_column('lower(name)')], unique=False)
    op.create_index('ix_institutions_region_id', 'institutions', ['region_id'], unique=False)
    op.create_index('ix_institutions_state_id', 'institutions', ['state_id'], unique=False)
    op.create_index('ix_institutions_university_id', 'institutions', ['university_id'], unique=False)
    op.create_table('institution_scores',
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('academic_year', sa.String(), nullable=False),
    sa.Column('integrity_index', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('components', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_institution_scores_institution_id_institutions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_institution_scores')),
    sa.UniqueConstraint('institution_id', 'academic_year', name=op.f('uq_institution_scores_institution_id_academic_year'))
    )
    op.create_table('programmes',
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('level', sa.Enum('DIPLOMA', 'UG', 'PG', 'POST_DIPLOMA', name='programmes_level'), nullable=False),
    sa.Column('discipline', sa.Enum('ENGINEERING', 'MANAGEMENT', 'COMPUTER_APPLICATIONS', 'PHARMACY', 'ARCHITECTURE', 'PLANNING', 'DESIGN', 'HOTEL_MANAGEMENT', 'APPLIED_ARTS', name='programmes_discipline'), nullable=False),
    sa.Column('shift', sa.Enum('FIRST', 'SECOND', name='programmes_shift'), nullable=False),
    sa.Column('duration_years', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_programmes_institution_id_institutions')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_programmes')),
    sa.UniqueConstraint('institution_id', 'code', 'shift', name=op.f('uq_programmes_institution_id_code_shift'))
    )
    op.create_index(op.f('ix_programmes_institution_id'), 'programmes', ['institution_id'], unique=False)
    op.create_table('users',
    sa.Column('email', postgresql.CITEXT(), nullable=False),
    sa.Column('password_hash', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('role', sa.Enum('AICTE_ADMIN', 'RO_OFFICER', 'INSTITUTION', 'STUDENT', 'UNIVERSITY', name='users_role'), nullable=False),
    sa.Column('institution_id', sa.UUID(), nullable=True),
    sa.Column('region_id', sa.UUID(), nullable=True),
    sa.Column('student_id', sa.UUID(), nullable=True),
    sa.Column('university_id', sa.UUID(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("(role = 'AICTE_ADMIN' AND institution_id IS NULL AND region_id IS NULL AND student_id IS NULL AND university_id IS NULL) OR (role = 'RO_OFFICER' AND region_id IS NOT NULL AND institution_id IS NULL AND student_id IS NULL AND university_id IS NULL) OR (role = 'INSTITUTION' AND institution_id IS NOT NULL AND region_id IS NULL AND student_id IS NULL AND university_id IS NULL) OR (role = 'STUDENT' AND student_id IS NOT NULL AND institution_id IS NULL AND region_id IS NULL AND university_id IS NULL) OR (role = 'UNIVERSITY' AND university_id IS NOT NULL AND institution_id IS NULL AND region_id IS NULL AND student_id IS NULL)", name=op.f('ck_users_role_scope')),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_users_institution_id_institutions')),
    sa.ForeignKeyConstraint(['region_id'], ['regions.id'], name=op.f('fk_users_region_id_regions')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_users_student_id_students')),
    sa.ForeignKeyConstraint(['university_id'], ['universities.id'], name=op.f('fk_users_university_id_universities')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('approvals',
    sa.Column('programme_id', sa.UUID(), nullable=False),
    sa.Column('academic_year', sa.String(), nullable=False),
    sa.Column('approved_intake', sa.Integer(), nullable=False),
    sa.Column('cutoff_date', sa.Date(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['programme_id'], ['programmes.id'], name=op.f('fk_approvals_programme_id_programmes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_approvals')),
    sa.UniqueConstraint('programme_id', 'academic_year', name=op.f('uq_approvals_programme_id_academic_year'))
    )
    op.create_table('audit_log',
    sa.Column('seq', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.Enum('CREATE', 'UPDATE', 'DELETE', 'READ', 'LOGIN', 'LOGOUT', 'SEED', name='audit_log_action'), nullable=False),
    sa.Column('entity_type', sa.String(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('request_id', sa.String(), nullable=True),
    sa.Column('prev_hash', sa.String(length=64), nullable=True),
    sa.Column('hash', sa.String(length=64), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_log_actor_id_users')),
    sa.PrimaryKeyConstraint('seq', name=op.f('pk_audit_log'))
    )
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_type'), 'audit_log', ['entity_type'], unique=False)
    op.create_table('upload_batches',
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('academic_year', sa.String(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('kind', sa.Enum('INITIAL', 'UPDATE', name='upload_batches_kind'), nullable=False),
    sa.Column('status', sa.Enum('QUEUED', 'VALIDATING', 'CHECKING', 'DONE', 'FAILED', name='upload_batches_status'), nullable=False),
    sa.Column('rows_total', sa.Integer(), nullable=False),
    sa.Column('rows_ok', sa.Integer(), nullable=False),
    sa.Column('rows_error', sa.Integer(), nullable=False),
    sa.Column('progress_pct', sa.Integer(), nullable=False),
    sa.Column('uploaded_by', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_upload_batches_institution_id_institutions')),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_upload_batches_uploaded_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_upload_batches'))
    )
    op.create_index(op.f('ix_upload_batches_institution_id'), 'upload_batches', ['institution_id'], unique=False)
    op.create_table('seat_pools',
    sa.Column('approval_id', sa.UUID(), nullable=False),
    sa.Column('seat_type', sa.Enum('REGULAR', 'NRI', 'TFW', 'LATERAL', 'INTERNATIONAL', name='seat_pools_seat_type'), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('is_supernumerary', sa.Boolean(), nullable=False),
    sa.Column('rule_source', sa.String(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['approval_id'], ['approvals.id'], name=op.f('fk_seat_pools_approval_id_approvals')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seat_pools')),
    sa.UniqueConstraint('approval_id', 'seat_type', name=op.f('uq_seat_pools_approval_id_seat_type'))
    )
    op.create_table('upload_row_errors',
    sa.Column('batch_id', sa.UUID(), nullable=False),
    sa.Column('row_no', sa.Integer(), nullable=False),
    sa.Column('field', sa.String(), nullable=True),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('message', sa.String(), nullable=False),
    sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['upload_batches.id'], name=op.f('fk_upload_row_errors_batch_id_upload_batches'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_upload_row_errors'))
    )
    op.create_index(op.f('ix_upload_row_errors_batch_id'), 'upload_row_errors', ['batch_id'], unique=False)
    op.create_table('seats',
    sa.Column('pool_id', sa.UUID(), nullable=False),
    sa.Column('seat_code', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('FREE', 'ASSIGNED', 'RELEASED', name='seats_status'), nullable=False),
    sa.Column('reserved_for', sa.String(), nullable=True),
    sa.Column('enrolment_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['pool_id'], ['seat_pools.id'], name=op.f('fk_seats_pool_id_seat_pools')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seats')),
    sa.UniqueConstraint('pool_id', 'seat_code', name=op.f('uq_seats_pool_id_seat_code'))
    )
    op.create_index('ix_seats_enrolment_id', 'seats', ['enrolment_id'], unique=False)
    op.create_index('ix_seats_pool_id_free', 'seats', ['pool_id'], unique=False, postgresql_where=sa.text("status = 'FREE'"))
    op.create_table('enrolments',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('programme_id', sa.UUID(), nullable=False),
    sa.Column('academic_year', sa.String(), nullable=False),
    sa.Column('year_of_study', sa.Integer(), nullable=False),
    sa.Column('admission_route', sa.Enum('COUNSELLING', 'MANAGEMENT', 'NRI', 'SPOT', 'LATERAL', 'INTERNATIONAL', 'TFW', name='enrolments_admission_route'), nullable=False),
    sa.Column('counselling_ref', sa.String(), nullable=True),
    sa.Column('category', sa.Enum('GENERAL', 'EWS', 'OBC', 'SC', 'ST', 'OTHER', name='enrolments_category'), nullable=False),
    sa.Column('seat_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('ACTIVE', 'WITHDRAWN', 'TRANSFERRED', 'GRADUATED', name='enrolments_status'), nullable=False),
    sa.Column('upload_batch_id', sa.UUID(), nullable=True),
    sa.Column('source_row_no', sa.Integer(), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_enrolments_institution_id_institutions')),
    sa.ForeignKeyConstraint(['programme_id'], ['programmes.id'], name=op.f('fk_enrolments_programme_id_programmes')),
    sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], name=op.f('fk_enrolments_seat_id_seats')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_enrolments_student_id_students')),
    sa.ForeignKeyConstraint(['upload_batch_id'], ['upload_batches.id'], name=op.f('fk_enrolments_upload_batch_id_upload_batches')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enrolments')),
    sa.UniqueConstraint('student_id', 'institution_id', 'programme_id', 'academic_year', name=op.f('uq_enrolments_student_id_institution_id_programme_id_academic_year'))
    )
    op.create_index('ix_enrolments_institution_year_status', 'enrolments', ['institution_id', 'academic_year', 'status'], unique=False)
    op.create_index('ix_enrolments_programme_year', 'enrolments', ['programme_id', 'academic_year'], unique=False)
    op.create_index('ix_enrolments_student_id', 'enrolments', ['student_id'], unique=False)
    op.create_foreign_key(
        'fk_seats_enrolment_id_enrolments', 'seats', 'enrolments', ['enrolment_id'], ['id']
    )
    op.create_table('checks',
    sa.Column('enrolment_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.Enum('IDENTITY', 'ADMISSION', 'SEAT', 'STUDYING', 'STUDENT', name='checks_type'), nullable=False),
    sa.Column('status', sa.Enum('PASS', 'FAIL', 'PENDING', 'NA', name='checks_status'), nullable=False),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_checks_enrolment_id_enrolments'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_checks')),
    sa.UniqueConstraint('enrolment_id', 'type', name=op.f('uq_checks_enrolment_id_type'))
    )
    op.create_table('credentials',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('enrolment_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('ENROLMENT', 'DEGREE', name='credentials_kind'), nullable=False),
    sa.Column('sd_jwt', sa.String(), nullable=False),
    sa.Column('status_list_index', sa.Integer(), nullable=False),
    sa.Column('revoked', sa.Boolean(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('issuer_key_id', sa.String(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_credentials_enrolment_id_enrolments')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_credentials_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_credentials')),
    sa.UniqueConstraint('status_list_index', name=op.f('uq_credentials_status_list_index'))
    )
    op.create_index(op.f('ix_credentials_student_id'), 'credentials', ['student_id'], unique=False)
    op.create_table('flags',
    sa.Column('type', sa.Enum('EXCESS_ADMISSION', 'QUOTA_BREACH', 'LATE_REFILL', 'INVALID_APAAR', 'NAME_MISMATCH', 'DUPLICATE_CROSS_INSTITUTION', 'DUPLICATE_WITHIN_UPLOAD', 'DUAL_ENROLMENT_ALLOWED', 'NO_ACADEMIC_ACTIVITY', 'STUDENT_DENIED', 'GHOST_RING', 'ANOMALY', name='flags_type'), nullable=False),
    sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', name='flags_severity'), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'DOCS_REQUESTED', 'CLEARED', 'ESCALATED', 'CONFIRMED', name='flags_status'), nullable=False),
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('programme_id', sa.UUID(), nullable=True),
    sa.Column('enrolment_id', sa.UUID(), nullable=True),
    sa.Column('related_enrolment_ids', sa.ARRAY(sa.UUID()), nullable=False),
    sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('assignee_id', sa.UUID(), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dedupe_key', sa.String(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['assignee_id'], ['users.id'], name=op.f('fk_flags_assignee_id_users')),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_flags_enrolment_id_enrolments')),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_flags_institution_id_institutions')),
    sa.ForeignKeyConstraint(['programme_id'], ['programmes.id'], name=op.f('fk_flags_programme_id_programmes')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flags')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_flags_dedupe_key'))
    )
    op.create_index('ix_flags_enrolment_id', 'flags', ['enrolment_id'], unique=False)
    op.create_index('ix_flags_institution_id_status', 'flags', ['institution_id', 'status'], unique=False)
    op.create_index('ix_flags_type_status', 'flags', ['type', 'status'], unique=False)
    op.create_table('notifications',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('enrolment_id', sa.UUID(), nullable=False),
    sa.Column('channel', sa.Enum('EMAIL', 'DIGILOCKER', name='notifications_channel'), nullable=False),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('message', sa.String(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('response', sa.Enum('YES', 'NO', name='notifications_response'), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_notifications_enrolment_id_enrolments')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_notifications_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    sa.UniqueConstraint('token', name=op.f('uq_notifications_token'))
    )
    op.create_index(op.f('ix_notifications_student_id'), 'notifications', ['student_id'], unique=False)
    op.create_table('seat_events',
    sa.Column('seq', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('seat_id', sa.UUID(), nullable=False),
    sa.Column('enrolment_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('ASSIGN', 'RELEASE', name='seat_events_kind'), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('reason', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_seat_events_actor_id_users')),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_seat_events_enrolment_id_enrolments')),
    sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], name=op.f('fk_seat_events_seat_id_seats')),
    sa.PrimaryKeyConstraint('seq', name=op.f('pk_seat_events'))
    )
    op.create_index('ix_seat_events_enrolment_id', 'seat_events', ['enrolment_id'], unique=False)
    op.create_index('ix_seat_events_seat_id_seq', 'seat_events', ['seat_id', 'seq'], unique=False)
    op.create_table('case_actions',
    sa.Column('seq', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('flag_id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.Enum('CLEAR', 'REQUEST_DOCS', 'ESCALATE', 'CONFIRM', 'NOTE', 'COLLEGE_RESPONSE', name='case_actions_action'), nullable=False),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_case_actions_actor_id_users')),
    sa.ForeignKeyConstraint(['flag_id'], ['flags.id'], name=op.f('fk_case_actions_flag_id_flags')),
    sa.PrimaryKeyConstraint('seq', name=op.f('pk_case_actions'))
    )
    op.create_index(op.f('ix_case_actions_flag_id'), 'case_actions', ['flag_id'], unique=False)


def downgrade() -> None:
    op.drop_constraint('fk_seats_enrolment_id_enrolments', 'seats', type_='foreignkey')
    op.drop_index(op.f('ix_case_actions_flag_id'), table_name='case_actions')
    op.drop_table('case_actions')
    op.drop_index('ix_seat_events_seat_id_seq', table_name='seat_events')
    op.drop_index('ix_seat_events_enrolment_id', table_name='seat_events')
    op.drop_table('seat_events')
    op.drop_index(op.f('ix_notifications_student_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index('ix_flags_type_status', table_name='flags')
    op.drop_index('ix_flags_institution_id_status', table_name='flags')
    op.drop_index('ix_flags_enrolment_id', table_name='flags')
    op.drop_table('flags')
    op.drop_index(op.f('ix_credentials_student_id'), table_name='credentials')
    op.drop_table('credentials')
    op.drop_table('checks')
    op.drop_index('ix_enrolments_student_id', table_name='enrolments')
    op.drop_index('ix_enrolments_programme_year', table_name='enrolments')
    op.drop_index('ix_enrolments_institution_year_status', table_name='enrolments')
    op.drop_table('enrolments')
    op.drop_index('ix_seats_pool_id_free', table_name='seats', postgresql_where=sa.text("status = 'FREE'"))
    op.drop_index('ix_seats_enrolment_id', table_name='seats')
    op.drop_table('seats')
    op.drop_index(op.f('ix_upload_row_errors_batch_id'), table_name='upload_row_errors')
    op.drop_table('upload_row_errors')
    op.drop_table('seat_pools')
    op.drop_index(op.f('ix_upload_batches_institution_id'), table_name='upload_batches')
    op.drop_table('upload_batches')
    op.drop_index(op.f('ix_audit_log_entity_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_table('approvals')
    op.drop_table('users')
    op.drop_index(op.f('ix_programmes_institution_id'), table_name='programmes')
    op.drop_table('programmes')
    op.drop_table('institution_scores')
    op.drop_index('ix_institutions_university_id', table_name='institutions')
    op.drop_index('ix_institutions_state_id', table_name='institutions')
    op.drop_index('ix_institutions_region_id', table_name='institutions')
    op.drop_index('ix_institutions_lower_name', table_name='institutions')
    op.drop_table('institutions')
    op.drop_table('universities')
    op.drop_table('states')
    op.drop_index(op.f('ix_data_requests_student_id'), table_name='data_requests')
    op.drop_table('data_requests')
    op.drop_index(op.f('ix_consents_student_id'), table_name='consents')
    op.drop_table('consents')
    op.drop_index('ix_students_mobile_hmac', table_name='students')
    op.drop_index('ix_students_email', table_name='students')
    op.drop_index('ix_students_dob_name_normalized', table_name='students')
    op.drop_index('ix_students_address_hmac', table_name='students')
    op.drop_table('students')
    op.drop_table('regions')
    for enum_type in ENUM_TYPES:
        op.execute(f'DROP TYPE IF EXISTS {enum_type}')
