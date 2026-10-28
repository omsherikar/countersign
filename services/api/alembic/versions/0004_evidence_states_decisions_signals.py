"""evidence states and provenance on checks, record status on enrolments, officer decisions,
completion attestations, enrolment and approval versions, column mappings, signals, completeness

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29 12:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


enrolments_record_status = postgresql.ENUM(
    'AWAITING_EVIDENCE', 'COUNTERSIGNED', 'UNDER_REVIEW', 'DISPUTED',
    name='enrolments_record_status', create_type=False,
)
signals_type = postgresql.ENUM('GHOST_RING', 'ANOMALY', name='signals_type', create_type=False)
signals_status = postgresql.ENUM('NEW', 'CASE_OPENED', 'DISMISSED', name='signals_status', create_type=False)
NEW_ENUMS = (enrolments_record_status, signals_type, signals_status)

# Postgres cannot use a label added by ADD VALUE in the transaction that added it, and the
# data step below writes the new check states, so these run in an autocommit block first.
# IF NOT EXISTS (and BEFORE an old label) keeps them safe to repeat when a later step fails
# and the transaction that holds the renames rolls back.
ADDED_VALUES = (
    ('checks_status', 'NOT_YET_DUE', "BEFORE 'NA'"),
    ('checks_status', 'SOURCE_UNAVAILABLE', ''),
    ('flags_status', 'CORRECTED', ''),
    ('case_actions_action', 'CORRECT', ''),
    ('flags_type', 'NOT_IN_JOINING_RECORD', ''),
    ('flags_type', 'ELIGIBILITY_BREACH', ''),
    ('flags_type', 'MISSING_FROM_UPLOAD', ''),
)
RENAMED_VALUES = (
    ('checks_status', 'PASS', 'CONFIRMED'),
    ('checks_status', 'FAIL', 'CONTRADICTED'),
    ('checks_status', 'NA', 'NOT_APPLICABLE'),
    ('flags_status', 'CLEARED', 'UPHELD'),
    ('flags_status', 'CONFIRMED', 'WITHDRAWN'),
    ('case_actions_action', 'CLEAR', 'UPHOLD'),
    ('case_actions_action', 'CONFIRM', 'WITHDRAW'),
    ('credentials_kind', 'DEGREE', 'COMPLETION'),
)

# the row each case type covers (API_CONTRACT A4.10), for the resolved backfill
CASE_ROWS = (
    ('INVALID_APAAR', 'IDENTITY'),
    ('NAME_MISMATCH', 'IDENTITY'),
    ('EXCESS_ADMISSION', 'SEAT'),
    ('QUOTA_BREACH', 'SEAT'),
    ('NO_ACADEMIC_ACTIVITY', 'STUDYING'),
    ('STUDENT_DENIED', 'STUDENT'),
)

CHECKS_STATUS_0003 = ('PASS', 'FAIL', 'PENDING', 'NA')
FLAGS_STATUS_0003 = ('OPEN', 'DOCS_REQUESTED', 'CLEARED', 'ESCALATED', 'CONFIRMED')
CASE_ACTIONS_0003 = (
    'CLEAR', 'REQUEST_DOCS', 'ESCALATE', 'CONFIRM', 'NOTE', 'COLLEGE_RESPONSE',
    'ASSIGN', 'REOPEN', 'SYSTEM_NOTE',
)
FLAGS_TYPE_0003 = (
    'EXCESS_ADMISSION', 'QUOTA_BREACH', 'LATE_REFILL', 'INVALID_APAAR', 'NAME_MISMATCH',
    'DUPLICATE_CROSS_INSTITUTION', 'DUPLICATE_WITHIN_UPLOAD', 'DUAL_ENROLMENT_ALLOWED',
    'NO_ACADEMIC_ACTIVITY', 'STUDENT_DENIED', 'GHOST_RING', 'ANOMALY',
)
FLAGS_TYPE_ADDED = ('NOT_IN_JOINING_RECORD', 'ELIGIBILITY_BREACH', 'MISSING_FROM_UPLOAD')


def _sql_list(values: Sequence[str]) -> str:
    return ', '.join(f"'{v}'" for v in values)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for type_name, value, position in ADDED_VALUES:
            op.execute(f"ALTER TYPE {type_name} ADD VALUE IF NOT EXISTS '{value}' {position}".rstrip())
    for type_name, old, new in RENAMED_VALUES:
        op.execute(f"ALTER TYPE {type_name} RENAME VALUE '{old}' TO '{new}'")

    bind = op.get_bind()
    for enum_type in NEW_ENUMS:
        enum_type.create(bind, checkfirst=True)

    # checks: the six evidence states (D34) and provenance
    # credits before the first semester result: year 1, or a year-2 lateral entrant (R4)
    op.execute(
        "UPDATE checks c SET status = 'NOT_YET_DUE' FROM enrolments e "
        "WHERE c.enrolment_id = e.id AND c.type = 'STUDYING' AND c.status = 'NOT_APPLICABLE' "
        "AND (e.year_of_study = 1 OR (e.admission_route = 'LATERAL' AND e.year_of_study = 2))"
    )
    op.execute(
        "UPDATE checks SET status = 'SOURCE_UNAVAILABLE' "
        "WHERE status = 'PENDING' AND detail ->> 'source_unavailable' = 'true'"
    )
    op.add_column('checks', sa.Column('supplied_by', sa.String(), server_default='', nullable=False))
    op.add_column('checks', sa.Column('observed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('checks', sa.Column('independent', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('checks', sa.Column('resolved', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    # a contradiction whose case was already cleared (now UPHELD) is resolved by that decision
    # (R2): the case's latest UPHOLD row, on the row the case covers, for each record it names
    # (its own enrolment, or a related one at the case's institution)
    case_rows = ', '.join(f"('{t}', '{r}')" for t, r in CASE_ROWS)
    op.execute(
        "WITH upheld AS ("
        "  SELECT DISTINCT ON (ca.flag_id) ca.flag_id, ca.seq, ca.actor_id, ca.at"
        "  FROM case_actions ca JOIN flags f ON f.id = ca.flag_id"
        "  WHERE ca.action = 'UPHOLD' AND f.status = 'UPHELD'"
        "  ORDER BY ca.flag_id, ca.seq DESC"
        "), named AS ("
        "  SELECT f.id AS flag_id, m.row_type, e.id AS enrolment_id"
        f"  FROM flags f JOIN (VALUES {case_rows}) AS m(flag_type, row_type) ON m.flag_type = f.type::text"
        "  JOIN enrolments e ON e.id = f.enrolment_id"
        "    OR (e.id = ANY(f.related_enrolment_ids) AND e.institution_id = f.institution_id)"
        ") "
        "UPDATE checks c SET resolved = jsonb_build_object("
        "  'outcome', 'UPHELD', 'case_id', n.flag_id::text, 'case_action_seq', u.seq,"
        "  'by_id', u.actor_id::text,"
        "  'at', to_char(u.at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'),"
        "  'reason_code', 'OTHER') "
        "FROM named n JOIN upheld u ON u.flag_id = n.flag_id "
        "WHERE c.enrolment_id = n.enrolment_id AND c.type::text = n.row_type "
        "AND c.status = 'CONTRADICTED'"
    )

    # enrolments: the record status (D35) and reported eligibility markers (D41). Every row
    # starts AWAITING_EVIDENCE; app.seed computes the real status as its last step.
    op.add_column('enrolments', sa.Column('record_status', enrolments_record_status, server_default='AWAITING_EVIDENCE', nullable=False))
    op.add_column('enrolments', sa.Column('status_reason', sa.String(), nullable=True))
    op.add_column('enrolments', sa.Column('next_step', sa.String(), nullable=True))
    op.add_column('enrolments', sa.Column('record_status_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('enrolments', sa.Column('eligibility', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.create_index('ix_enrolments_institution_year_record_status', 'enrolments', ['institution_id', 'academic_year', 'record_status'], unique=False)

    # case_actions: the reason, correction and withdrawn enrolments of an outcome (D43)
    op.add_column('case_actions', sa.Column('reason_code', sa.String(), nullable=True))
    op.add_column('case_actions', sa.Column('correction', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('case_actions', sa.Column('withdrawn_enrolment_ids', postgresql.ARRAY(sa.UUID()), server_default=sa.text("'{}'::uuid[]"), nullable=False))
    op.execute("UPDATE case_actions SET reason_code = 'OTHER' WHERE action IN ('UPHOLD', 'WITHDRAW')")

    # enrolment_versions (D42)
    op.create_table('enrolment_versions',
    sa.Column('enrolment_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('batch_id', sa.UUID(), nullable=True),
    sa.Column('case_action_seq', sa.BigInteger(), nullable=True),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_enrolment_versions_actor_id_users')),
    sa.ForeignKeyConstraint(['batch_id'], ['upload_batches.id'], name=op.f('fk_enrolment_versions_batch_id_upload_batches')),
    sa.ForeignKeyConstraint(['case_action_seq'], ['case_actions.seq'], name=op.f('fk_enrolment_versions_case_action_seq_case_actions')),
    sa.ForeignKeyConstraint(['enrolment_id'], ['enrolments.id'], name=op.f('fk_enrolment_versions_enrolment_id_enrolments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enrolment_versions')),
    sa.UniqueConstraint('enrolment_id', 'version', name=op.f('uq_enrolment_versions_enrolment_id_version'))
    )

    # approval_versions (D41): one version 1 per approval, as recorded so far
    op.create_table('approval_versions',
    sa.Column('approval_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('approved_intake', sa.Integer(), nullable=False),
    sa.Column('effective_from', sa.Date(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['approval_id'], ['approvals.id'], name=op.f('fk_approval_versions_approval_id_approvals')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_approval_versions')),
    sa.UniqueConstraint('approval_id', 'version', name=op.f('uq_approval_versions_approval_id_version'))
    )
    op.add_column('approvals', sa.Column('current_version', sa.Integer(), server_default=sa.text('1'), nullable=False))
    op.execute(
        "INSERT INTO approval_versions (approval_id, version, approved_intake, effective_from, source) "
        "SELECT id, 1, approved_intake, created_at::date, 'Initial approval' FROM approvals"
    )

    # institution_column_mappings (D42)
    op.create_table('institution_column_mappings',
    sa.Column('institution_id', sa.UUID(), nullable=False),
    sa.Column('mapping', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'], name=op.f('fk_institution_column_mappings_institution_id_institutions')),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], name=op.f('fk_institution_column_mappings_updated_by_id_users')),
    sa.PrimaryKeyConstraint('institution_id', name=op.f('pk_institution_column_mappings'))
    )

    # signals (D45)
    op.create_table('signals',
    sa.Column('type', signals_type, nullable=False),
    sa.Column('academic_year', sa.String(), nullable=False),
    sa.Column('institution_ids', postgresql.ARRAY(sa.UUID()), nullable=False),
    sa.Column('enrolment_ids', postgresql.ARRAY(sa.UUID()), server_default=sa.text("'{}'::uuid[]"), nullable=False),
    sa.Column('summary', sa.String(), nullable=False),
    sa.Column('facts', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('rule', sa.String(), nullable=False),
    sa.Column('score', sa.Numeric(), nullable=True),
    sa.Column('status', signals_status, server_default='NEW', nullable=False),
    sa.Column('case_flag_id', sa.UUID(), nullable=True),
    sa.Column('dedupe_key', sa.String(), nullable=False),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('decided_by_id', sa.UUID(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['case_flag_id'], ['flags.id'], name=op.f('fk_signals_case_flag_id_flags')),
    sa.ForeignKeyConstraint(['decided_by_id'], ['users.id'], name=op.f('fk_signals_decided_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_signals')),
    sa.UniqueConstraint('dedupe_key', name=op.f('uq_signals_dedupe_key'))
    )

    # users: a STUDENT signed in through DigiLocker (D37)
    op.add_column('users', sa.Column('digilocker_sub', sa.String(), nullable=True))
    op.create_unique_constraint(op.f('uq_users_digilocker_sub'), 'users', ['digilocker_sub'])

    # institution_scores: the completeness percentage replaces the Integrity Index (D40); an
    # old index is not a completeness, so existing rows start null until the next
    # reconciliation
    op.alter_column('institution_scores', 'integrity_index', new_column_name='completeness_pct')
    op.alter_column('institution_scores', 'completeness_pct', existing_type=sa.Numeric(precision=5, scale=2), nullable=True)
    op.execute('UPDATE institution_scores SET completeness_pct = NULL')


def _rebuild_enum(name: str, labels: Sequence[str], columns: Sequence[tuple[str, str]], mapping: str) -> None:
    """Postgres cannot drop an enum label: move the type aside, create it again with `labels`,
    convert each column through `mapping` (a SQL expression over `{col}`), drop the old type."""
    op.execute(f'ALTER TYPE {name} RENAME TO {name}_0004')
    postgresql.ENUM(*labels, name=name).create(op.get_bind())
    for table, column in columns:
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} TYPE {name} '
            f'USING ({mapping.format(col=column)})::{name}'
        )
    op.execute(f'DROP TYPE {name}_0004')


def downgrade() -> None:
    bind = op.get_bind()

    op.execute('UPDATE institution_scores SET completeness_pct = 0 WHERE completeness_pct IS NULL')
    op.alter_column('institution_scores', 'completeness_pct', existing_type=sa.Numeric(precision=5, scale=2), nullable=False)
    op.alter_column('institution_scores', 'completeness_pct', new_column_name='integrity_index')

    op.drop_constraint(op.f('uq_users_digilocker_sub'), 'users', type_='unique')
    op.drop_column('users', 'digilocker_sub')

    op.drop_table('signals')
    op.drop_table('institution_column_mappings')
    op.drop_column('approvals', 'current_version')
    op.drop_table('approval_versions')
    op.drop_table('enrolment_versions')

    op.drop_column('case_actions', 'withdrawn_enrolment_ids')
    op.drop_column('case_actions', 'correction')
    op.drop_column('case_actions', 'reason_code')

    op.drop_index('ix_enrolments_institution_year_record_status', table_name='enrolments')
    op.drop_column('enrolments', 'eligibility')
    op.drop_column('enrolments', 'record_status_at')
    op.drop_column('enrolments', 'next_step')
    op.drop_column('enrolments', 'status_reason')
    op.drop_column('enrolments', 'record_status')

    op.drop_column('checks', 'resolved')
    op.drop_column('checks', 'independent')
    op.drop_column('checks', 'observed_at')
    op.drop_column('checks', 'supplied_by')

    for type_name, old, new in reversed(RENAMED_VALUES):
        op.execute(f"ALTER TYPE {type_name} RENAME VALUE '{new}' TO '{old}'")

    # The 0003 schema has no states, outcomes or case types for these: a check that is not
    # yet due reads as n/a and an unavailable source as pending again; a corrected case reads
    # as cleared and a CORRECT row as a note; cases of the new types are removed with their
    # history.
    _rebuild_enum(
        'checks_status', CHECKS_STATUS_0003, [('checks', 'status')],
        "CASE {col}::text WHEN 'NOT_YET_DUE' THEN 'NA' "
        "WHEN 'SOURCE_UNAVAILABLE' THEN 'PENDING' ELSE {col}::text END",
    )
    _rebuild_enum(
        'flags_status', FLAGS_STATUS_0003,
        [('flags', 'status'), ('case_actions', 'from_status'), ('case_actions', 'to_status')],
        "CASE {col}::text WHEN 'CORRECTED' THEN 'CLEARED' ELSE {col}::text END",
    )
    _rebuild_enum(
        'case_actions_action', CASE_ACTIONS_0003, [('case_actions', 'action')],
        "CASE {col}::text WHEN 'CORRECT' THEN 'NOTE' ELSE {col}::text END",
    )
    added = _sql_list(FLAGS_TYPE_ADDED)
    op.execute(
        'DELETE FROM case_attachments WHERE flag_id IN '
        f'(SELECT id FROM flags WHERE type::text IN ({added}))'
    )
    op.execute(
        'DELETE FROM case_actions WHERE flag_id IN '
        f'(SELECT id FROM flags WHERE type::text IN ({added}))'
    )
    op.execute(f'DELETE FROM flags WHERE type::text IN ({added})')
    _rebuild_enum('flags_type', FLAGS_TYPE_0003, [('flags', 'type')], '{col}::text')

    for enum_type in reversed(NEW_ENUMS):
        enum_type.drop(bind, checkfirst=True)
