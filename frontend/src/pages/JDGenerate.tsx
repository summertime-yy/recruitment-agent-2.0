import React, { useState, useEffect } from 'react';
import { Form, Input, Select, Button, Card, Alert, Space, Tag, Spin, Result, Descriptions, App, Row, Col, Divider, Typography } from 'antd';
import { ArrowLeftOutlined, ThunderboltOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { jdApi } from '@/services/jd';
import type { JDGenerateResponse, JDGenerateFormData } from '@/types';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const JDPreview: React.FC<{ formData: Partial<JDGenerateFormData>; generatedJD?: JDGenerateResponse['jd'] | null }> = ({ formData, generatedJD }) => {
  const data = generatedJD || formData;

  return (
    <div style={{ background: '#fff', borderRadius: 8, padding: 24, height: '100%', overflow: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        <EyeOutlined style={{ color: 'var(--brand-primary)' }} />
        <span style={{ fontWeight: 600, fontSize: '1rem' }}>JD 实时预览</span>
      </div>

      <div style={{ borderBottom: '1px solid #f0f0f0', paddingBottom: 16, marginBottom: 20 }}>
        <Title level={4} style={{ margin: 0, marginBottom: 12 }}>
          {(data as any).title || '职位名称'}
        </Title>
        <Space wrap size={[8, 8]}>
          {(data as any).department && <Tag color="blue">{(data as any).department}</Tag>}
          {(data as any).recruit_type && <Tag color="purple">{(data as any).recruit_type}</Tag>}
          {(data as any).job_type && <Tag>{(data as any).job_type}</Tag>}
          {(data as any).headcount && <Tag color="cyan">招 {(data as any).headcount} 人</Tag>}
          {(data as any).location && <Tag color="geekblue">{(data as any).location}</Tag>}
          {(data as any).level && <Tag color="magenta">{(data as any).level}</Tag>}
          {(data as any).experience_years && <Tag color="orange">{(data as any).experience_years}</Tag>}
          {(data as any).education_requirement && <Tag color="gold">{(data as any).education_requirement}</Tag>}
          {(data as any).salary_range && <Tag color="red">{(data as any).salary_range}</Tag>}
        </Space>
      </div>

      {(data as any).summary && (
        <div style={{ marginBottom: 20 }}>
          <Title level={5} style={{ color: 'var(--ink-secondary)', marginBottom: 8 }}>职位简介</Title>
          <Paragraph style={{ margin: 0, color: 'var(--ink-secondary)', lineHeight: 1.8 }}>
            {(data as any).summary}
          </Paragraph>
        </div>
      )}

      {((data as any).responsibilities?.length > 0 || (data as any).description) && (
        <div style={{ marginBottom: 20 }}>
          <Title level={5} style={{ color: 'var(--ink-secondary)', marginBottom: 8 }}>岗位职责</Title>
          {(data as any).responsibilities?.length > 0 ? (
            <ul style={{ paddingLeft: 20, margin: 0 }}>
              {(data as any).responsibilities.map((item: string, idx: number) => (
                <li key={idx} style={{ marginBottom: 6, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
              ))}
            </ul>
          ) : (
            <Text type="secondary">填写职位信息后，AI将自动生成岗位职责</Text>
          )}
        </div>
      )}

      {((data as any).requirements?.length > 0 || (data as any).experience_years || (data as any).education_requirement) && (
        <div style={{ marginBottom: 20 }}>
          <Title level={5} style={{ color: 'var(--ink-secondary)', marginBottom: 8 }}>任职要求</Title>
          {(data as any).requirements?.length > 0 ? (
            <ul style={{ paddingLeft: 20, margin: 0 }}>
              {(data as any).requirements.map((item: string, idx: number) => (
                <li key={idx} style={{ marginBottom: 6, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
              ))}
            </ul>
          ) : (
            <Space direction="vertical" size={4}>
              {(data as any).education_requirement && <Tag color="gold">{(data as any).education_requirement}</Tag>}
              {(data as any).experience_years && <Tag color="orange">{(data as any).experience_years}</Tag>}
            </Space>
          )}
        </div>
      )}

      {(((data as any).required_skills?.length > 0) || ((data as any).preferred_skills?.length > 0)) && (
        <div style={{ marginBottom: 8 }}>
          <Title level={5} style={{ color: 'var(--ink-secondary)', marginBottom: 12 }}>技能要求</Title>
          <Row gutter={[16, 12]}>
            {(data as any).required_skills?.length > 0 && (
              <Col span={24}>
                <div style={{ marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: '0.85rem' }}>必备技能</Text>
                </div>
                <Space wrap>
                  {(data as any).required_skills.map((skill: string, idx: number) => (
                    <Tag color="blue" key={idx} style={{ padding: '4px 10px', fontSize: '0.85rem' }}>{skill}</Tag>
                  ))}
                </Space>
              </Col>
            )}
            {(data as any).preferred_skills?.length > 0 && (
              <Col span={24}>
                <div style={{ marginBottom: 4 }}>
                  <Text type="secondary" style={{ fontSize: '0.85rem' }}>加分技能</Text>
                </div>
                <Space wrap>
                  {(data as any).preferred_skills.map((skill: string, idx: number) => (
                    <Tag color="green" key={idx} style={{ padding: '4px 10px', fontSize: '0.85rem' }}>{skill}</Tag>
                  ))}
                </Space>
              </Col>
            )}
          </Row>
        </div>
      )}

      {!generatedJD && !(data as any).summary && !(data as any).responsibilities?.length && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--ink-tertiary)' }}>
          <EyeOutlined style={{ fontSize: 48, opacity: 0.3, marginBottom: 12 }} />
          <div>填写左侧表单即可实时预览JD效果</div>
          <div style={{ fontSize: '0.85rem', marginTop: 4 }}>点击「AI 生成 JD」获取完整职位描述</div>
        </div>
      )}
    </div>
  );
};

const JDGeneratePage: React.FC = () => {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm<JDGenerateFormData>();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<JDGenerateResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Partial<JDGenerateFormData>>({ job_type: '全职', recruit_type: '社招', headcount: 1 });

  useEffect(() => {
    form.setFieldsValue(formValues);
  }, []);

  const onValuesChange = (_: any, allValues: JDGenerateFormData) => {
    setFormValues(allValues);
  };

  const onFinish = async (values: JDGenerateFormData) => {
    setLoading(true);
    setResult(null);
    setErrorMsg(null);
    try {
      const res = await jdApi.generate(values);
      setResult(res);
      message.success('JD生成成功');
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail : 'JD生成失败，请重试';
      setErrorMsg(msg);
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    const jd = result.jd;
    const compliancePassed = !jd.compliance_check || jd.compliance_check.passed;
    return (
      <div>
        <div style={{ marginBottom: 24 }}>
          <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('/jds')} style={{ paddingLeft: 0, marginBottom: 8 }}>
            返回JD列表
          </Button>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>JD 生成结果</h1>
        </div>

        <Result
          status={compliancePassed ? 'success' : 'warning'}
          title="JD 生成成功"
          subTitle={`执行耗时 ${(result.execution_time_ms / 1000).toFixed(1)}s · 验证分数 ${(result.validation_score * 100).toFixed(0)}% · ${compliancePassed ? '合规检查通过' : `发现 ${jd.compliance_check?.issues.length || 0} 个合规问题`}`}
          extra={[
            <Button type="primary" key="view" onClick={() => navigate(`/jds/${jd.jd_id}`)}>
              查看详情
            </Button>,
            <Button key="list" onClick={() => navigate('/jds')}>
              返回列表
            </Button>,
            <Button key="again" onClick={() => { setResult(null); form.resetFields(); setFormValues({ job_type: '全职', recruit_type: '社招', headcount: 1 }); }}>
              再生成一个
            </Button>,
          ]}
          style={{ padding: '24px 0' }}
        />

        <Row gutter={24}>
          <Col span={12}>
            <Card title="JD预览" style={{ marginTop: 24 }}>
              <div style={{ background: '#fafafa', borderRadius: 8, padding: 20 }}>
                <div style={{ borderBottom: '1px solid #f0f0f0', paddingBottom: 16, marginBottom: 16 }}>
                  <Title level={4} style={{ margin: 0, marginBottom: 12 }}>{jd.title}</Title>
                  <Space wrap size={[8, 8]}>
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
                </div>

                {jd.summary && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ color: 'var(--ink-secondary)' }}>职位简介</Text>
                    <Paragraph style={{ margin: '8px 0 0', color: 'var(--ink-secondary)', lineHeight: 1.8 }}>{jd.summary}</Paragraph>
                  </div>
                )}

                {jd.responsibilities && jd.responsibilities.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ color: 'var(--ink-secondary)' }}>岗位职责</Text>
                    <ul style={{ paddingLeft: 20, margin: '8px 0 0' }}>
                      {jd.responsibilities.map((item, idx) => (
                        <li key={idx} style={{ marginBottom: 6, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {jd.requirements && jd.requirements.length > 0 && (
                  <div style={{ marginBottom: 16 }}>
                    <Text strong style={{ color: 'var(--ink-secondary)' }}>任职要求</Text>
                    <ul style={{ paddingLeft: 20, margin: '8px 0 0' }}>
                      {jd.requirements.map((item, idx) => (
                        <li key={idx} style={{ marginBottom: 6, lineHeight: 1.8, color: 'var(--ink-secondary)' }}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <Row gutter={[16, 12]}>
                  {jd.required_skills && jd.required_skills.length > 0 && (
                    <Col span={24}>
                      <Text type="secondary" style={{ fontSize: '0.85rem' }}>必备技能</Text>
                      <div style={{ marginTop: 4 }}>
                        <Space wrap>
                          {jd.required_skills.map((skill, idx) => (
                            <Tag color="blue" key={idx} style={{ padding: '4px 10px' }}>{skill}</Tag>
                          ))}
                        </Space>
                      </div>
                    </Col>
                  )}
                  {jd.preferred_skills && jd.preferred_skills.length > 0 && (
                    <Col span={24}>
                      <Text type="secondary" style={{ fontSize: '0.85rem' }}>加分技能</Text>
                      <div style={{ marginTop: 4 }}>
                        <Space wrap>
                          {jd.preferred_skills.map((skill, idx) => (
                            <Tag color="green" key={idx} style={{ padding: '4px 10px' }}>{skill}</Tag>
                          ))}
                        </Space>
                      </div>
                    </Col>
                  )}
                </Row>
              </div>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="元数据" style={{ marginTop: 24 }}>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="职位ID">{jd.jd_id}</Descriptions.Item>
                <Descriptions.Item label="执行耗时">{result.execution_time_ms}ms</Descriptions.Item>
                <Descriptions.Item label="验证分数">{(result.validation_score * 100).toFixed(0)}%</Descriptions.Item>
              </Descriptions>
              {jd.compliance_check && !jd.compliance_check.passed && jd.compliance_check.issues.length > 0 && (
                <Alert
                  message="合规问题"
                  description={
                    <ul style={{ marginBottom: 0 }}>
                      {jd.compliance_check.issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                  }
                  type="warning"
                  showIcon
                  style={{ marginTop: 16 }}
                />
              )}
            </Card>
          </Col>
        </Row>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate('/jds')} style={{ paddingLeft: 0, marginBottom: 8 }}>
          返回JD列表
        </Button>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>AI 生成 JD</h1>
        <p style={{ color: 'var(--ink-secondary)', fontSize: '0.9rem', margin: 0 }}>填写职位基本信息和需求描述，左侧编辑，右侧实时预览，AI将自动生成完整的职位描述</p>
      </div>

      {errorMsg && !loading && (
        <Alert type="error" message={errorMsg} style={{ marginBottom: 16 }} showIcon closable onClose={() => setErrorMsg(null)} />
      )}

      {loading && (
        <Card>
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#666' }}>AI正在生成JD，请稍候（约30-60秒）...</div>
          </div>
        </Card>
      )}

      {!loading && (
        <Row gutter={24} style={{ minHeight: 'calc(100vh - 200px)' }}>
          <Col span={12}>
            <Card title="职位信息填写" style={{ height: '100%' }}>
              <Form
                form={form}
                layout="vertical"
                onFinish={onFinish}
                onValuesChange={onValuesChange}
                initialValues={{ job_type: '全职', recruit_type: '社招', headcount: 1 }}
              >
                <Form.Item
                  label="职位名称"
                  name="title"
                  rules={[{ required: true, message: '请输入职位名称', min: 2 }]}
                >
                  <Input placeholder="如：AI产品经理" size="large" />
                </Form.Item>

                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item label="所属部门" name="department">
                      <Input placeholder="如：AI产品部" />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item label="职级" name="level">
                      <Select placeholder="请选择职级" allowClear options={[
                        { value: 'P5', label: 'P5' },
                        { value: 'P6', label: 'P6' },
                        { value: 'P7', label: 'P7' },
                        { value: 'P8', label: 'P8' },
                        { value: 'P9', label: 'P9' },
                      ]} />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="招聘类型" name="recruit_type">
                      <Select options={[
                        { value: '社招', label: '社招' },
                        { value: '校招', label: '校招' },
                        { value: '内推', label: '内推' },
                      ]} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="工作类型" name="job_type">
                      <Select options={[
                        { value: '全职', label: '全职' },
                        { value: '实习', label: '实习' },
                        { value: '兼职', label: '兼职' },
                      ]} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="招聘人数" name="headcount">
                      <Input type="number" min={1} max={100} placeholder="1" />
                    </Form.Item>
                  </Col>
                </Row>

                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="工作地点" name="location">
                      <Input placeholder="如：北京" />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="经验年限" name="experience_years">
                      <Select placeholder="请选择" allowClear options={[
                        { value: '不限', label: '不限' },
                        { value: '1-3年', label: '1-3年' },
                        { value: '3-5年', label: '3-5年' },
                        { value: '5-10年', label: '5-10年' },
                        { value: '10年以上', label: '10年以上' },
                        { value: '应届毕业生', label: '应届毕业生' },
                      ]} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="学历要求" name="education_requirement">
                      <Select placeholder="请选择" allowClear options={[
                        { value: '不限', label: '不限' },
                        { value: '大专及以上', label: '大专及以上' },
                        { value: '本科及以上', label: '本科及以上' },
                        { value: '硕士及以上', label: '硕士及以上' },
                        { value: '博士及以上', label: '博士及以上' },
                      ]} />
                    </Form.Item>
                  </Col>
                </Row>

                <Form.Item label="薪资范围" name="salary_range">
                  <Input placeholder="如：25k-40k·15薪" />
                </Form.Item>

                <Form.Item label="必备技能" name="required_skills" extra="输入后按回车添加标签">
                  <Select
                    mode="tags"
                    placeholder="如：Python、React、产品设计"
                    tokenSeparators={[',', '，']}
                    open={false}
                  />
                </Form.Item>

                <Form.Item label="加分技能" name="preferred_skills" extra="输入后按回车添加标签">
                  <Select
                    mode="tags"
                    placeholder="如：大模型应用、SaaS产品经验"
                    tokenSeparators={[',', '，']}
                    open={false}
                  />
                </Form.Item>

                <Form.Item
                  label="职位需求描述"
                  name="description"
                  rules={[{ required: true, message: '请输入职位需求描述（至少10个字）', min: 10 }]}
                  extra="请详细描述对该职位的要求，AI会基于此生成完整JD（包含岗位职责、任职要求等）"
                >
                  <TextArea rows={5} placeholder="如：负责AI产品线规划与设计，3年以上AI产品经验，熟悉大模型应用开发流程，有ToB SaaS产品经验优先，具备良好的跨部门沟通能力" />
                </Form.Item>

                <Divider style={{ margin: '8px 0 16px' }} />

                <Form.Item style={{ marginBottom: 0 }}>
                  <Space>
                    <Button type="primary" htmlType="submit" size="large" icon={<ThunderboltOutlined />}>
                      AI 生成 JD
                    </Button>
                    <Button size="large" onClick={() => { form.resetFields(); setFormValues({ job_type: '全职', recruit_type: '社招', headcount: 1 }); }}>
                      重置
                    </Button>
                  </Space>
                </Form.Item>
              </Form>
            </Card>
          </Col>
          <Col span={12}>
            <Card bodyStyle={{ padding: 0, height: '100%' }} style={{ height: '100%', background: '#fafafa' }}>
              <JDPreview formData={formValues} />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default JDGeneratePage;
