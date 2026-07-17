import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App } from 'antd';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import ResumesPage from '@/pages/Resumes';

function dim(score = 80) {
  return {
    skill_match: { score, rationale: `skill-${score}` },
    experience_match: { score, rationale: `exp-${score}` },
    education_match: { score, rationale: `edu-${score}` },
    overall_reasoning: 'overall-reasoning-text',
  };
}

function resumeList() {
  const base = {
    file_type: 'pdf',
    parse_status: 'PARSED' as const,
    parsed_content: { summary: 's', education: [], work_experience: [], project_experience: [], skills: ['Go'] },
    candidate_status: 'NEW' as const,
    created_at: '2026-07-16T00:00:00',
    updated_at: '2026-07-16T00:00:00',
  };
  return {
    items: [
      { resume_id: 'r1', candidate_name: '张三', file_name: 'zhangsan.pdf', ...base },
      { resume_id: 'r2', candidate_name: '李四', file_name: 'lisi.pdf', ...base },
    ],
    total: 2,
    page: 1,
    page_size: 10,
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

function ranking(jdId: string, items: unknown[]) {
  return { jd_id: jdId, total: items.length, items };
}

describe('Resumes 页面匹配分接入 (S4-12)', () => {
  test('test_resumes_confidence_shows_dash_when_no_jd', async () => {
    server.use(
      http.get('http://localhost/api/v1/resumes', () => HttpResponse.json(resumeList())),
      http.get('http://localhost/api/v1/resumes/tags-meta', () => HttpResponse.json({ tags: [], sources: [] })),
      http.get('http://localhost/api/v1/jds', () => HttpResponse.json(jdList())),
    );
    render(
      <App>
        <MemoryRouter>
          <ResumesPage />
        </MemoryRouter>
      </App>,
    );
    // 默认未选 JD：匹配分列应显示 '-'（未选 JD 显示 - 关键路径）
    const cell = await screen.findByTestId('confidence-r1');
    expect(within(cell).getByText('-')).toBeInTheDocument();
  });

  test('test_resumes_confidence_shows_real_score_after_jd_select', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('http://localhost/api/v1/resumes', () => HttpResponse.json(resumeList())),
      http.get('http://localhost/api/v1/resumes/tags-meta', () => HttpResponse.json({ tags: [], sources: [] })),
      http.get('http://localhost/api/v1/jds', () => HttpResponse.json(jdList())),
      http.get('http://localhost/api/v1/jds/jd1/ranking', () =>
        HttpResponse.json(
          ranking('jd1', [
            { score_id: 's1', resume_id: 'r1', candidate_name: '张三', overall_score: 73, dimension_scores: dim(73), is_stale: false, created_at: '2026-07-16T00:00:00' },
          ]),
        ),
      ),
    );
    render(
      <App>
        <MemoryRouter>
          <ResumesPage />
        </MemoryRouter>
      </App>,
    );
    const beforeCell = await screen.findByTestId('confidence-r1');
    expect(within(beforeCell).getByText('-')).toBeInTheDocument();
    // 选择 JD（通过 role=combobox + 可访问名 定位，避免多 Select 与占位符 pointer-events 歧义）
    await user.click(await screen.findByRole('combobox', { name: '匹配JD' }));
    await user.click(await screen.findByText('后端工程师'));
    // 选 JD 后 r1 展示真实分 73（来自 rankByJd，非随机）
    await waitFor(() =>
      expect(within(screen.getByTestId('confidence-r1')).getByText('73')).toBeInTheDocument(),
    );
  });

  test('test_resumes_has_no_math_random', () => {
    const src = readFileSync(resolve(__dirname, '../../src/pages/Resumes.tsx'), 'utf-8');
    expect(src).not.toContain('Math.random(');
  });
});
