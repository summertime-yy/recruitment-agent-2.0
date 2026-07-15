import React, { useEffect, useState } from 'react';
import { Card, Space, Input, Button, List, Tag, Rate, Empty, Spin, App, Typography, Popconfirm, Segmented } from 'antd';
import { SolutionOutlined, DeleteOutlined } from '@ant-design/icons';
import { candidateApi } from '@/services/candidate';
import {
  NOTE_TYPE_LABEL,
  NOTE_TYPE_COLOR,
  type CandidateNoteItem,
  type CandidateNoteType,
} from '@/types';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Props {
  resumeId: string;
  refreshKey?: number;
}

const formatTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return iso;
  }
};

const CandidateNotesCard: React.FC<Props> = ({ resumeId, refreshKey = 0 }) => {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<CandidateNoteItem[]>([]);
  const [noteType, setNoteType] = useState<CandidateNoteType>('NOTE');
  const [content, setContent] = useState('');
  const [rating, setRating] = useState<number>(3);
  const [submitting, setSubmitting] = useState(false);

  const fetchNotes = async () => {
    setLoading(true);
    try {
      const res = await candidateApi.listNotes(resumeId);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, refreshKey]);

  const handleSubmit = async () => {
    if (!content.trim()) {
      message.warning('请输入内容');
      return;
    }
    setSubmitting(true);
    try {
      await candidateApi.createNote(resumeId, {
        note_type: noteType,
        content: content.trim(),
        rating: noteType === 'EVALUATION' ? rating : undefined,
        author: 'recruiter',
      });
      message.success('已添加');
      setContent('');
      setRating(3);
      fetchNotes();
    } catch {
      message.error('添加失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (noteId: string) => {
    try {
      await candidateApi.deleteNote(resumeId, noteId);
      message.success('已删除');
      fetchNotes();
    } catch {
      message.error('删除失败');
    }
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <SolutionOutlined style={{ color: '#0D9488' }} />
          <span>备注与评价</span>
          {items.length > 0 && <Tag>{items.length}</Tag>}
        </Space>
      }
    >
      <div style={{ marginBottom: 12 }}>
        <Segmented
          size="small"
          value={noteType}
          onChange={(v) => setNoteType(v as CandidateNoteType)}
          options={[
            { value: 'NOTE', label: '备注' },
            { value: 'EVALUATION', label: '评价' },
          ]}
          style={{ marginBottom: 8 }}
        />
        <TextArea
          rows={2}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={noteType === 'EVALUATION' ? '输入评价内容...' : '输入备注内容...'}
          maxLength={2000}
          showCount
        />
        {noteType === 'EVALUATION' && (
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Text type="secondary" style={{ fontSize: 13 }}>评分：</Text>
            <Rate value={rating} onChange={setRating} />
          </div>
        )}
        <div style={{ marginTop: 8, textAlign: 'right' }}>
          <Button type="primary" size="small" loading={submitting} onClick={handleSubmit}>
            添加{noteType === 'EVALUATION' ? '评价' : '备注'}
          </Button>
        </div>
      </div>

      {loading ? (
        <Spin size="small" />
      ) : items.length === 0 ? (
        <Empty description="暂无备注/评价" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Popconfirm
                  key="del"
                  title="确认删除？"
                  onConfirm={() => handleDelete(item.note_id)}
                >
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                </Popconfirm>,
              ]}
            >
              <div style={{ width: '100%' }}>
                <div style={{ marginBottom: 4 }}>
                  <Tag color={NOTE_TYPE_COLOR[item.note_type]}>
                    {NOTE_TYPE_LABEL[item.note_type]}
                  </Tag>
                  {item.rating && <Rate disabled value={item.rating} style={{ fontSize: 12 }} />}
                  <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                    {formatTime(item.created_at)}
                    {item.author ? ` · ${item.author}` : ''}
                  </Text>
                </div>
                <Paragraph style={{ margin: 0, color: '#57534E', fontSize: '0.9rem' }}>
                  {item.content}
                </Paragraph>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
};

export default CandidateNotesCard;

