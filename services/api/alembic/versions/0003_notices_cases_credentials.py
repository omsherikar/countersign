"""notice delivery, case history and attachments, signing and holder keys, presentations, consent and data request fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28 21:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


notifications_delivery = postgresql.ENUM('QUEUED', 'SENT', 'FAILED', name='notifications_delivery', create_type=False)
notifications_response = postgresql.ENUM('YES', 'NO', name='notifications_response', create_type=False)
flags_status = postgresql.ENUM(
    'OPEN', 'DOCS_REQUESTED', 'CLEARED', 'ESCALATED', 'CONFIRMED', name='flags_status', create_type=False,
)
CASE_ACTIONS_0002 = ('CLEAR', 'REQUEST_DOCS', 'ESCALATE', 'CONFIRM', 'NOTE', 'COLLEGE_RESPONSE')
CASE_ACTIONS_ADDED = ('ASSIGN', 'REOPEN', 'SYSTEM_NOTE')


def upgrade() -> None:
    bind = op.get_bind()
    notifications_delivery.create(bind, checkfirst=True)
    for value in CASE_ACTIONS_ADDED:
        op.execute(f"ALTER TYPE case_actions_action ADD VALUE IF NOT EXISTS '{value}'")

    # notifications: only sha256(token) is kept from now on, so hash any stored token
    op.alter_column('notifications', 'token', new_column_name='token_hash')
    op.execute('ALTER TABLE notifications RENAME CONSTRAINT uq_notifications_token TO uq_notifications_token_hash')
    op.execute("UPDATE notifications SET token_hash = encode(sha256(convert_to(token_hash, 'UTF8')), 'hex')")
    op.add_column('notifications', sa.Column('delivery_status', notifications_delivery, server_default='QUEUED', nullable=False))
    op.add_column('notifications', sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('notifications', sa.Column('last_error', sa.String(), nullable=True))
    op.add_column('notifications', sa.Column('comment', sa.String(), nullable=True))
    op.add_column('notifications', sa.Column('previous_response', notifications_response, nullable=True))
    op.add_column('notifications', sa.Column('changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notifications', sa.Column('resent_by_id', sa.UUID(), nullable=True))
    op.execute("UPDATE notifications SET delivery_status = 'SENT' WHERE sent_at IS NOT NULL")
    op.create_foreign_key(op.f('fk_notifications_resent_by_id_users'), 'notifications', 'users', ['resent_by_id'], ['id'])
    op.create_index('ix_notifications_enrolment_id_channel', 'notifications', ['enrolment_id', 'channel'], unique=False)

    # case_actions: system rows have no actor; status moves are recorded on each row
    op.alter_column('case_actions', 'actor_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('case_actions', sa.Column('from_status', flags_status, nullable=True))
    op.add_column('case_actions', sa.Column('to_status', flags_status, nullable=True))
    op.add_column('case_actions', sa.Column('due_date', sa.Date(), nullable=True))
    op.add_column('case_actions', sa.Column('assignee_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_case_actions_assignee_id_users'), 'case_actions', 'users', ['assignee_id'], ['id'])

    # flags
    op.add_column('flags', sa.Column('docs_due_on', sa.Date(), nullable=True))
    op.add_column('flags', sa.Column('response_received', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('flags', sa.Column('last_action_at', sa.DateTime(timezone=True), nullable=True))

    # case_attachments
    op.create_table('case_attachments',
    sa.Column('flag_id', sa.UUID(), nullable=False),
    sa.Column('case_action_seq', sa.BigInteger(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('content_type', sa.String(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.CHAR(length=64), nullable=False),
    sa.Column('storage_key', sa.String(), nullable=False),
    sa.Column('uploaded_by_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['case_action_seq'], ['case_actions.seq'], name=op.f('fk_case_attachments_case_action_seq_case_actions')),
    sa.ForeignKeyConstraint(['flag_id'], ['flags.id'], name=op.f('fk_case_attachments_flag_id_flags')),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_case_attachments_uploaded_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_attachments')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_case_attachments_storage_key'))
    )
    op.create_index(op.f('ix_case_attachments_flag_id'), 'case_attachments', ['flag_id'], unique=False)

    # signing_keys
    op.create_table('signing_keys',
    sa.Column('kid', sa.String(), nullable=False),
    sa.Column('alg', sa.String(), nullable=False),
    sa.Column('purpose', sa.String(), server_default='ISSUER', nullable=False),
    sa.Column('public_jwk', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('private_jwk_encrypted', sa.String(), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('kid', name=op.f('pk_signing_keys'))
    )
    op.create_index('uq_signing_keys_purpose_active', 'signing_keys', ['purpose'], unique=True, postgresql_where=sa.text('active'))

    # holder_keys
    op.create_table('holder_keys',
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('public_jwk', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('private_jwk_encrypted', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_holder_keys_student_id_students')),
    sa.PrimaryKeyConstraint('student_id', name=op.f('pk_holder_keys'))
    )

    # credentials: no Week 2 code issues credentials, but backfill so upgrade works on any data
    op.add_column('credentials', sa.Column('vct', sa.String(), nullable=True))
    op.add_column('credentials', sa.Column('short_id', sa.String(), nullable=True))
    op.add_column('credentials', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('credentials', sa.Column('revoked_reason', sa.String(), nullable=True))
    op.add_column('credentials', sa.Column('revoked_by_id', sa.UUID(), nullable=True))
    op.add_column('credentials', sa.Column('disclosable', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::text[]"), nullable=False))
    op.execute(
        "UPDATE credentials SET vct = format('countersign:%s:v1', lower(kind::text)), "
        "short_id = upper(substr(md5(id::text), 1, 12))"
    )
    op.alter_column('credentials', 'vct', nullable=False)
    op.alter_column('credentials', 'short_id', nullable=False)
    op.create_unique_constraint(op.f('uq_credentials_short_id'), 'credentials', ['short_id'])
    op.create_foreign_key(op.f('fk_credentials_revoked_by_id_users'), 'credentials', 'users', ['revoked_by_id'], ['id'])
    op.create_index('uq_credentials_enrolment_id_kind', 'credentials', ['enrolment_id', 'kind'], unique=True, postgresql_where=sa.text('revoked = false'))

    # credential_presentations
    op.create_table('credential_presentations',
    sa.Column('credential_id', sa.UUID(), nullable=False),
    sa.Column('code_hash', sa.CHAR(length=64), nullable=False),
    sa.Column('presentation', sa.String(), nullable=False),
    sa.Column('disclosed', postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'::text[]"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('first_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verify_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['credential_id'], ['credentials.id'], name=op.f('fk_credential_presentations_credential_id_credentials')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_credential_presentations')),
    sa.UniqueConstraint('code_hash', name=op.f('uq_credential_presentations_code_hash'))
    )
    op.create_index(op.f('ix_credential_presentations_credential_id'), 'credential_presentations', ['credential_id'], unique=False)

    # consents
    op.add_column('consents', sa.Column('enrolment_id', sa.UUID(), nullable=True))
    op.add_column('consents', sa.Column('notice_version', sa.String(), server_default='v1', nullable=False))
    op.add_column('consents', sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(op.f('fk_consents_enrolment_id_enrolments'), 'consents', 'enrolments', ['enrolment_id'], ['id'])

    # data_requests
    op.add_column('data_requests', sa.Column('details', sa.String(), nullable=True))
    op.add_column('data_requests', sa.Column('response', sa.String(), nullable=True))
    op.add_column('data_requests', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('data_requests', sa.Column('resolved_by_id', sa.UUID(), nullable=True))
    op.create_foreign_key(op.f('fk_data_requests_resolved_by_id_users'), 'data_requests', 'users', ['resolved_by_id'], ['id'])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(op.f('fk_data_requests_resolved_by_id_users'), 'data_requests', type_='foreignkey')
    op.drop_column('data_requests', 'resolved_by_id')
    op.drop_column('data_requests', 'resolved_at')
    op.drop_column('data_requests', 'response')
    op.drop_column('data_requests', 'details')

    op.drop_constraint(op.f('fk_consents_enrolment_id_enrolments'), 'consents', type_='foreignkey')
    op.drop_column('consents', 'withdrawn_at')
    op.drop_column('consents', 'notice_version')
    op.drop_column('consents', 'enrolment_id')

    op.drop_index(op.f('ix_credential_presentations_credential_id'), table_name='credential_presentations')
    op.drop_table('credential_presentations')

    op.drop_index('uq_credentials_enrolment_id_kind', table_name='credentials', postgresql_where=sa.text('revoked = false'))
    op.drop_constraint(op.f('fk_credentials_revoked_by_id_users'), 'credentials', type_='foreignkey')
    op.drop_constraint(op.f('uq_credentials_short_id'), 'credentials', type_='unique')
    op.drop_column('credentials', 'disclosable')
    op.drop_column('credentials', 'revoked_by_id')
    op.drop_column('credentials', 'revoked_reason')
    op.drop_column('credentials', 'expires_at')
    op.drop_column('credentials', 'short_id')
    op.drop_column('credentials', 'vct')

    op.drop_table('holder_keys')

    op.drop_index('uq_signing_keys_purpose_active', table_name='signing_keys', postgresql_where=sa.text('active'))
    op.drop_table('signing_keys')

    op.drop_index(op.f('ix_case_attachments_flag_id'), table_name='case_attachments')
    op.drop_table('case_attachments')

    op.drop_column('flags', 'last_action_at')
    op.drop_column('flags', 'response_received')
    op.drop_column('flags', 'docs_due_on')

    op.drop_constraint(op.f('fk_case_actions_assignee_id_users'), 'case_actions', type_='foreignkey')
    op.drop_column('case_actions', 'assignee_id')
    op.drop_column('case_actions', 'due_date')
    op.drop_column('case_actions', 'to_status')
    op.drop_column('case_actions', 'from_status')
    # Week 2 has no system rows and no ASSIGN/REOPEN/SYSTEM_NOTE: drop the first, keep the
    # rest as notes, then rebuild the enum without the added values (Postgres cannot drop one).
    op.execute('DELETE FROM case_actions WHERE actor_id IS NULL')
    op.execute(
        "UPDATE case_actions SET action = 'NOTE' "
        "WHERE action::text IN (" + ", ".join(f"'{v}'" for v in CASE_ACTIONS_ADDED) + ")"
    )
    op.alter_column('case_actions', 'actor_id', existing_type=sa.UUID(), nullable=False)
    op.execute('ALTER TYPE case_actions_action RENAME TO case_actions_action_0003')
    postgresql.ENUM(*CASE_ACTIONS_0002, name='case_actions_action').create(bind)
    op.execute(
        'ALTER TABLE case_actions ALTER COLUMN action TYPE case_actions_action '
        'USING action::text::case_actions_action'
    )
    op.execute('DROP TYPE case_actions_action_0003')

    # stored values stay hashes: a link token cannot be recovered from its hash
    op.drop_index('ix_notifications_enrolment_id_channel', table_name='notifications')
    op.drop_constraint(op.f('fk_notifications_resent_by_id_users'), 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'resent_by_id')
    op.drop_column('notifications', 'changed_at')
    op.drop_column('notifications', 'previous_response')
    op.drop_column('notifications', 'comment')
    op.drop_column('notifications', 'last_error')
    op.drop_column('notifications', 'attempts')
    op.drop_column('notifications', 'delivery_status')
    op.execute('ALTER TABLE notifications RENAME CONSTRAINT uq_notifications_token_hash TO uq_notifications_token')
    op.alter_column('notifications', 'token_hash', new_column_name='token')

    notifications_delivery.drop(bind, checkfirst=True)
