import React, { useEffect, useState } from 'react';
import { Table, Button, Input, Select, Space, Tag, Popconfirm, App, Card } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { jdApi } from '@/services/jd';
import type { JD, JDStatus, PaginatedResponse } from '@/types';

const statusMap: Record<JDStatus, { color: string; text: string }> = {
  DRAFT: { color: 'default', text: '草稿' },
  PUBLISHED: { color: 'green', text: '已发布' },
  ARCHIVED: { color: 'red', text: '已归档' },
};

const JDListPage: React.FC = () => {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PaginatedResponse<JD>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 10,
  });
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>();

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await jdApi.list({
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        status: (statusFilter as JDStatus) || undefined,
      });
      setData(res);
    } catch (err) {
      console.error('Failed to fetch JD list:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(1);
  }, [statusFilter]);

  const handleDelete = async (id: string) => {
    try {
      await jdApi.delete(id);
      message.success('删除成功');
      fetchData(data.page, data.page_size);
    } catch (err) {
      console.error('Failed to delete JD:', err);
    }
  };

  const handleSearch = () => {
    fetchData(1);
  };

  const columns: ColumnsType<JD> = [
    {
      title: '职位名称',
      dataIndex: 'title',
      key: 'title',
      render: (text, record) => (
        <div>
          <a onClick={() => navigate(`/jds/${record.jd_id}`)} style={{ fontWeight: 600, color: 'var(--ink)' }}>
            {text}
          </a>
          <Space size={4} style={{ marginTop: 4 }}>
            {record.recruit_type && <Tag color="purple" style={{ fontSize: '0.75rem', padding: '0 4px', lineHeight: '18px' }}>{record.recruit_type}</Tag>}
            {record.headcount && <Tag color="cyan" style={{ fontSize: '0.75rem', padding: '0 4px', lineHeight: '18px' }}>{record.headcount}人</Tag>}
            {record.experience_years && <Tag color="orange" style={{ fontSize: '0.75rem', padding: '0 4px', lineHeight: '18px' }}>{record.experience_years}</Tag>}
            {record.education_requirement && <Tag color="gold" style={{ fontSize: '0.75rem', padding: '0 4px', lineHeight: '18px' }}>{record.education_requirement}</Tag>}
          </Space>
        </div>
      ),
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
      width: 100,
      render: (v) => v || '-',
    },
    {
      title: '地点',
      dataIndex: 'location',
      key: 'location',
      width: 80,
      render: (v) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: JDStatus) => <Tag color={statusMap[status].color}>{statusMap[status].text}</Tag>,
    },
    {
      title: '薪资',
      dataIndex: 'salary_range',
      key: 'salary_range',
      width: 110,
      render: (v) => v ? <Tag color="red">{v}</Tag> : '-',
    },
    {
      title: '技能标签',
      dataIndex: 'required_skills',
      key: 'required_skills',
      width: 200,
      render: (skills: string[]) =>
        skills?.slice(0, 2).map((s, i) => (
          <Tag key={i} color="blue" style={{ marginBottom: 2 }}>
            {s}
          </Tag>
        )) || '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (d) => dayjs(d).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => navigate(`/jds/${record.jd_id}`)}>
            查看
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => navigate(`/jds/${record.jd_id}?edit=1`)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此JD？" onConfirm={() => handleDelete(record.jd_id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>JD 管理</h1>
          <p style={{ color: 'var(--ink-secondary)', fontSize: '0.9rem', margin: 0 }}>管理所有职位描述，支持AI生成、编辑、发布和归档</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} size="large" onClick={() => navigate('/jds/generate')} style={{ borderRadius: 'var(--radius-md)' }}>
          生成 JD
        </Button>
      </div>

      <Card style={{ marginBottom: 16 }} bodyStyle={{ padding: '16px 20px' }}>
        <Space wrap>
          <Input
            placeholder="搜索职位名称..."
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 240 }}
            prefix={<SearchOutlined style={{ color: 'var(--ink-tertiary)' }} />}
            allowClear
          />
          <Select
            placeholder="状态筛选"
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 140 }}
            allowClear
            options={[
              { value: 'DRAFT', label: '草稿' },
              { value: 'PUBLISHED', label: '已发布' },
              { value: 'ARCHIVED', label: '已归档' },
            ]}
          />
          <Button onClick={handleSearch}>搜索</Button>
        </Space>
      </Card>

      <Card>
        <Table
          columns={columns}
          dataSource={data.items}
          rowKey="jd_id"
          loading={loading}
          pagination={{
            current: data.page,
            pageSize: data.page_size,
            total: data.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => fetchData(page, pageSize),
          }}
        />
      </Card>
    </div>
  );
};

export default JDListPage;
