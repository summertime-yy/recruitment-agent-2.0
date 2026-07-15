import React, { useState, useEffect } from 'react';
import { Tag, Dropdown, Modal, Input, Form, App, Spin } from 'antd';
import { DownOutlined } from '@ant-design/icons';
import { candidateApi } from '@/services/candidate';
import {
  CANDIDATE_STATUS_LABEL,
  CANDIDATE_STATUS_COLOR,
  type CandidateStatus,
  type CandidateStatusInfo,
  type CandidateStatusMeta,
} from '@/types';

interface Props {
  resumeId: string;
  status: CandidateStatus;
  operator?: string;
  onChange?: (newStatus: CandidateStatus) => void;
  /** 是否允许交互切换，默认 true */
  editable?: boolean;
}

const CandidateStatusSwitch: React.FC<Props> = ({
  resumeId,
  status,
  operator = 'recruiter',
  onChange,
  editable = true,
}) => {
  const { message } = App.useApp();
  const [meta, setMeta] = useState<CandidateStatusMeta | null>(null);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [targetStatus, setTargetStatus] = useState<CandidateStatus | null>(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchMeta = async () => {
    if (!editable) return;
    setLoading(true);
    try {
      const m = await candidateApi.getStatusMeta(resumeId);
      setMeta(m);
    } catch {
      // 静默失败，不影响列表展示
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMeta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, status, editable]);

  const openModal = (to: CandidateStatus) => {
    setTargetStatus(to);
    setReason('');
    setModalOpen(true);
    form.resetFields();
  };

  const handleSubmit = async () => {
    if (!targetStatus) return;
    setSubmitting(true);
    try {
      await candidateApi.updateStatus(resumeId, {
        to_status: targetStatus,
        reason: reason || undefined,
        operator,
      });
      message.success(`状态已更新为：${CANDIDATE_STATUS_LABEL[targetStatus]}`);
      setModalOpen(false);
      onChange?.(targetStatus);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '状态更新失败';
      message.error(typeof detail === 'string' ? detail : '状态更新失败');
    } finally {
      setSubmitting(false);
    }
  };

  const renderMenuItems = () => {
    if (!meta) return [];
    const available = new Set(meta.available_transitions);
    return meta.all_statuses
      .filter((s: CandidateStatusInfo) => available.has(s.value))
      .map((s: CandidateStatusInfo) => ({
        key: s.value,
        label: (
          <span>
            <Tag color={s.color} style={{ marginRight: 6 }}>
              {CANDIDATE_STATUS_LABEL[s.value as CandidateStatus]}
            </Tag>
            {s.value === status && <span style={{ color: '#999' }}>当前</span>}
          </span>
        ),
        onClick: () => {
          if (s.value !== status) openModal(s.value as CandidateStatus);
        },
        disabled: s.value === status,
      }));
  };

  const tag = (
    <Tag color={CANDIDATE_STATUS_COLOR[status]} style={{ margin: 0 }}>
      {CANDIDATE_STATUS_LABEL[status] ?? status}
    </Tag>
  );

  if (!editable) return tag;

  return (
    <Spin spinning={loading} size="small">
      <Dropdown
        menu={{ items: renderMenuItems() }}
        trigger={['click']}
        disabled={!meta}
      >
        <span style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          {tag}
          <DownOutlined style={{ fontSize: 10, color: '#999' }} />
        </span>
      </Dropdown>

      <Modal
        title="更新候选人状态"
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        okText="确认变更"
        cancelText="取消"
        destroyOnHidden
      >
        <div style={{ marginBottom: 12 }}>
          当前状态：
          <Tag color={CANDIDATE_STATUS_COLOR[status]}>{CANDIDATE_STATUS_LABEL[status]}</Tag>
          {targetStatus && (
            <>
              {' → '}
              <Tag color={CANDIDATE_STATUS_COLOR[targetStatus]}>
                {CANDIDATE_STATUS_LABEL[targetStatus]}
              </Tag>
            </>
          )}
        </div>
        <Form form={form} layout="vertical">
          <Form.Item label="变更原因 / 备注（可选）">
            <Input.TextArea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="例如：简历匹配度高，初筛通过"
              maxLength={500}
              showCount
            />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

export default CandidateStatusSwitch;