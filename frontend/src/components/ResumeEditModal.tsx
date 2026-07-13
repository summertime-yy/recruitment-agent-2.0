import React, { useEffect } from 'react';
import { Modal, Form, Input, Divider, Button, Space } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { resumeApi } from '@/services/resume';
import type { Resume, ParsedContent, EducationItem, WorkExperienceItem, ProjectExperienceItem } from '@/types';

const { TextArea } = Input;

interface EditFormData {
  candidate_name: string;
  phone: string;
  email: string;
  summary: string;
  education: EducationItem[];
  work_experience: WorkExperienceItem[];
  project_experience: ProjectExperienceItem[];
  skills: string;
}

interface ResumeEditModalProps {
  open: boolean;
  resume: Resume | null;
  onCancel: () => void;
  onSaved: (updated: Resume) => void;
}

const ResumeEditModal: React.FC<ResumeEditModalProps> = ({ open, resume, onCancel, onSaved }) => {
  const [form] = Form.useForm<EditFormData>();
  const [saving, setSaving] = React.useState(false);

  useEffect(() => {
    if (open && resume) {
      const pc = resume.parsed_content || {
        summary: '',
        education: [],
        work_experience: [],
        project_experience: [],
        skills: [],
      };
      form.setFieldsValue({
        candidate_name: resume.candidate_name || '',
        phone: resume.phone || '',
        email: resume.email || '',
        summary: pc.summary || '',
        education: pc.education.length > 0 ? pc.education : [{ school: '', degree: '', major: '', start_date: '', end_date: '' }],
        work_experience: pc.work_experience.length > 0 ? pc.work_experience : [{ company: '', position: '', start_date: '', end_date: '', description: '' }],
        project_experience: pc.project_experience.length > 0 ? pc.project_experience : [{ name: '', role: '', start_date: '', end_date: '', description: '' }],
        skills: (pc.skills || []).join(', '),
      });
    }
  }, [open, resume, form]);

  const handleSave = async () => {
    if (!resume) return;
    try {
      const values = await form.validateFields();
      setSaving(true);

      const parsedContent: ParsedContent = {
        summary: values.summary || undefined,
        education: (values.education || []).filter((e: EducationItem) => e.school && e.school.trim()),
        work_experience: (values.work_experience || []).filter((w: WorkExperienceItem) => w.company && w.company.trim()),
        project_experience: (values.project_experience || []).filter((p: ProjectExperienceItem) => p.name && p.name.trim()),
        skills: values.skills ? values.skills.split(/[,，、\s]+/).filter(Boolean) : [],
      };

      const updated = await resumeApi.update(resume.resume_id, {
        candidate_name: values.candidate_name || undefined,
        phone: values.phone || undefined,
        email: values.email || undefined,
        parsed_content: parsedContent,
      });

      onSaved(updated);
    } catch (err: any) {
      if (err?.errorFields) {
        // form validation error, antd will show it
      } else {
        console.error('Save failed:', err);
      }
    } finally {
      setSaving(false);
    }
  };

  if (!open || !resume) return null;

  return (
    <Modal
      title={`编辑简历信息 - ${resume.candidate_name || resume.file_name}`}
      open={open}
      width={720}
      onCancel={onCancel}
      onOk={handleSave}
      confirmLoading={saving}
      okText="保存"
      cancelText="取消"
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: 8 }}
      >
        <Space size={16} style={{ width: '100%' }}>
          <Form.Item label="姓名" name="candidate_name" style={{ flex: 1, marginBottom: 12 }}>
            <Input placeholder="候选人姓名" />
          </Form.Item>
          <Form.Item label="手机号" name="phone" style={{ flex: 1, marginBottom: 12 }}>
            <Input placeholder="手机号" />
          </Form.Item>
          <Form.Item label="邮箱" name="email" style={{ flex: 1, marginBottom: 12 }}>
            <Input placeholder="邮箱地址" />
          </Form.Item>
        </Space>

        <Form.Item label="个人简介" name="summary" style={{ marginBottom: 12 }}>
          <TextArea rows={2} placeholder="个人简介/自我评价" />
        </Form.Item>

        <Divider orientation="left" style={{ fontSize: '0.85rem', margin: '8px 0' }}>教育经历</Divider>
        <Form.List name="education">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item {...restField} name={[name, 'school']} style={{ marginBottom: 0, width: 140 }}>
                    <Input placeholder="学校" size="small" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'degree']} style={{ marginBottom: 0, width: 80 }}>
                    <Input placeholder="学历" size="small" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'major']} style={{ marginBottom: 0, width: 120 }}>
                    <Input placeholder="专业" size="small" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'start_date']} style={{ marginBottom: 0, width: 90 }}>
                    <Input placeholder="开始时间" size="small" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'end_date']} style={{ marginBottom: 0, width: 90 }}>
                    <Input placeholder="结束时间" size="small" />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(name)} />
                </Space>
              ))}
              <Button type="dashed" size="small" onClick={() => add()} block icon={<PlusOutlined />}>
                添加教育经历
              </Button>
            </>
          )}
        </Form.List>

        <Divider orientation="left" style={{ fontSize: '0.85rem', margin: '16px 0 8px' }}>工作经历</Divider>
        <Form.List name="work_experience">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <div key={key} style={{ marginBottom: 8, padding: 8, background: '#fafafa', borderRadius: 4 }}>
                  <Space style={{ display: 'flex', marginBottom: 4 }} align="baseline">
                    <Form.Item {...restField} name={[name, 'company']} style={{ marginBottom: 0, flex: 1 }}>
                      <Input placeholder="公司名称" size="small" />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'position']} style={{ marginBottom: 0, flex: 1 }}>
                      <Input placeholder="职位" size="small" />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} />
                  </Space>
                  <Space style={{ display: 'flex' }} align="baseline">
                    <Form.Item {...restField} name={[name, 'start_date']} style={{ marginBottom: 0, width: 120 }}>
                      <Input placeholder="开始时间" size="small" />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'end_date']} style={{ marginBottom: 0, width: 120 }}>
                      <Input placeholder="结束时间" size="small" />
                    </Form.Item>
                  </Space>
                  <Form.Item {...restField} name={[name, 'description']} style={{ marginBottom: 0, marginTop: 4 }}>
                    <TextArea rows={2} placeholder="工作内容描述" size="small" />
                  </Form.Item>
                </div>
              ))}
              <Button type="dashed" size="small" onClick={() => add()} block icon={<PlusOutlined />}>
                添加工作经历
              </Button>
            </>
          )}
        </Form.List>

        <Divider orientation="left" style={{ fontSize: '0.85rem', margin: '16px 0 8px' }}>项目经历</Divider>
        <Form.List name="project_experience">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <div key={key} style={{ marginBottom: 8, padding: 8, background: '#fafafa', borderRadius: 4 }}>
                  <Space style={{ display: 'flex', marginBottom: 4 }} align="baseline">
                    <Form.Item {...restField} name={[name, 'name']} style={{ marginBottom: 0, flex: 1 }}>
                      <Input placeholder="项目名称" size="small" />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'role']} style={{ marginBottom: 0, width: 120 }}>
                      <Input placeholder="角色" size="small" />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} />
                  </Space>
                  <Space style={{ display: 'flex' }} align="baseline">
                    <Form.Item {...restField} name={[name, 'start_date']} style={{ marginBottom: 0, width: 120 }}>
                      <Input placeholder="开始时间" size="small" />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'end_date']} style={{ marginBottom: 0, width: 120 }}>
                      <Input placeholder="结束时间" size="small" />
                    </Form.Item>
                  </Space>
                  <Form.Item {...restField} name={[name, 'description']} style={{ marginBottom: 0, marginTop: 4 }}>
                    <TextArea rows={2} placeholder="项目描述" size="small" />
                  </Form.Item>
                </div>
              ))}
              <Button type="dashed" size="small" onClick={() => add()} block icon={<PlusOutlined />}>
                添加项目经历
              </Button>
            </>
          )}
        </Form.List>

        <Divider orientation="left" style={{ fontSize: '0.85rem', margin: '16px 0 8px' }}>技能标签</Divider>
        <Form.Item name="skills" style={{ marginBottom: 0 }}>
          <Input placeholder="多个技能用逗号分隔，如：Python, React, SQL" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ResumeEditModal;
