import React, { useEffect, useState, useRef } from 'react';
import {
  Card,
  Button,
  Space,
  Tag,
  Spin,
  App,
  Typography,
  Timeline,
  Alert,
  Divider,
} from 'antd';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  PhoneOutlined,
  MailOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
  BankOutlined,
  SolutionOutlined,
  CodeOutlined,
  ProfileOutlined,
  EditOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import CandidateStatusSwitch from '@/components/CandidateStatusSwitch';
import CandidateStatusTimeline from '@/components/CandidateStatusTimeline';
import CandidateNotesCard from '@/components/CandidateNotesCard';
import { resumeApi } from '@/services/resume';
import type { Resume, ResumeParseStatus, EducationItem, WorkExperienceItem, ProjectExperienceItem } from '@/types';
import { DEDUP_STATUS_LABEL } from '@/types';
import ResumeEditModal from '@/components/ResumeEditModal';
import dayjs from 'dayjs';

const { Text, Paragraph } = Typography;

const parseStatusMap: Record<ResumeParseStatus, { color: string; text: string; icon: React.ReactNode }> = {
  PENDING: { color: 'default', text: '待解析', icon: <ClockCircleOutlined /> },
  PARSING: { color: 'processing', text: '解析中', icon: <LoadingOutlined /> },
  PARSED: { color: 'success', text: '已解析', icon: <CheckCircleOutlined /> },
  FAILED: { color: 'error', text: '解析失败', icon: <CloseCircleOutlined /> },
};

const formatFileSize = (bytes?: number) => {
  if (!bytes) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const ResumeDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState(false);
  const [statusRefreshKey, setStatusRefreshKey] = useState(0);
  const [resume, setResume] = useState<Resume | null>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchResume = async (silent = false) => {
    if (!id) return;
    if (!silent) setLoading(true);
    try {
      const res = await resumeApi.getById(id);
      setResume(res);
      return res;
    } catch (err) {
      console.error('Failed to fetch resume:', err);
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const stopPolling = () => {
    if (pollTimer.current) {
      clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    const poll = async () => {
      const updated = await fetchResume(true);
      if (!updated) {
        pollTimer.current = setTimeout(poll, 3000);
        return;
      }
      if (updated.parse_status === 'PARSED') {
        message.success(`${updated.candidate_name || updated.file_name} 解析完成`);
        setParsing(false);
        return;
      }
      if (updated.parse_status === 'FAILED') {
        message.error(`解析失败: ${updated.parse_error || '未知错误'}`);
        setParsing(false);
        return;
      }
      pollTimer.current = setTimeout(poll, 2000);
    };
    poll();
  };

  useEffect(() => {
    fetchResume();
    return () => stopPolling();
  }, [id]);

  useEffect(() => {
    if (resume?.parse_status === 'PARSING' && !pollTimer.current) {
      startPolling();
    }
    if (resume?.parse_status !== 'PARSING') {
      stopPolling();
    }
  }, [resume?.parse_status]);

  const handleParse = async () => {
    if (!id) return;
    setParsing(true);
    try {
      message.loading({ content: '正在开始解析...', key: 'parse' });
      await resumeApi.parse(id);
      message.success({ content: '已开始解析，请稍候...', key: 'parse' });
      setResume(prev => prev ? { ...prev, parse_status: 'PARSING', parse_error: undefined } : prev);
      startPolling();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      message.error({ content: detail || '解析失败', key: 'parse' });
      setParsing(false);
    }
  };

  const handleViewOriginal = () => {
    if (!id) return;
    const url = resumeApi.getPreviewUrl(id);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const handleEditSaved = (updated: Resume) => {
    setResume(updated);
    message.success('保存成功');
    setEditModalVisible(false);
  };

  const handleDedup = async (action: 'CONFIRM_DUP' | 'IGNORE' | 'RECHECK') => {
    if (!id) return;
    try {
      const updated = await resumeApi.handleDedup(id, action);
      setResume(updated);
      message.success('已更新');
    } catch {
      message.error('操作失败');
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16, color: 'var(--ink-tertiary)' }}>加载中...</div>
      </div>
    );
  }

  if (!resume) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <div style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: 8 }}>简历不存在</div>
        <div style={{ color: 'var(--ink-tertiary)', marginBottom: 24 }}>该简历可能已被删除或ID无效</div>
        <Button type="primary" onClick={() => navigate('/resumes')}>返回列表</Button>
      </div>
    );
  }

  const status = parseStatusMap[resume.parse_status];
  const parsed = resume.parsed_content;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('/resumes')} style={{ paddingLeft: 0, marginBottom: 8 }}>
          返回简历列表
        </Button>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
              {resume.file_type === 'pdf' ? (
                <FilePdfOutlined style={{ fontSize: '1.8rem', color: '#ef4444' }} />
              ) : (
                <FileWordOutlined style={{ fontSize: '1.8rem', color: '#2563eb' }} />
              )}
              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>
                {resume.candidate_name || resume.file_name.replace(/\.(pdf|docx)$/i, '')}
              </h1>
              <Tag icon={status.icon} color={status.color} style={{ fontSize: '0.85rem' }}>{status.text}</Tag>
              <Divider type="vertical" style={{ height: 20 }} />
              <span style={{ fontSize: '0.85rem', color: '#78716C' }}>候选人：</span>
              <CandidateStatusSwitch
                resumeId={resume.resume_id}
                status={resume.candidate_status}
                operator='recruiter'
                onChange={(newStatus) => { setResume(prev => prev ? { ...prev, candidate_status: newStatus } : prev); setStatusRefreshKey(k => k + 1); }}
              />
            </div>
            <Space size={12} wrap>
              {resume.phone && (
                <Space size={4}>
                  <PhoneOutlined style={{ color: '#78716C' }} />
                  <Text>{resume.phone}</Text>
                </Space>
              )}
              {resume.email && (
                <Space size={4}>
                  <MailOutlined style={{ color: '#78716C' }} />
                  <Text>{resume.email}</Text>
                </Space>
              )}
              <Text type="secondary">{resume.file_name}</Text>
              <Text type="secondary">·</Text>
              <Text type="secondary">{formatFileSize(resume.file_size)}</Text>
              {resume.parse_time_ms && (
                <>
                  <Text type="secondary">·</Text>
                  <Text type="secondary">解析耗时 {(resume.parse_time_ms / 1000).toFixed(1)}s</Text>
                </>
              )}
            </Space>
            <div style={{ marginTop: 4, color: '#78716C', fontSize: '0.85rem' }}>
              上传于 {dayjs(resume.created_at).format('YYYY-MM-DD HH:mm')}
            </div>
          </div>
          <Space>
            <Button icon={<EyeOutlined />} onClick={handleViewOriginal}>
              查看原始简历
            </Button>
            {resume.parse_status === 'PARSED' && (
              <Button icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>
                编辑修正
              </Button>
            )}
            {resume.parse_status === 'FAILED' || resume.parse_status === 'PENDING' ? (
              <Button type="primary" icon={<ReloadOutlined />} loading={parsing} onClick={handleParse}>
                {resume.parse_status === 'FAILED' ? '重新解析' : '开始解析'}
              </Button>
            ) : resume.parse_status === 'PARSED' ? (
              <Button icon={<ReloadOutlined />} loading={parsing} onClick={handleParse}>重新解析</Button>
            ) : null}
          </Space>
        </div>
      </div>

      {resume.parse_error && (
        <Alert
          message="解析失败"
          description={resume.parse_error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" danger onClick={handleParse} loading={parsing}>重试</Button>
          }
        />
      )}

      {resume.parse_status === 'PARSING' && (
        <Alert
          message="正在解析中"
          description="AI正在解析简历内容，请稍候..."
          type="info"
          showIcon
          icon={<LoadingOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      {parsed ? (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card
            title={
              <Space>
                <SolutionOutlined style={{ color: '#0D9488' }} />
                <span>候选人状态流转</span>
              </Space>
            }
          >
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">当前候选人状态：</Text>{' '}
              <CandidateStatusSwitch
                resumeId={resume.resume_id}
                status={resume.candidate_status}
                operator='recruiter'
                onChange={(newStatus) => { setResume(prev => prev ? { ...prev, candidate_status: newStatus } : prev); setStatusRefreshKey(k => k + 1); }}
              />
            </div>
            <Divider style={{ margin: '8px 0 16px' }} />
            <Text type="secondary">流转历史：</Text>
            <div style={{ marginTop: 12 }}>
              <CandidateStatusTimeline resumeId={resume.resume_id} refreshKey={statusRefreshKey} />
            </div>
          </Card>
          {resume.dedup_status && resume.dedup_status !== 'NONE' && (
            <Alert
              showIcon
              type={resume.dedup_status === 'CONFIRMED_DUP' ? 'error' : 'warning'}
              message={"疑似重复简历"}
              description={
                <Space>
                  <span>{DEDUP_STATUS_LABEL[resume.dedup_status]}</span>
                  {resume.dedup_status === 'SUSPECTED' && (
                    <>
                      <Button size='small' type='link' onClick={() => handleDedup('CONFIRM_DUP')}>确认重复</Button>
                      <Button size='small' type='link' onClick={() => handleDedup('IGNORE')}>忽略</Button>
                      <Button size='small' type='link' onClick={() => handleDedup('RECHECK')}>重新检测</Button>
                    </>
                  )}
                </Space>
              }
            />
          )}
          <CandidateNotesCard resumeId={resume.resume_id} refreshKey={statusRefreshKey} />
          {parsed.summary && (
            <Card
              title={
                <Space>
                  <ProfileOutlined style={{ color: '#0D9488' }} />
                  <span>个人简介</span>
                </Space>
              }
              extra={
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>编辑</Button>
              }
            >
              <Paragraph style={{ margin: 0, lineHeight: 1.8, color: '#57534E' }}>
                {parsed.summary}
              </Paragraph>
            </Card>
          )}

          {parsed.skills && parsed.skills.length > 0 && (
            <Card
              title={
                <Space>
                  <CodeOutlined style={{ color: '#0D9488' }} />
                  <span>技能标签</span>
                  <Tag color="blue" style={{ marginLeft: 8 }}>{parsed.skills.length} 项</Tag>
                </Space>
              }
              extra={
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>编辑</Button>
              }
            >
              <Space wrap size={[8, 8]}>
                {parsed.skills.map((skill, idx) => (
                  <Tag key={idx} color="blue" style={{ padding: '4px 12px', fontSize: '0.9rem' }}>
                    {skill}
                  </Tag>
                ))}
              </Space>
            </Card>
          )}

          {parsed.education && parsed.education.length > 0 && (
            <Card
              title={
                <Space>
                  <BankOutlined style={{ color: '#0D9488' }} />
                  <span>教育经历</span>
                </Space>
              }
              extra={
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>编辑</Button>
              }
            >
              <Timeline
                items={parsed.education.map((edu: EducationItem) => ({
                  children: (
                    <div style={{ paddingBottom: 8 }}>
                      <div style={{ fontWeight: 600, fontSize: '1rem', marginBottom: 4 }}>
                        {edu.school}
                      </div>
                      <Space split={<Text type="secondary">·</Text>}>
                        <Text>{edu.degree}</Text>
                        <Text>{edu.major}</Text>
                        {(edu.start_date || edu.end_date) && (
                          <Text type="secondary">{edu.start_date} - {edu.end_date || '至今'}</Text>
                        )}
                      </Space>
                    </div>
                  ),
                  color: 'blue',
                }))}
              />
            </Card>
          )}

          {parsed.work_experience && parsed.work_experience.length > 0 && (
            <Card
              title={
                <Space>
                  <SolutionOutlined style={{ color: '#0D9488' }} />
                  <span>工作经历</span>
                </Space>
              }
              extra={
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>编辑</Button>
              }
            >
              <Timeline
                items={parsed.work_experience.map((work: WorkExperienceItem) => ({
                  children: (
                    <div style={{ paddingBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                        <Text strong style={{ fontSize: '1rem' }}>{work.position}</Text>
                        {(work.start_date || work.end_date) && (
                          <Text type="secondary" style={{ fontSize: '0.85rem' }}>
                            {work.start_date} - {work.end_date || '至今'}
                          </Text>
                        )}
                      </div>
                      <div style={{ color: '#57534E', marginBottom: 8 }}>{work.company}</div>
                      {work.description && (
                        <Paragraph style={{ margin: 0, color: '#57534E', lineHeight: 1.7, fontSize: '0.9rem' }}>
                          {work.description}
                        </Paragraph>
                      )}
                    </div>
                  ),
                  color: 'green',
                }))}
              />
            </Card>
          )}

          {parsed.project_experience && parsed.project_experience.length > 0 && (
            <Card
              title={
                <Space>
                  <ProfileOutlined style={{ color: '#0D9488' }} />
                  <span>项目经历</span>
                </Space>
              }
              extra={
                <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditModalVisible(true)}>编辑</Button>
              }
            >
              <Timeline
                items={parsed.project_experience.map((proj: ProjectExperienceItem) => ({
                  children: (
                    <div style={{ paddingBottom: 12 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                        <Text strong style={{ fontSize: '1rem' }}>{proj.name}</Text>
                        {(proj.start_date || proj.end_date) && (
                          <Text type="secondary" style={{ fontSize: '0.85rem' }}>
                            {proj.start_date} - {proj.end_date || '至今'}
                          </Text>
                        )}
                      </div>
                      {proj.role && <div style={{ color: '#57534E', marginBottom: 6 }}>角色：{proj.role}</div>}
                      {proj.description && (
                        <Paragraph style={{ margin: 0, color: '#57534E', lineHeight: 1.7, fontSize: '0.9rem' }}>
                          {proj.description}
                        </Paragraph>
                      )}
                    </div>
                  ),
                  color: 'orange',
                }))}
              />
            </Card>
          )}
        </Space>
      ) : resume.parse_status === 'PENDING' ? (
        <Card style={{ textAlign: 'center', padding: '60px 0' }}>
          <ClockCircleOutlined style={{ fontSize: 48, color: '#A8A29E', opacity: 0.4, marginBottom: 16 }} />
          <div style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8 }}>简历待解析</div>
          <div style={{ color: '#78716C', marginBottom: 24 }}>点击右上角「开始解析」按钮，AI将提取简历中的结构化信息</div>
          <Button type="primary" size="large" icon={<ReloadOutlined />} loading={parsing} onClick={handleParse}>
            开始解析
          </Button>
        </Card>
      ) : null}

      {editModalVisible && resume && (
        <ResumeEditModal
          open={editModalVisible}
          resume={resume}
          onCancel={() => setEditModalVisible(false)}
          onSaved={handleEditSaved}
        />
      )}
    </div>
  );
};

export default ResumeDetailPage;
