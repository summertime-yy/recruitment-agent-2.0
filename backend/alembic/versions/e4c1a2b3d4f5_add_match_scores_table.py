"""add match_scores table

Revision ID: e4c1a2b3d4f5
Revises: 113702a6d427
Create Date: 2026-07-16 15:00:00.000000

Stage 4：人岗匹配评分表 match_scores
- 直接引用 resumes.resume_id（取代废弃的 candidate_id），jd_id/resume_id 均 ON DELETE CASCADE
- 唯一约束 uq_match_scores_jd_resume(jd_id, resume_id)
- 复合降序索引 idx_match_scores_jd_id_overall(jd_id, overall_score DESC) + idx_match_scores_resume_id
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e4c1a2b3d4f5'
down_revision: str = '113702a6d427'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'match_scores',
        sa.Column('score_id', sa.String(length=50), nullable=False),
        sa.Column('jd_id', sa.String(length=50), nullable=False),
        sa.Column('resume_id', sa.String(length=50), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False, comment='综合匹配度0-100'),
        sa.Column('dimension_scores', sa.JSON(), nullable=False,
                  comment='维度分：skill/experience/education + overall_reasoning'),
        sa.Column('matching_skill_id', sa.String(length=100), nullable=True, comment='匹配Skill ID'),
        sa.Column('matching_skill_version', sa.String(length=20), nullable=True, comment='匹配Skill版本'),
        sa.Column('skill_execution_id', sa.Integer(), nullable=True),
        sa.Column('resume_updated_at_snapshot', sa.DateTime(), nullable=True,
                  comment='生成时简历updated_at快照，用于陈旧判断'),
        sa.Column('jd_updated_at_snapshot', sa.DateTime(), nullable=True,
                  comment='生成时JD updated_at快照'),
        sa.Column('status', sa.String(length=20), server_default='COMPLETED', nullable=False,
                  comment='COMPLETED/FAILED/STALE'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Skill失败原因'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['jd_id'], ['jds.jd_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.resume_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['skill_execution_id'], ['skill_execution_logs.execution_id']),
        sa.PrimaryKeyConstraint('score_id'),
        sa.UniqueConstraint('jd_id', 'resume_id', name='uq_match_scores_jd_resume'),
    )
    op.create_index(
        'idx_match_scores_jd_id_overall', 'match_scores',
        ['jd_id', sa.text('overall_score DESC')], unique=False,
    )
    op.create_index('idx_match_scores_resume_id', 'match_scores', ['resume_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_match_scores_resume_id', table_name='match_scores')
    op.drop_index('idx_match_scores_jd_id_overall', table_name='match_scores')
    op.drop_table('match_scores')
