import React, { useEffect, useState } from 'react';
import { Select, Button, Space, Empty, message } from 'antd';
import MatchRankingTable from '@/components/MatchRankingTable';
import MatchDetailDrawer from '@/components/MatchDetailDrawer';
import { jdApi } from '@/services/jd';
import { matchApi } from '@/services/match';
import type { JD, MatchRankingItem, MatchScore } from '@/types';

const ScoringReport: React.FC = () => {
  const [jds, setJds] = useState<JD[]>([]);
  const [jdId, setJdId] = useState<string | undefined>();
  const [items, setItems] = useState<MatchRankingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerData, setDrawerData] = useState<MatchScore | MatchRankingItem | null>(null);

  useEffect(() => {
    jdApi
      .list({ page_size: 200 })
      .then((res) => setJds(res.items))
      .catch(() => setJds([]));
  }, []);

  const loadRanking = async (id: string) => {
    setLoading(true);
    try {
      const res = await matchApi.rankByJd(id, { limit: 200 });
      setItems(res.items);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (id: string) => {
    setJdId(id);
    loadRanking(id);
  };

  const handleBatch = async () => {
    if (!jdId) return;
    const task = await matchApi.batchMatch({ jd_id: jdId, limit: 200 });
    let status = 'RUNNING';
    while (status === 'RUNNING' || status === 'PENDING') {
      const s = await matchApi.getBatchStatus(task.task_id);
      status = s.status;
      if (status === 'COMPLETED' || status === 'FAILED') break;
    }
    await loadRanking(jdId);
    message.success('批量匹配完成');
  };

  const handleViewDetail = (item: MatchRankingItem) => {
    setDrawerData(item);
    setDrawerOpen(true);
  };

  const handleRematch = async (item: MatchRankingItem) => {
    if (!jdId) return;
    const score = await matchApi.matchOne({ jd_id: jdId, resume_id: item.resume_id, force: true });
    setDrawerData(score);
    setDrawerOpen(true);
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="请选择 JD"
          style={{ width: 280 }}
          value={jdId}
          onChange={handleSelect}
          options={jds.map((j) => ({ label: j.title, value: j.jd_id }))}
        />
        <Button type="primary" onClick={handleBatch} disabled={!jdId}>
          触发批量匹配
        </Button>
      </Space>

      {!jdId ? (
        <Empty description="请选择 JD 以查看候选人匹配排名" />
      ) : (
        <MatchRankingTable
          items={items}
          loading={loading}
          onViewDetail={handleViewDetail}
          onRematch={handleRematch}
        />
      )}

      <MatchDetailDrawer open={drawerOpen} data={drawerData} onClose={() => setDrawerOpen(false)} />
    </div>
  );
};

export default ScoringReport;
