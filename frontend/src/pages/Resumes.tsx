import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Space,
  Tag,
  Input,
  Select,
  Upload,
  App,
  Typography,
  UploadProps,
  Popconfirm,
  Breadcrumb,
  Badge,
  Card,
} from 'antd';
import {
  FilePdfOutlined,
  FileWordOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  UploadOutlined,
  ExportOutlined,
  PlusOutlined,
  HistoryOutlined,
  CloseCircleFilled,
  LinkOutlined,
  LoadingOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import { resumeApi } from '@/services/resume';
import { jdApi } from '@/services/jd';
import { matchApi } from '@/services/match';
import type { Resume, ResumeParseStatus, CandidateStatus, DedupStatus, TagsMetaResponse, JD } from '@/types';
import ResumeEditModal from '@/components/ResumeEditModal';
import CandidateStatusSwitch from '@/components/CandidateStatusSwitch';

const { Dragger } = Upload;
const { Text } = Typography;
const { Search } = Input;

const parseStatusConfig: Record<ResumeParseStatus, { color: string; text: string; bgColor: string }> = {
  PENDING: { color: 'default', text: '待解析', bgColor: '#f5f5f5' },
  PARSING: { color: 'processing', text: '解析中', bgColor: '#e6f7ff' },
  PARSED: { color: 'success', text: '解析成功', bgColor: '#f6ffed' },
  FAILED: { color: 'error', text: '解析失败', bgColor: '#fff2f0' },
};

const ScoreRing: React.FC<{ score: number }> = ({ score }) => {
  let color = '#52c41a';
  if (score < 60) color = '#ff4d4f';
  else if (score < 80) color = '#faad14';
  return (
    <div style={{
      width: 36,
      height: 36,
      borderRadius: '50%',
      border: `3px solid ${color}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '0.75rem',
      fontWeight: 600,
      color,
    }}>
      {score}
    </div>
  );
};

const ResumesPage: React.FC = () => {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [keyword, setKeyword] = useState('');
  const [parseStatus, setParseStatus] = useState<ResumeParseStatus | undefined>(undefined);
  const [candidateStatus, setCandidateStatus] = useState<CandidateStatus | undefined>(undefined);
  const [tagFilter, setTagFilter] = useState<string | undefined>(undefined);
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined);
  const [dedupFilter, setDedupFilter] = useState<DedupStatus | undefined>(undefined);
  const [tagsMeta, setTagsMeta] = useState<TagsMetaResponse>({ tags: [], sources: [] });
  const [uploading, setUploading] = useState(false);
  const [stats, setStats] = useState({ total: 0, parsed: 0, pending: 0, failed: 0 });
  const [parsingIds, setParsingIds] = useState<Set<string>>(new Set());
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);
  const [selectedResume, setSelectedResume] = useState<Resume | null>(null);
  const [matchJds, setMatchJds] = useState<JD[]>([]);
  const [matchAgainstJdId, setMatchAgainstJdId] = useState<string | undefined>();
  const [matchScoreMap, setMatchScoreMap] = useState<Record<string, number>>({});
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingResume, setEditingResume] = useState<Resume | null>(null);
  const pollingTimers = React.useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const fetchAllStats = async () => {
    try {
      const res = await resumeApi.list({ page, page_size: pageSize, keyword: keyword || undefined, parse_status: parseStatus, candidate_status: candidateStatus, tag: tagFilter, source: sourceFilter, dedup_status: dedupFilter });
      const items = res.items;
      setStats({
        total: res.total,
        parsed: items.filter(r => r.parse_status === 'PARSED').length,
        pending: items.filter(r => r.parse_status === 'PENDING' || r.parse_status === 'PARSING').length,
        failed: items.filter(r => r.parse_status === 'FAILED').length,
      });
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const stopPolling = (resumeId: string) => {
    const timer = pollingTimers.current.get(resumeId);
    if (timer) {
      clearTimeout(timer);
      pollingTimers.current.delete(resumeId);
    }
    setParsingIds(prev => {
      const next = new Set(prev);
      next.delete(resumeId);
      return next;
    });
  };

  const startPolling = (resumeId: string) => {
    setParsingIds(prev => new Set(prev).add(resumeId));

    const poll = async () => {
      try {
        const updated = await resumeApi.getById(resumeId);
        setResumes(prev => prev.map(r => r.resume_id === resumeId ? updated : r));

        if (updated.parse_status === 'PARSED') {
          stopPolling(resumeId);
          message.success(`${updated.candidate_name || updated.file_name} 解析完成`);
          if (selectedResume?.resume_id === resumeId) {
            setSelectedResume(updated);
          }
          fetchAllStats();
          return;
        }
        if (updated.parse_status === 'FAILED') {
          stopPolling(resumeId);
          message.error(`${updated.file_name} 解析失败: ${updated.parse_error || '未知错误'}`);
          fetchAllStats();
          return;
        }

        pollingTimers.current.set(resumeId, setTimeout(poll, 2000));
      } catch (err) {
        console.error('Polling error:', err);
        pollingTimers.current.set(resumeId, setTimeout(poll, 3000));
      }
    };

    poll();
  };

  React.useEffect(() => {
    return () => {
      pollingTimers.current.forEach(timer => clearTimeout(timer));
      pollingTimers.current.clear();
    };
  }, []);

  const fetchResumes = async () => {
    setLoading(true);
    try {
      const res = await resumeApi.list({ page, page_size: pageSize, keyword: keyword || undefined, parse_status: parseStatus, candidate_status: candidateStatus });
      setResumes(res.items);
      setTotal(res.total);
      if (!keyword && !parseStatus && !candidateStatus && !tagFilter && !sourceFilter && !dedupFilter) {
        setStats({
          total: res.total,
          parsed: res.items.filter(r => r.parse_status === 'PARSED').length,
          pending: res.items.filter(r => r.parse_status === 'PENDING' || r.parse_status === 'PARSING').length,
          failed: res.items.filter(r => r.parse_status === 'FAILED').length,
        });
      } else {
        fetchAllStats();
      }
    } catch (err) {
      console.error('Failed to fetch resumes:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchResumes();
  }, [page, pageSize, parseStatus, candidateStatus, keyword, tagFilter, sourceFilter, dedupFilter]);

  useEffect(() => {
    resumeApi.getTagsMeta().then(setTagsMeta).catch(() => {});
  }, []);

  useEffect(() => {
    jdApi.list({ page_size: 200 }).then((res) => setMatchJds(res.items)).catch(() => setMatchJds([]));
  }, []);

  useEffect(() => {
    if (!matchAgainstJdId) {
      setMatchScoreMap({});
      return;
    }
    let cancelled = false;
    matchApi
      .rankByJd(matchAgainstJdId, { limit: 200 })
      .then((res) => {
        if (cancelled) return;
        const map: Record<string, number> = {};
        res.items.forEach((it) => { map[it.resume_id] = it.overall_score; });
        setMatchScoreMap(map);
      })
      .catch(() => { if (!cancelled) setMatchScoreMap({}); });
    return () => { cancelled = true; };
  }, [matchAgainstJdId]);

  const handleSearch = (value: string) => {
    setKeyword(value);
    setPage(1);
    setTimeout(fetchResumes, 0);
  };

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    showUploadList: false,
    accept: '.pdf,.docx',
    beforeUpload: async (file) => {
      const isPdfOrDocx = file.type === 'application/pdf' ||
        file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
        file.name.endsWith('.pdf') || file.name.endsWith('.docx');
      if (!isPdfOrDocx) {
        message.error('只支持 PDF 和 DOCX 格式');
        return Upload.LIST_IGNORE;
      }
      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('文件大小不能超过 10MB');
        return Upload.LIST_IGNORE;
      }
      return true;
    },
    customRequest: async ({ file, onSuccess, onError }) => {
      setUploading(true);
      try {
        const uploadRes = await resumeApi.upload(file as File, true);
        message.success(`${(file as File).name} 上传成功，开始后台解析...`);
        await fetchResumes();
        startPolling(uploadRes.resume_id);
        onSuccess?.(null);
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        if (err.code === 'ERR_NETWORK' || !err.response) {
          message.error('网络错误，请检查后端服务是否启动');
        } else {
          message.error(detail || `${(file as File).name} 上传失败`);
        }
        onError?.(err as Error);
      } finally {
        setUploading(false);
      }
    },
  };

  const handleParse = async (resumeId: string) => {
    try {
      await resumeApi.parse(resumeId);
      message.loading({ content: '已开始后台解析，状态将自动更新...', key: `parse-${resumeId}`, duration: 2 });
      startPolling(resumeId);
      setResumes(prev => prev.map(r =>
        r.resume_id === resumeId ? { ...r, parse_status: 'PARSING' as const, parse_error: undefined } : r
      ));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err.code === 'ERR_NETWORK' || !err.response) {
        message.error('网络错误，请检查后端服务是否启动');
      } else {
        message.error(detail || '启动解析失败');
      }
    }
  };

  const handleDelete = async (resumeId: string) => {
    try {
      await resumeApi.delete(resumeId);
      message.success('删除成功');
      if (selectedResume?.resume_id === resumeId) {
        setSelectedResume(null);
      }
      fetchResumes();
    } catch (err) {
      console.error('Failed to delete resume:', err);
      message.error('删除失败');
    }
  };

  const handlePreview = (resumeId: string) => {
    navigate(`/resumes/${resumeId}`);
  };

  const handleViewOriginalFile = (resumeId: string) => {
    const url = resumeApi.getPreviewUrl(resumeId);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const handleOpenEdit = (record: Resume) => {
    setEditingResume(record);
    setEditModalVisible(true);
  };

  const handleEditSaved = (updated: Resume) => {
    setResumes(prev => prev.map(r => r.resume_id === updated.resume_id ? updated : r));
    if (selectedResume?.resume_id === updated.resume_id) {
      setSelectedResume(updated);
    }
    message.success('保存成功');
    setEditModalVisible(false);
    setEditingResume(null);
  };

  const handleParseAll = () => {
    message.info('批量解析功能开发中');
  };

  const handleExport = () => {
    message.info('批量导出功能开发中');
  };

  const toggleExpand = (resumeId: string) => {
    setExpandedRowKeys(prev =>
      prev.includes(resumeId) ? prev.filter(k => k !== resumeId) : [...prev, resumeId]
    );
  };

  const columns: ColumnsType<Resume> = [
    {
      title: '#',
      key: 'index',
      width: 50,
      align: 'center',
      render: (_, __, idx) => (page - 1) * pageSize + idx + 1,
    },
    {
      title: '姓名',
      dataIndex: 'candidate_name',
      key: 'candidate_name',
      width: 130,
      render: (text, record) => (
        <Space>
          {record.file_type === 'pdf'
            ? <FilePdfOutlined style={{ color: '#ef4444', fontSize: '1rem' }} />
            : <FileWordOutlined style={{ color: '#2563eb', fontSize: '1rem' }} />}
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
              {text || record.file_name.replace(/\.(pdf|docx)$/i, '').substring(0, 12)}
            </div>
            <Text type="secondary" style={{ fontSize: '0.75rem' }}>{record.file_name.substring(0, 18)}</Text>
          </div>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'parse_status',
      key: 'parse_status',
      width: 100,
      render: (status: ResumeParseStatus, record) => (
        <Tag
          color={parseStatusConfig[status].color}
          style={{ borderRadius: 4, margin: 0 }}
          icon={(status === 'PARSING' || parsingIds.has(record.resume_id)) ? <LoadingOutlined /> : undefined}
        >
          {parsingIds.has(record.resume_id) ? '解析中' : parseStatusConfig[status].text}
        </Tag>
      ),
    },
    {
      title: '候选人状态',
      dataIndex: 'candidate_status',
      key: 'candidate_status',
      width: 130,
      render: (status: CandidateStatus, record: Resume) => (
        <CandidateStatusSwitch
          resumeId={record.resume_id}
          status={status}
          operator='recruiter'
          onChange={() => {
            // 切换后刷新列表以同步状态
            fetchResumes();
          }}
        />
      ),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags?: string[], record?: Resume) => (
        <Space size={4} wrap>
          {(tags || []).map(t => <Tag key={t} color='blue'>{t}</Tag>)}
          {record?.dedup_status && record.dedup_status !== 'NONE' && (
            <Tag color={record.dedup_status === 'SUSPECTED' ? 'warning' : record.dedup_status === 'CONFIRMED_DUP' ? 'error' : 'default'}>
              {record.dedup_status === 'SUSPECTED' ? '疑似重复' : record.dedup_status === 'CONFIRMED_DUP' ? '重复' : '已忽略'}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '联系方式',
      key: 'contact',
      width: 150,
      render: (_, record) => (
        <div>
          {record.phone ? <div style={{ fontSize: '0.8rem' }}>{record.phone}</div> : <Text type="secondary" style={{ fontSize: '0.8rem' }}>-</Text>}
          {record.email ? <div style={{ fontSize: '0.75rem', color: '#8c8c8c' }}>{record.email.substring(0, 20)}</div> : null}
        </div>
      ),
    },
    {
      title: '最新公司',
      key: 'latest_company',
      width: 120,
      render: (_, record) => {
        const latest = record.parsed_content?.work_experience?.[0];
        return latest?.company ? <Text style={{ fontSize: '0.85rem' }}>{latest.company.substring(0, 8)}</Text> : <Text type="secondary" style={{ fontSize: '0.85rem' }}>-</Text>;
      },
    },
    {
      title: '核心技能',
      key: 'skills',
      render: (_, record) => {
        const skills = record.parsed_content?.skills || [];
        return skills.length ? (
          <Space wrap size={[4, 4]}>
            {skills.slice(0, 5).map((s, i) => (
              <Tag key={i} style={{ fontSize: '0.75rem', borderRadius: 4, margin: 0 }}>{s}</Tag>
            ))}
            {skills.length > 5 && <Text type="secondary" style={{ fontSize: '0.75rem' }}>+{skills.length - 5}</Text>}
          </Space>
        ) : <Text type="secondary" style={{ fontSize: '0.85rem' }}>-</Text>;
      },
    },
    {
      title: '匹配分',
      key: 'matchScore',
      width: 70,
      align: 'center',
      render: (_, record) => {
        const score = matchScoreMap[record.resume_id];
        const hasScore = matchAgainstJdId !== undefined && score !== undefined;
        return (
          <span data-testid={`confidence-${record.resume_id}`}>
            {hasScore ? <ScoreRing score={score as number} /> : <Text type="secondary">-</Text>}
          </span>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_, record) => (
        <Space size={2}>
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handlePreview(record.resume_id)}
            title="预览原始简历"
          >
            预览
          </Button>
          {record.parse_status === 'PARSED' && (
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleOpenEdit(record)}
              style={{ color: '#0D9488' }}
            >
              编辑
            </Button>
          )}
          {(record.parse_status === 'FAILED' || record.parse_status === 'PENDING') && (
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined />}
              loading={parsingIds.has(record.resume_id)}
              onClick={() => handleParse(record.resume_id)}
              style={{ color: '#faad14' }}
            >
              解析
            </Button>
          )}
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.resume_id)} okText="删除" cancelText="取消">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const expandedRowRender = (record: Resume) => {
    if (record.parse_status === 'FAILED') {
      return (
        <div style={{ padding: '8px 16px', background: '#fff2f0', borderRadius: 4 }}>
          <Text type="danger" style={{ fontSize: '0.85rem' }}>失败原因：{record.parse_error}</Text>
          <Button
            type="link"
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => handleParse(record.resume_id)}
            style={{ marginLeft: 12 }}
          >
            重新解析
          </Button>
        </div>
      );
    }
    if (record.parse_status === 'PARSING' || parsingIds.has(record.resume_id)) {
      return (
        <div style={{ padding: '8px 16px' }}>
          <Text type="secondary" style={{ fontSize: '0.85rem' }}><LoadingOutlined /> 正在后台解析中，请稍候...</Text>
        </div>
      );
    }
    if (record.parse_status !== 'PARSED' || !record.parsed_content) {
      return (
        <div style={{ padding: '8px 16px' }}>
          <Text type="secondary" style={{ fontSize: '0.85rem' }}>等待解析</Text>
          <Button type="link" size="small" onClick={() => handleParse(record.resume_id)}>立即解析</Button>
        </div>
      );
    }
    const pc = record.parsed_content;
    return (
      <div style={{ padding: '12px 24px', background: '#fafafa' }}>
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Space>
              <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewOriginalFile(record.resume_id)}>
                查看原始简历
              </Button>
              <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenEdit(record)}>
                编辑修正
              </Button>
            </Space>
            <Text type="secondary" style={{ fontSize: '0.75rem' }}>
              解析版本: {record.parsing_skill_version} | 耗时: {record.parse_time_ms ? (record.parse_time_ms / 1000).toFixed(1) + 's' : '-'}
            </Text>
          </div>

          {pc.summary && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>个人简介：</Text>
              <Text style={{ fontSize: '0.85rem' }}>{pc.summary}</Text>
            </div>
          )}
          {(record.phone || record.email) && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>联系方式：</Text>
              <Text style={{ fontSize: '0.85rem' }}>{[record.phone, record.email].filter(Boolean).join(' | ')}</Text>
            </div>
          )}
          {pc.education?.length > 0 && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>教育经历：</Text>
              <Space size={8} wrap style={{ marginTop: 4 }}>
                {pc.education.map((edu, i) => (
                  <Tag key={i} style={{ fontSize: '0.8rem', padding: '2px 8px' }}>
                    {edu.school} · {edu.degree} · {edu.major}
                    {edu.start_date && ` (${edu.start_date}~${edu.end_date || '至今'})`}
                  </Tag>
                ))}
              </Space>
            </div>
          )}
          {pc.work_experience?.length > 0 && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>工作经历：</Text>
              <div style={{ marginTop: 4 }}>
                {pc.work_experience.map((w, i) => (
                  <div key={i} style={{ fontSize: '0.82rem', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #0D9488' }}>
                    <Text strong>{w.company}</Text> - {w.position}
                    <Text type="secondary" style={{ marginLeft: 8 }}>{w.start_date} ~ {w.end_date || '至今'}</Text>
                    {w.description && <div style={{ color: '#595959', marginTop: 2 }}>{w.description.substring(0, 100)}{w.description.length > 100 ? '...' : ''}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {pc.project_experience?.length > 0 && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>项目经历：</Text>
              <div style={{ marginTop: 4 }}>
                {pc.project_experience.slice(0, 3).map((p, i) => (
                  <div key={i} style={{ fontSize: '0.82rem', marginBottom: 4, paddingLeft: 8, borderLeft: '2px solid #722ed1' }}>
                    <Text strong>{p.name}</Text>
                    {p.role && <Text type="secondary" style={{ marginLeft: 8 }}>{p.role}</Text>}
                  </div>
                ))}
                {pc.project_experience.length > 3 && (
                  <Text type="secondary" style={{ fontSize: '0.8rem' }}>...还有 {pc.project_experience.length - 3} 个项目</Text>
                )}
              </div>
            </div>
          )}
          {pc.skills?.length > 0 && (
            <div>
              <Text strong style={{ fontSize: '0.85rem' }}>技能标签：</Text>
              <Space size={[4, 4]} wrap style={{ marginTop: 4 }}>
                {pc.skills.map((s, i) => (
                  <Tag key={i} color="teal" style={{ fontSize: '0.78rem', borderRadius: 4, margin: 0 }}>{s}</Tag>
                ))}
              </Space>
            </div>
          )}
        </Space>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      <div style={{ padding: '16px 24px 0', borderBottom: '1px solid #f0f0f0', background: '#fff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <Breadcrumb items={[{ title: '智能招聘 Agent' }, { title: '简历工作台' }]} style={{ marginBottom: 8 }} />
            <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700 }}>简历工作台</h2>
          </div>
          <Space>
            <Button icon={<HistoryOutlined />}>历史记录</Button>
          </Space>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <Space size={8} wrap>
              <Select
                aria-label="匹配JD"
                placeholder="匹配 JD"
                allowClear
                size="small"
                style={{ width: 160 }}
                value={matchAgainstJdId}
                onChange={(v) => setMatchAgainstJdId(v)}
                options={matchJds.map((j) => ({ value: j.jd_id, label: j.title }))}
              />
              <Tag color="teal" style={{ borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' }}>
                未关联筛选任务
              </Tag>
            <Badge count={stats.total} showZero style={{ backgroundColor: '#8c8c8c' }}>
              <Tag style={{ borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' }}>总计</Tag>
            </Badge>
            <Badge count={stats.parsed} showZero style={{ backgroundColor: '#52c41a' }}>
              <Tag color="success" style={{ borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' }}>成功</Tag>
            </Badge>
            <Badge count={stats.pending} showZero style={{ backgroundColor: '#faad14' }}>
              <Tag color="warning" style={{ borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' }}>待解析</Tag>
            </Badge>
            <Badge count={stats.failed} showZero style={{ backgroundColor: '#ff4d4f' }}>
              <Tag color="error" style={{ borderRadius: 4, padding: '4px 12px', fontSize: '0.85rem' }}>失败</Tag>
            </Badge>
          </Space>
          <Space>
            <Button icon={<ExportOutlined />} onClick={handleExport}>批量导出</Button>
            <Button icon={<ReloadOutlined />} onClick={handleParseAll}>重新解析全部</Button>
            <Upload {...uploadProps}>
              <Button type="primary" icon={<PlusOutlined />} loading={uploading}>上传简历</Button>
            </Upload>
          </Space>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', padding: 16, gap: 16 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Card size="small" style={{ marginBottom: 12 }} styles={{ body: { padding: '12px 16px' } }}>
            <Dragger {...uploadProps} style={{ padding: '8px 0', background: '#fafafa' }}>
              <p className="ant-upload-drag-icon" style={{ marginBottom: 4 }}>
                <UploadOutlined style={{ fontSize: '1.5rem', color: '#0D9488' }} />
              </p>
              <p className="ant-upload-text" style={{ fontSize: '0.85rem', margin: 0 }}>
                拖拽简历文件到此处，或<Text style={{ color: '#0D9488' }}>点击上传</Text>
              </p>
            </Dragger>
          </Card>

          <Card size="small" style={{ flex: 1, display: 'flex', flexDirection: 'column' }} styles={{ body: { padding: 0, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text strong>候选人列表 <Text type="secondary" style={{ fontWeight: 400 }}>(第 {page} 页)</Text></Text>
              <Space>
                <Search
                  placeholder="搜索姓名/手机/邮箱..."
                  allowClear
                  style={{ width: 220 }}
                  onSearch={handleSearch}
                  size="small"
                />
                <Select
                  placeholder="状态筛选"
                  allowClear
                  size="small"
                  style={{ width: 110 }}
                  value={parseStatus}
                  onChange={(v) => { setParseStatus(v); setPage(1); }}
                  options={[
                    { value: 'PARSED', label: '解析成功' },
                    { value: 'PENDING', label: '待解析' },
                    { value: 'PARSING', label: '解析中' },
                    { value: 'FAILED', label: '解析失败' },
                  ]}
                />
                <Select
                  placeholder="候选人状态"
                  allowClear
                  size="small"
                  style={{ width: 130 }}
                  value={candidateStatus}
                  onChange={(v) => { setCandidateStatus(v); setPage(1); }}
                  options={[
                    { value: 'NEW', label: '新简历' },
                    { value: 'SCREENING_PASSED', label: '初筛通过' },
                    { value: 'INTERVIEWING', label: '面试中' },
                    { value: 'OFFERED', label: '已录用' },
                    { value: 'SCREENING_REJECTED', label: '初筛淘汰' },
                    { value: 'ARCHIVED', label: '已归档' },
                  ]}
                />
                <Select
                  placeholder='标签'
                  allowClear
                  size='small'
                  style={{ width: 120 }}
                  value={tagFilter}
                  onChange={(v) => { setTagFilter(v); setPage(1); }}
                  options={tagsMeta.tags.map(t => ({ value: t, label: t }))}
                />
                <Select
                  placeholder='来源'
                  allowClear
                  size='small'
                  style={{ width: 110 }}
                  value={sourceFilter}
                  onChange={(v) => { setSourceFilter(v); setPage(1); }}
                  options={tagsMeta.sources.map(s => ({ value: s, label: s }))}
                />
                <Select
                  placeholder='重复状态'
                  allowClear
                  size='small'
                  style={{ width: 120 }}
                  value={dedupFilter}
                  onChange={(v) => { setDedupFilter(v); setPage(1); }}
                  options={[
                    { value: 'SUSPECTED', label: '疑似重复' },
                    { value: 'CONFIRMED_DUP', label: '已确认重复' },
                    { value: 'IGNORED', label: '已忽略' },
                  ]}
                />
              </Space>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <Table
                columns={columns}
                dataSource={resumes}
                rowKey="resume_id"
                loading={loading}
                pagination={{
                  current: page,
                  pageSize,
                  total,
                  showSizeChanger: true,
                  showTotal: (t) => `共 ${t} 条记录`,
                  onChange: (p, ps) => { setPage(p); setPageSize(ps); },
                  pageSizeOptions: ['10', '20', '50'],
                  size: 'small',
                }}
                size="middle"
                expandable={{
                  expandedRowKeys,
                  expandedRowRender,
                  expandIconColumnIndex: -1,
                  onExpand: (_, record) => toggleExpand(record.resume_id),
                }}
                scroll={{ x: 1000, y: 'calc(100vh - 420px)' }}
              />
            </div>
          </Card>
        </div>

        <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
          <Card size="small" style={{ flex: 1, display: 'flex', flexDirection: 'column' }} styles={{ body: { padding: 0, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' } }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <LinkOutlined style={{ color: '#0D9488' }} />
                <Text strong>关联 JD</Text>
              </Space>
              <Button type="text" size="small" icon={<CloseCircleFilled />} onClick={() => setSelectedResume(null)} />
            </div>

            <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', background: '#f6ffed' }}>
              {selectedResume ? (
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Text type="secondary" style={{ fontSize: '0.75rem' }}>当前候选人</Text>
                  <Text strong>{selectedResume.candidate_name || selectedResume.file_name.replace(/\.(pdf|docx)$/i, '')}</Text>
                  <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewOriginalFile(selectedResume.resume_id)} style={{ padding: 0 }}>
                    查看原始简历
                  </Button>
                </Space>
              ) : (
                <Text type="secondary" style={{ fontSize: '0.85rem' }}>点击操作列按钮查看候选人详情</Text>
              )}
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {selectedResume && selectedResume.parse_status === 'PARSED' ? (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Text strong>候选人 → JD 匹配</Text>
                  {matchAgainstJdId ? (
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      {matchScoreMap[selectedResume.resume_id] !== undefined ? (
                        <ScoreRing score={matchScoreMap[selectedResume.resume_id] as number} />
                      ) : (
                        <Text type="secondary" style={{ fontSize: '0.85rem' }}>
                          暂无匹配分，可在「评分报告」触发批量匹配后查看
                        </Text>
                      )}
                      <Button
                        size="small"
                        type="primary"
                        onClick={async () => {
                          try {
                            const score = await matchApi.matchOne({
                              jd_id: matchAgainstJdId as string,
                              resume_id: selectedResume.resume_id,
                              force: true,
                            });
                            setMatchScoreMap((prev) => ({ ...prev, [selectedResume.resume_id]: score.overall_score }));
                            message.success('匹配完成');
                          } catch {
                            message.error('匹配失败');
                          }
                        }}
                      >
                        重新匹配
                      </Button>
                    </Space>
                  ) : (
                    <Text type="secondary" style={{ fontSize: '0.85rem' }}>请先在上方选择一个匹配 JD</Text>
                  )}
                </Space>
              ) : (
                <div style={{ textAlign: 'center', paddingTop: 60 }}>
                  <LinkOutlined style={{ fontSize: '3rem', color: '#d9d9d9', marginBottom: 16 }} />
                  <div>
                    <Text type="secondary" style={{ fontSize: '0.85rem', display: 'block', marginBottom: 4 }}>
                      {selectedResume ? '请先解析此简历' : '选择一个候选人'}
                    </Text>
                    <Text type="secondary" style={{ fontSize: '0.75rem' }}>
                      匹配功能开发中
                    </Text>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      {editModalVisible && editingResume && (
        <ResumeEditModal
          open={editModalVisible}
          resume={editingResume}
          onCancel={() => { setEditModalVisible(false); setEditingResume(null); }}
          onSaved={handleEditSaved}
        />
      )}
    </div>
  );
};

export default ResumesPage;
