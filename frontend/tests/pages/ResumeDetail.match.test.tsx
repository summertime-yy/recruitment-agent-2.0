import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { App } from 'antd';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import ResumeDetailPage from '@/pages/ResumeDetail';

function dim(score = 80) {
  return {
    skill_match: { score, rationale: `skill-${score}` },
    experience_match: { score, rationale: `exp-${score}` },
    education_match: { score, rationale: `edu-${score}` },
    overall_reasoning: 'overall-reasoning-text',
  };
}

function parsedResume() {
  return {
    resume_id: 'r1',
    candidate_name: '张三',
    file_name: 'zhangsan.pdf',
    file_type: 'pdf',
    parse_status: 'PARSED',
    parsed_content: { summary: 's', education: [], work_experience: [], project_experience: [], skills: ['Go'] },
    candidate_status: 'NEW',
    created_at: '2026-07-16T00:00:00',
    updated_at: '2026-07-16T00:00:00',
  };
}

function jdList() {
  return {
    items: [{ jd_id: 'jd1', title: '后端工程师', status: 'PUBLISHED', created_at: '', updated_at: '' }],
    total: 1,
    page: 1,
    page_size: 10,
  };
}

describe('ResumeDetail 匹配面板 (S4-13)', () => {
  test('test_resume_detail_generates_score_and_shows_in_drawer', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('http://localhost/api/v1/resumes/r1', () => HttpResponse.json(parsedResume())),
      http.get('http://localhost/api/v1/jds', () => HttpResponse.json(jdList())),
      http.get('http://localhost/api/v1/resumes/r1/matches', () => HttpResponse.json([])),
      http.post('http://localhost/api/v1/match-scores', () =>
        HttpResponse.json({
          score_id: 'ms1',
          jd_id: 'jd1',
          resume_id: 'r1',
          overall_score: 91,
          dimension_scores: dim(91),
          status: 'COMPLETED',
          is_stale: false,
          created_at: '2026-07-16T00:00:00',
          updated_at: '2026-07-16T00:00:00',
        }),
      ),
    );
    render(
      <App>
        <MemoryRouter initialEntries={['/resumes/r1']}>
          <Routes>
            <Route path="/resumes/:id" element={<ResumeDetailPage />} />
          </Routes>
        </MemoryRouter>
      </App>,
    );
    // 等待简历加载完成
    await screen.findByText('张三');
    // 默认应已选中最近 JD（下拉展示 JD 标题），确保 matchJdId 已就绪
    await screen.findByText('后端工程师');
    // 点击「生成评分」→ 经 MSW 拦截 POST /match-scores → Drawer 展示新分数
    const genBtn = await screen.findByText('生成评分');
    await user.click(genBtn);
    // skill-91 仅来自新匹配响应，唯一 → 验证 Drawer 展示新分数（关键路径）
    expect(await screen.findByText('skill-91')).toBeInTheDocument();
  });
});
