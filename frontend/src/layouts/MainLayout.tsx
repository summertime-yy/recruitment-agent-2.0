import React, { useState } from 'react';
import { Layout, Menu, Avatar, Tooltip } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  BarChartOutlined,
  SendOutlined,
  LineChartOutlined,
  SettingOutlined,
  CalendarOutlined,
  TeamOutlined,
  BranchesOutlined,
  SwapOutlined,
  PlusOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

interface NavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  phase2?: boolean;
}

const coreNavItems: NavItem[] = [
  { key: 'kanban', label: '任务看板', icon: <DashboardOutlined />, path: '/' },
  { key: 'chat', label: '任务中心', icon: <MessageOutlined />, path: '/chat' },
  { key: 'jds', label: 'JD 管理', icon: <FileTextOutlined />, path: '/jds' },
  { key: 'resumes', label: '简历工作台', icon: <FileSearchOutlined />, path: '/resumes' },
  { key: 'scores', label: '评分报告', icon: <BarChartOutlined />, path: '/scores' },
  { key: 'push', label: '推送反馈', icon: <SendOutlined />, path: '/push' },
];

const analyticsNavItems: NavItem[] = [
  { key: 'analytics', label: '数据看板', icon: <LineChartOutlined />, path: '/analytics' },
  { key: 'settings', label: '系统设置', icon: <SettingOutlined />, path: '/settings' },
];

const phase2NavItems: NavItem[] = [
  { key: 'interview', label: '面试安排', icon: <CalendarOutlined />, path: '/interview', phase2: true },
  { key: 'candidate-chat', label: '候选人沟通', icon: <TeamOutlined />, path: '/candidate-chat', phase2: true },
  { key: 'workflow', label: '流程跟踪', icon: <BranchesOutlined />, path: '/workflow', phase2: true },
  { key: 'compare', label: '对比分析', icon: <SwapOutlined />, path: '/compare', phase2: true },
];

const pageTitles: Record<string, string> = {
  '/': '任务看板',
  '/chat': '任务中心',
  '/jds': 'JD 管理',
  '/jds/generate': '生成 JD',
  '/resumes': '简历工作台',
  '/scores': '评分报告',
  '/push': '推送反馈',
  '/analytics': '数据看板',
  '/settings': '系统设置',
  '/interview': '面试安排',
  '/candidate-chat': '候选人沟通',
  '/workflow': '流程跟踪',
  '/compare': '对比分析',
};

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const getSelectedKey = () => {
    const path = location.pathname;
    if (path.startsWith('/jds')) return 'jds';
    if (path.startsWith('/chat')) return 'chat';
    if (path.startsWith('/resumes')) return 'resumes';
    if (path.startsWith('/scores')) return 'scores';
    if (path.startsWith('/push')) return 'push';
    if (path.startsWith('/analytics')) return 'analytics';
    if (path.startsWith('/settings')) return 'settings';
    if (path.startsWith('/interview')) return 'interview';
    if (path.startsWith('/candidate-chat')) return 'candidate-chat';
    if (path.startsWith('/workflow')) return 'workflow';
    if (path.startsWith('/compare')) return 'compare';
    return 'kanban';
  };

  const renderNavItems = (items: NavItem[]) =>
    items.map((item) => ({
      key: item.key,
      icon: item.icon,
      label: (
        <span style={{ display: 'flex', alignItems: 'center' }}>
          {item.label}
          {item.phase2 && <span className="phase2-badge">Phase 2</span>}
        </span>
      ),
      onClick: () => navigate(item.path),
      className: item.phase2 ? 'phase2-nav-item' : '',
      style: item.phase2 ? { opacity: 0.65 } : undefined,
    }));

  const menuItems = [
    {
      key: 'core-group',
      type: 'group' as const,
      label: !collapsed && <div className="nav-group-label">核心流程</div>,
      children: renderNavItems(coreNavItems),
    },
    {
      key: 'analytics-group',
      type: 'group' as const,
      label: !collapsed && <div className="nav-group-label">分析与设置</div>,
      children: renderNavItems(analyticsNavItems),
    },
    {
      key: 'phase2-group',
      type: 'group' as const,
      label: !collapsed && <div className="nav-group-label">更多功能</div>,
      children: renderNavItems(phase2NavItems),
    },
  ];

  const currentTitle = pageTitles[location.pathname]
    || (location.pathname.startsWith('/jds/') ? 'JD 详情' : '')
    || (location.pathname.startsWith('/resumes/') ? '简历详情' : '页面');

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        width={260}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          background: '#fff',
          borderRight: '1px solid var(--border)',
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
        }}
        trigger={null}
      >
        <div
          style={{
            padding: collapsed ? '16px 8px' : '20px',
            borderBottom: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            minHeight: 64,
          }}
        >
          <div className="brand-icon">RA</div>
          {!collapsed && (
            <div>
              <div style={{ fontFamily: 'system-ui', fontSize: '0.95rem', fontWeight: 700, color: 'var(--ink)', lineHeight: 1.2 }}>
                智能招聘 Agent
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--ink-tertiary)', marginTop: 1 }}>Smart Recruitment</div>
            </div>
          )}
        </div>

        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          style={{ border: 'none', padding: '8px 6px', flex: 1 }}
          onClick={({ key }) => {
            const allItems = [...coreNavItems, ...analyticsNavItems, ...phase2NavItems];
            const item = allItems.find((i) => i.key === key);
            if (item) navigate(item.path);
          }}
        />

        <div
          style={{
            padding: '14px 16px',
            borderTop: '1px solid var(--border-light)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginTop: 'auto',
          }}
        >
          <Avatar size={32} style={{ background: 'var(--primary-light)', color: 'var(--primary-dark)', fontWeight: 700, fontSize: '0.75rem' }}>
            AD
          </Avatar>
          {!collapsed && (
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--ink)' }}>管理员</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--ink-tertiary)' }}>超级管理员</div>
            </div>
          )}
        </div>
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 260, transition: 'margin-left 0.2s' }}>
        <Header
          style={{
            background: '#fff',
            borderBottom: '1px solid var(--border)',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            minHeight: 54,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem', color: 'var(--ink-tertiary)' }}>
            <span>智能招聘 Agent</span>
            <span style={{ opacity: 0.4 }}>/</span>
            <span style={{ color: 'var(--ink-secondary)', fontWeight: 500 }}>{currentTitle}</span>
          </div>

          <div style={{ flex: 1 }} />

          {location.pathname === '/jds' && (
            <Tooltip title="生成新 JD">
              <button
                onClick={() => navigate('/jds/generate')}
                style={{
                  background: 'var(--primary)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 'var(--radius-sm)',
                  padding: '6px 14px',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <PlusOutlined /> 生成 JD
              </button>
            </Tooltip>
          )}

          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--ink-tertiary)',
              fontSize: '1.1rem',
              padding: 4,
            }}
          >
            <UserOutlined />
          </button>
        </Header>

        <Content
          style={{
            overflow: 'auto',
            background: 'var(--bg)',
            height: 'calc(100vh - 54px)',
          }}
        >
          <div className="page-content">{children}</div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
