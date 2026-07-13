import React, { useEffect, useState } from 'react';
import { Card, Descriptions, Button, Space, Tag, Spin, App, Form, Input, Select, Alert, Row, Col, Typography } from 'antd';
import { ArrowLeftOutlined, EditOutlined, SaveOutlined, RollbackOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { jdApi } from '@/services/jd';
import type { JD, JDStatus } from '@/types';
import dayjs from 'dayjs';

const statusMap: Record<JDStatus, { color: string; text: string }> = {
  DRAFT: { color: 'default', text: '草稿' },
  PUBLISHED: { color: 'green', text: '已发布' },
  ARCHIVED: { color: 'red', text: '已归档' },
};

const { TextArea } = Input;
const { Paragraph } = Typography;

const JDDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [jd, setJd] = useState<JD | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchJD = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res = await jdApi.getById(id);
      setJd(res);
    } catch (err) {
      console.error('Failed to fetch JD:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJD();
  }, [id]);

  useEffect(() => {
    if (editing && jd) {
      form.setFieldsValue(jd);
    }
  }, [editing, jd]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('edit') === '1') {
      setEditing(true);
    }
  }, []);

  const handleSave = async () => {
    if (!id || !jd) return;
    const values = await form.validateFields();
    const submitData = {
      ...values,
      responsibilities: values.responsibilities
        ? String(values.responsibilities).split('\n').filter((s: string) => s.trim())
        : jd.responsibilities,
      requirements: values.requirements
        ? String(values.requirements).split('\n').filter((s: string) => s.trim())
        : jd.requirements,
    };
    setSaving(true);
    try {
      const res = await jdApi.update(id, submitData);
      setJd(res);
      setEditing(false);
      message.success('保存成功');
    } catch (err) {
      console.error('Failed to update JD:', err);
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: JDStatus) => {
    if (!id) return;
    try {
      const res = await jdApi.update(id, { status: newStatus });
      setJd(res);
      message.success(`状态已更新为${statusMap[newStatus].text}`);
    } catch (err) {
      console.error('Failed to update status:', err);
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

  if (!jd) {
    return (
      <div className="placeholder-page">
        <div className="placeholder-title">JD 不存在</div>
        <div className="placeholder-desc">该JD可能已被删除或ID无效</div>
        <Button type="primary" onClick={() => navigate('/jds')} style={{ marginTop: 24 }}>
          返回列表
        </Button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('/jds')} style={{ paddingLeft: 0, marginBottom: 8 }}>
          返回JD列表
        </Button>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 8 }}>{jd.title}</h1>
            <Space wrap size={[8, 8]}>
              <Tag color={statusMap[jd.status].color}>{statusMap[jd.status].text}</Tag>
              {jd.department && <Tag color="blue">{jd.department}</Tag>}
              {jd.recruit_type && <Tag color="purple">{jd.recruit_type}</Tag>}
              {jd.job_type && <Tag>{jd.job_type}</Tag>}
              {jd.headcount && <Tag color="cyan">招 {jd.headcount} 人</Tag>}
              {jd.location && <Tag color="geekblue">{jd.location}</Tag>}
              {jd.level && <Tag color="magenta">{jd.level}</Tag>}
              {jd.experience_years && <Tag color="orange">{jd.experience_years}</Tag>}
              {jd.education_requirement && <Tag color="gold">{jd.education_requirement}</Tag>}
              {jd.salary_range && <Tag color="red">{jd.salary_range}</Tag>}
            </Space>
            <div style={{ marginTop: 8, color: 'var(--ink-tertiary)', fontSize: '0.85rem' }}>
              创建于 {dayjs(jd.created_at).format('YYYY-MM-DD HH:mm')} · 更新于 {dayjs(jd.updated_at).format('YYYY-MM-DD HH:mm')}
            </div>
          </div>
          <Space>
            {jd.status === 'DRAFT' && (
              <Button type="primary" onClick={() => handleStatusChange('PUBLISHED')}>发布</Button>
            )}
            {jd.status === 'PUBLISHED' && (
              <Button danger onClick={() => handleStatusChange('ARCHIVED')}>归档</Button>
            )}
            {jd.status === 'ARCHIVED' && (
              <Button onClick={() => handleStatusChange('DRAFT')}>恢复草稿</Button>
            )}
            {!editing ? (
              <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑</Button>
            ) : (
              <Space>
                <Button icon={<RollbackOutlined />} onClick={() => setEditing(false)}>取消</Button>
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>
              </Space>
            )}
          </Space>
        </div>
      </div>

      {jd.compliance_check && !jd.compliance_check.passed && (
        <Alert
          message="合规检查未通过"
          description={
            <ul style={{ marginBottom: 0 }}>
              {jd.compliance_check.issues.map((issue, idx) => (
                <li key={idx}>{issue}</li>
              ))}
            </ul>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {editing ? (
        <Card title="编辑 JD">
          <Form
            form={form}
            layout="vertical"
            initialValues={jd}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="职位名称" name="title" rules={[{ required: true, message: '请输入职位名称' }]}>
                  <Input />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="部门" name="department">
                  <Input />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="职级" name="level">
                  <Select allowClear options={[
                    { value: 'P5', label: 'P5' },
                    { value: 'P6', label: 'P6' },
                    { value: 'P7', label: 'P7' },
                    { value: 'P8', label: 'P8' },
                    { value: 'P9', label: 'P9' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="招聘类型" name="recruit_type">
                  <Select allowClear options={[
                    { value: '社招', label: '社招' },
                    { value: '校招', label: '校招' },
                    { value: '内推', label: '内推' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="工作类型" name="job_type">
                  <Select allowClear options={[
                    { value: '全职', label: '全职' },
                    { value: '实习', label: '实习' },
                    { value: '兼职', label: '兼职' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="招聘人数" name="headcount">
                  <Input type="number" min={1} max={100} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="工作地点" name="location">
                  <Input />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item label="薪资范围" name="salary_range">
                  <Input placeholder="如：25k-40k·15薪" />
                </Form.Item>
              </Col>
            </Row>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="经验年限" name="experience_years">
                  <Select allowClear options={[
                    { value: '不限', label: '不限' },
                    { value: '1-3年', label: '1-3年' },
                    { value: '3-5年', label: '3-5年' },
                    { value: '5-10年', label: '5-10年' },
                    { value: '10年以上', label: '10年以上' },
                    { value: '应届毕业生', label: '应届毕业生' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="学历要求" name="education_requirement">
                  <Select allowClear options={[
                    { value: '不限', label: '不限' },
                    { value: '大专及以上', label: '大专及以上' },
                    { value: '本科及以上', label: '本科及以上' },
                    { value: '硕士及以上', label: '硕士及以上' },
                    { value: '博士及以上', label: '博士及以上' },
                  ]} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item label="职位摘要" name="summary">
              <TextArea rows={2} />
            </Form.Item>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label="必备技能" name="required_skills" extra="输入后按回车添加标签">
                  <Select mode="tags" placeholder="如：Python、React" tokenSeparators={[',', '，']} open={false} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item label="加分技能" name="preferred_skills" extra="输入后按回车添加标签">
                  <Select mode="tags" placeholder="如：大模型应用" tokenSeparators={[',', '，']} open={false} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item label="岗位职责（每行一条）" name="responsibilities" getValueFromEvent={(e) => e.target.value} getValueProps={(v) => ({ value: Array.isArray(v) ? v.join('\n') : v || '' })}>
              <TextArea rows={5} placeholder="每行一条岗位职责" />
            </Form.Item>

            <Form.Item label="任职要求（每行一条）" name="requirements" getValueFromEvent={(e) => e.target.value} getValueProps={(v) => ({ value: Array.isArray(v) ? v.join('\n') : v || '' })}>
              <TextArea rows={5} placeholder="每行一条任职要求" />
            </Form.Item>

            <Form.Item label="状态" name="status">
              <Select options={[
                { value: 'DRAFT', label: '草稿' },
                { value: 'PUBLISHED', label: '已发布' },
                { value: 'ARCHIVED', label: '已归档' },
              ]} />
            </Form.Item>
          </Form>
        </Card>
      ) : (
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card title="基本信息">
            <Descriptions column={3} bordered size="small">
              <Descriptions.Item label="JD ID">{jd.jd_id}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusMap[jd.status].color}>{statusMap[jd.status].text}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="招聘类型">{jd.recruit_type || '-'}</Descriptions.Item>
              <Descriptions.Item label="部门">{jd.department || '-'}</Descriptions.Item>
              <Descriptions.Item label="职级">{jd.level || '-'}</Descriptions.Item>
              <Descriptions.Item label="招聘人数">{jd.headcount ? `${jd.headcount} 人` : '-'}</Descriptions.Item>
              <Descriptions.Item label="工作类型">{jd.job_type || '-'}</Descriptions.Item>
              <Descriptions.Item label="工作地点">{jd.location || '-'}</Descriptions.Item>
              <Descriptions.Item label="经验年限">{jd.experience_years || '-'}</Descriptions.Item>
              <Descriptions.Item label="学历要求">{jd.education_requirement || '-'}</Descriptions.Item>
              <Descriptions.Item label="薪资范围">{jd.salary_range || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{dayjs(jd.created_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="更新时间" span={2}>{dayjs(jd.updated_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            </Descriptions>
          </Card>

          {jd.summary && (
            <Card title="职位摘要">
              <Paragraph style={{ margin: 0, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{jd.summary}</Paragraph>
            </Card>
          )}

          {jd.responsibilities && jd.responsibilities.length > 0 && (
            <Card title="岗位职责">
              <ul style={{ paddingLeft: 20, margin: 0 }}>
                {jd.responsibilities.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: 8, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
                ))}
              </ul>
            </Card>
          )}

          {jd.requirements && jd.requirements.length > 0 && (
            <Card title="任职要求">
              <ul style={{ paddingLeft: 20, margin: 0 }}>
                {jd.requirements.map((item, idx) => (
                  <li key={idx} style={{ marginBottom: 8, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
                ))}
              </ul>
            </Card>
          )}

          <Row gutter={16}>
            {jd.required_skills && jd.required_skills.length > 0 && (
              <Col span={12}>
                <Card title="必备技能" style={{ height: '100%' }}>
                  <Space wrap>
                    {jd.required_skills.map((skill, idx) => (
                      <Tag color="blue" key={idx} style={{ padding: '4px 10px', fontSize: '0.85rem' }}>{skill}</Tag>
                    ))}
                  </Space>
                </Card>
              </Col>
            )}
            {jd.preferred_skills && jd.preferred_skills.length > 0 && (
              <Col span={12}>
                <Card title="加分技能" style={{ height: '100%' }}>
                  <Space wrap>
                    {jd.preferred_skills.map((skill, idx) => (
                      <Tag color="green" key={idx} style={{ padding: '4px 10px', fontSize: '0.85rem' }}>{skill}</Tag>
                    ))}
                  </Space>
                </Card>
              </Col>
            )}
          </Row>
        </Space>
      )}
    </div>
  );
};

export default JDDetailPage;
