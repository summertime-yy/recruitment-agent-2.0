import React, { useEffect, useState } from 'react';
import { Timeline, Empty, Spin, Tag, Typography, Space } from 'antd';
import { DownOutlined, UpOutlined } from '@ant-design/icons';
import { candidateApi } from '@/services/candidate';
import {
  CANDIDATE_STATUS_LABEL,
  CANDIDATE_STATUS_COLOR,
  type CandidateStatus,
  type CandidateStatusHistoryItem,
} from '@/types';

const { Text } = Typography;

/** 默认展开显示的记录数 */
const DEFAULT_VISIBLE_COUNT = 3;

interface Props {
  resumeId: string;
  /** 触发刷新的 key（例如状态变更后自增） */
  refreshKey?: number;
}

const formatTime = (iso: string) => {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
};

const renderTimelineItem = (it: CandidateStatusHistoryItem) => ({
  color: CANDIDATE_STATUS_COLOR[it.to_status as CandidateStatus],
  children: (
    <div>
      <div style={{ marginBottom: 2 }}>
        {it.from_status ? (
          <Tag color={CANDIDATE_STATUS_COLOR[it.from_status as CandidateStatus]}>
            {CANDIDATE_STATUS_LABEL[it.from_status as CandidateStatus]}
          </Tag>
        ) : (
          <Text type="secondary">初始</Text>
        )}
        <span style={{ margin: '0 6px' }}>→</span>
        <Tag color={CANDIDATE_STATUS_COLOR[it.to_status as CandidateStatus]}>
          {CANDIDATE_STATUS_LABEL[it.to_status as CandidateStatus]}
        </Tag>
      </div>
      {it.reason && <div style={{ color: '#555' }}>{it.reason}</div>}
      <Text type="secondary" style={{ fontSize: 12 }}>
        {formatTime(it.occurred_at)}
        {it.operator ? ` · 操作人：${it.operator}` : ''}
      </Text>
    </div>
  ),
});

const CandidateStatusTimeline: React.FC<Props> = ({ resumeId, refreshKey = 0 }) => {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<CandidateStatusHistoryItem[]>([]);
  const [expanded, setExpanded] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await candidateApi.getStatusHistory(resumeId);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, refreshKey]);

  if (loading) return <Spin size="small" />;
  if (!items.length) {
    return <Empty description="暂无状态流转记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  /** 记录数不超过阈值，直接全部展示 */
  if (items.length <= DEFAULT_VISIBLE_COUNT) {
    return <Timeline items={items.map(renderTimelineItem)} />;
  }

  /** 超过阈值时：默认显示最近 N 条，可展开查看全部 */
  const visibleItems = expanded ? items : items.slice(0, DEFAULT_VISIBLE_COUNT);

  return (
    <div>
      <Timeline items={visibleItems.map(renderTimelineItem)} />
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          textAlign: 'center',
          cursor: 'pointer',
          padding: '6px 0',
          color: '#1677ff',
          fontSize: 13,
        }}
      >
        <Space size={4}>
          {expanded ? (
            <>
              <UpOutlined />
              收起
            </>
          ) : (
            <>
              <DownOutlined />
              展开全部 ({items.length} 条)
            </>
          )}
        </Space>
      </div>
    </div>
  );
};

export default CandidateStatusTimeline;
