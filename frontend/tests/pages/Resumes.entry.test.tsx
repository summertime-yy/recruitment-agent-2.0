// PR-27 · Resumes 批量多选入口测试(独立文件 · 与既有 Resumes.match.test.tsx 不冲突)。
// 落点:TC-PR27-3。
import { describe, test, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import request from '@/utils/request';
import ResumesPage from '@/pages/Resumes';

const base = request.defaults.baseURL || '';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-probe">{location.pathname}{location.search}</div>;
}

function renderResumes() {
  return render(
    <ConfigProvider>
      <MemoryRouter initialEntries={['/resumes']}>
        <Routes>
          <Route path="/resumes" element={<ResumesPage />} />
          <Route path="/candidate-chat" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

const RESUME_ITEMS = [
  { resume_id: 'r1', candidate_name: 'Alice', desired_position: 'FE', match_status: 'MATCHED', confidence: 0.9, match_score: 90, file_name: 'alice_resume.pdf', file_type: 'pdf', parse_status: 'PARSED', candidate_status: 'NEW' },
  { resume_id: 'r2', candidate_name: 'Bob', desired_position: 'BE', match_status: 'PENDING', confidence: 0.7, match_score: 70, file_name: 'bob_resume.pdf', file_type: 'pdf', parse_status: 'PARSED', candidate_status: 'NEW' },
];

beforeEach(() => {
  server.resetHandlers();
  server.use(
    http.get(`${base}/resumes`, () =>
      HttpResponse.json({ items: RESUME_ITEMS, total: 2, page: 1, page_size: 10 }),
    ),
  );
});

describe('Resumes bulk entry (PR-27)', () => {
  test('TC-PR27-3 勾选 2 行 → 点击「AI 对话 / 画像」→ 跳转 /candidate-chat?candidates=r1,r2', async () => {
    const user = userEvent.setup();
    renderResumes();

    // 表格渲染
    await screen.findByText('Alice');

    // "AI 对话 / 画像" 按钮初始禁用
    const aiBtn = screen.getByRole('button', { name: /AI.*对话.*画像/ });
    expect(aiBtn).toBeDisabled();

    // 勾选两行(第 0 个是表头全选框)
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]);
    await user.click(checkboxes[2]);

    expect(aiBtn).not.toBeDisabled();

    await user.click(aiBtn);

    await waitFor(() => {
      const probe = screen.getByTestId('location-probe');
      expect(probe.textContent).toContain('candidates=r1,r2');
    });
  });
});
