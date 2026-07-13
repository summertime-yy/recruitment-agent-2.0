import React, { useEffect, useState } from 'react';
import { Row, Col, Button, Tag, Space, Skeleton, Card } from 'antd';
import { PlusOutlined, MessageOutlined, FileTextOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { jdApi } from '@/services/jd';
import type { JD } from '@/types';

const statusConfig = {
  DRAFT: { color: 'default', label: '草稿', bg: 'var(--bg-secondary)', dotColor: '#A8A29E' },
  PUBLISHED: { color: 'green', label: '已发布', bg: 'rgba(22,163,74,0.08)', dotColor: '#16A34A' },
  ARCHIVED: { color: 'red', label: '已归档', bg: 'rgba(220,38,38,0.06)', dotColor: '#DC2626' },
};

const TaskKanbanPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [jds, setJds] = useState<JD[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await jdApi.list({ page: 1, page_size: 50 });
      setJds(res.items || []);
    } catch (err) {
      console.error('Failed to load JDs:', err);
    } finally {
      setLoading(false);
    }
  };

  const draftJDs = jds.filter((j) => j.status === 'DRAFT');
  const publishedJDs = jds.filter((j) => j.status === 'PUBLISHED');
  const archivedJDs = jds.filter((j) => j.status === 'ARCHIVED');

  const quickActions = [
    { icon: <MessageOutlined />, label: '开始对话', desc: '通过AI对话完成招聘任务', path: '/chat', primary: true },
    { icon: <FileTextOutlined />, label: '生成 JD', desc: 'AI辅助生成职位描述', path: '/jds/generate' },
  ];

  const renderKanbanColumn = (title: string, items: JD[], config: typeof statusConfig.DRAFT, accentColor: string) => (
    <div className="kanban-column" style={{ borderTop: `3px solid ${accentColor}` }}>
      <div className="kanban-column-title">
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: config.dotColor }} />
        {title}
        <span className="kanban-column-count">{items.length}</span>
      </div>

      {loading ? (
        <div style={{ padding: 20 }}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </div>
      ) : items.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--ink-tertiary)', fontSize: '0.85rem' }}>
          暂无{title}
        </div>
      ) : (
        items.map((jd) => (
          <div key={jd.jd_id} className="kanban-card" onClick={() => navigate(`/jds/${jd.jd_id}`)}>
            <div className="kanban-card-title">{jd.title}</div>
            <div className="kanban-card-meta">
              {jd.department && <span>{jd.department}</span>}
              {jd.department && jd.location && <span>·</span>}
              {jd.location && <span>{jd.location}</span>}
              {!jd.department && !jd.location && <span>职位描述</span>}
            </div>
            <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {jd.required_skills?.slice(0, 3).map((skill, i) => (
                <Tag key={i} style={{ fontSize: '0.72rem', padding: '0 6px', lineHeight: '18px', margin: 0 }}>
                  {skill}
                </Tag>
              ))}
            </div>
            <div className="kanban-card-footer">
              <span style={{ fontSize: '0.75rem', color: 'var(--ink-tertiary)' }}>
                {dayjs(jd.created_at).format('MM-DD HH:mm')}
              </span>
              <Tag color={config.color as any} style={{ margin: 0, fontSize: '0.72rem' }}>
                {config.label}
              </Tag>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>任务看板</h1>
        <p style={{ color: 'var(--ink-secondary)', fontSize: '0.9rem', margin: 0 }}>管理招聘流程中的所有职位与任务</p>
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <div className="stat-card">
            <div className="stat-value">{loading ? '-' : jds.length}</div>
            <div className="stat-label">职位总数</div>
          </div>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <div className="stat-card" style={{ borderLeft: '3px solid #A8A29E' }}>
            <div className="stat-value">{loading ? '-' : draftJDs.length}</div>
            <div className="stat-label">草稿中</div>
          </div>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <div className="stat-card" style={{ borderLeft: '3px solid #16A34A' }}>
            <div className="stat-value" style={{ color: '#16A34A' }}>{loading ? '-' : publishedJDs.length}</div>
            <div className="stat-label">进行中（已发布）</div>
          </div>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <div className="stat-card" style={{ borderLeft: '3px solid #DC2626' }}>
            <div className="stat-value" style={{ color: '#DC2626' }}>{loading ? '-' : archivedJDs.length}</div>
            <div className="stat-label">已归档</div>
          </div>
        </Col>
      </Row>

      <Card style={{ marginBottom: 24, borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)' }}>
        <div style={{ padding: '8px 0' }}>
          <div style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 12 }}>快捷操作</div>
          <Space wrap>
            {quickActions.map((action, i) => (
              <Button
                key={i}
                type={action.primary ? 'primary' : 'default'}
                icon={action.icon}
                size="large"
                onClick={() => navigate(action.path)}
                style={{
                  borderRadius: 'var(--radius-md)',
                  height: 'auto',
                  padding: '12px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>{action.label}</div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.8, fontWeight: 400 }}>{action.desc}</div>
                </div>
              </Button>
            ))}
            <Button
              icon={<PlusOutlined />}
              size="large"
              onClick={() => navigate('/jds')}
              style={{
                borderRadius: 'var(--radius-md)',
                height: 'auto',
                padding: '12px 20px',
              }}
            >
              查看全部 JD
            </Button>
          </Space>
        </div>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          {renderKanbanColumn('草稿', draftJDs, statusConfig.DRAFT, '#A8A29E')}
        </Col>
        <Col xs={24} lg={8}>
          {renderKanbanColumn('已发布', publishedJDs, statusConfig.PUBLISHED, '#16A34A')}
        </Col>
        <Col xs={24} lg={8}>
          {renderKanbanColumn('已归档', archivedJDs, statusConfig.ARCHIVED, '#DC2626')}
        </Col>
      </Row>
    </div>
  );
};

export default TaskKanbanPage;
