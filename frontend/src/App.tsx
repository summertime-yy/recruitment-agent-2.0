import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainLayout from '@/layouts/MainLayout';
import TaskKanbanPage from '@/pages/TaskKanban';
import JDListPage from '@/pages/JDList';
import JDGeneratePage from '@/pages/JDGenerate';
import JDDetailPage from '@/pages/JDDetail';
import ChatCenterPage from '@/pages/ChatCenter';
import ResumesPage from '@/pages/Resumes';
import ResumeDetailPage from '@/pages/ResumeDetail';
import ScoringReportPage from '@/pages/ScoringReport';
import PushFeedbackPage from '@/pages/PushFeedback';
import AnalyticsPage from '@/pages/Analytics';
import SettingsPage from '@/pages/Settings';
import InterviewSchedulePage from '@/pages/InterviewSchedule';
import CandidateChatPage from '@/pages/CandidateChat';
import WorkflowTrackPage from '@/pages/WorkflowTrack';
import CompareAnalysisPage from '@/pages/CompareAnalysis';

const theme = {
  token: {
    colorPrimary: '#0D9488',
    colorSuccess: '#16A34A',
    colorWarning: '#D97706',
    colorError: '#DC2626',
    colorInfo: '#0D9488',
    colorBgBase: '#F8F7F6',
    colorBgContainer: '#FFFFFF',
    colorBorder: '#E7E5E4',
    colorBorderSecondary: '#F5F5F4',
    colorText: '#1C1917',
    colorTextSecondary: '#78716C',
    colorTextTertiary: '#A8A29E',
    borderRadius: 6,
    borderRadiusLG: 10,
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif",
  },
  components: {
    Card: {
      borderRadiusLG: 14,
      boxShadow: '0 1px 2px rgba(28,25,23,0.04)',
    },
    Button: {
      borderRadius: 6,
    },
    Table: {
      headerBg: '#F0EFED',
      headerColor: '#78716C',
    },
    Menu: {
      itemSelectedBg: 'rgba(13,148,136,0.06)',
      itemSelectedColor: '#0F766E',
      itemHoverBg: 'rgba(13,148,136,0.06)',
      itemHoverColor: '#0F766E',
    },
  },
};

const App: React.FC = () => {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntdApp>
        <BrowserRouter>
          <MainLayout>
            <Routes>
              <Route path="/" element={<TaskKanbanPage />} />
              <Route path="/chat" element={<ChatCenterPage />} />
              <Route path="/jds" element={<JDListPage />} />
              <Route path="/jds/generate" element={<JDGeneratePage />} />
              <Route path="/jds/:id" element={<JDDetailPage />} />
              <Route path="/resumes" element={<ResumesPage />} />
              <Route path="/resumes/:id" element={<ResumeDetailPage />} />
              <Route path="/scores" element={<ScoringReportPage />} />
              <Route path="/push" element={<PushFeedbackPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/interview" element={<InterviewSchedulePage />} />
              <Route path="/candidate-chat" element={<CandidateChatPage />} />
              <Route path="/workflow" element={<WorkflowTrackPage />} />
              <Route path="/compare" element={<CompareAnalysisPage />} />
            </Routes>
          </MainLayout>
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  );
};

export default App;
