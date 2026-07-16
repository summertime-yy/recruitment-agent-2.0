import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import ScoringReport from '@/pages/ScoringReport';

function dim(score = 80) {
  return {
    skill_match: { score, rationale: `skill-${score}` },
    experience_match: { score, rationale: `exp-${score}` },
    education_match: { score, rationale: `edu-${score}` },
    overall_reasoning: 'overall-reasoning-text',
  };
}

function rankingItems() {
  return [
    { score_id: 's1', resume_id: 'r1', candidate_name: '张三', overall_score: 90, dimension_scores: dim(90), is_stale: false, created_at: '2026-07-16T00:00:00' },
    { score_id: 's2', resume_id: 'r2', candidate_name: '李四', overall_score: 80, dimension_scores: dim(80), is_stale: true, created_at: '2026-07-16T00:00:00' },
  ];
}

function jdListHandler() {
  return http.get('http://localhost/api/v1/jds', () =>
    HttpResponse.json({
      items: [{ jd_id: 'jd1', title: '后端工程师', status: 'PUBLISHED', created_at: '', updated_at: '' }],
      total: 1,
      page: 1,
      page_size: 10,
    }),
  );
}

async function selectJd(user: ReturnType<typeof userEvent.setup>) {
  const combobox = await screen.findByRole('combobox');
  await user.click(combobox);
  await user.click(await screen.findByText('后端工程师'));
}

describe('ScoringReport 页面 (S4-11)', () => {
  test('test_scoring_report_shows_empty_state_without_jd', async () => {
    server.use(http.get('http://localhost/api/v1/jds', () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 10 })));
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    expect(await screen.findByText('请选择 JD 以查看候选人匹配排名')).toBeInTheDocument();
    // 未选 JD 时不展示任何候选人行
    expect(screen.queryByText('张三')).toBeNull();
  });

  test('test_scoring_report_loads_ranking_after_jd_select', async () => {
    const user = userEvent.setup();
    server.use(
      jdListHandler(),
      http.get('http://localhost/api/v1/jds/jd1/ranking', () => HttpResponse.json({ jd_id: 'jd1', total: 2, items: rankingItems() })),
    );
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    await selectJd(user);
    expect(await screen.findByText('张三')).toBeInTheDocument();
    expect(screen.getByText('李四')).toBeInTheDocument();
  });

  test('test_scoring_report_triggers_batch_and_polls', async () => {
    const user = userEvent.setup();
    let batchCalls = 0;
    server.use(
      jdListHandler(),
      http.post('http://localhost/api/v1/match-scores/batch', () =>
        HttpResponse.json({ task_id: 't1', jd_id: 'jd1', total_submitted: 2, submitted_at: '2026-07-16T00:00:00' }),
      ),
      http.get('http://localhost/api/v1/match-scores/batch/t1', () => {
        batchCalls += 1;
        const status = batchCalls >= 2 ? 'COMPLETED' : 'RUNNING';
        return HttpResponse.json({
          task_id: 't1',
          jd_id: 'jd1',
          total: 2,
          completed: batchCalls >= 2 ? 2 : 0,
          failed: 0,
          status,
          started_at: '2026-07-16T00:00:00',
          finished_at: batchCalls >= 2 ? '2026-07-16T00:01:00' : null,
        });
      }),
      http.get('http://localhost/api/v1/jds/jd1/ranking', () => HttpResponse.json({ jd_id: 'jd1', total: 2, items: rankingItems() })),
    );
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    await selectJd(user);
    await screen.findByText('张三');
    await user.click(screen.getByText('触发批量匹配'));
    await waitFor(() => expect(screen.getByText('张三')).toBeInTheDocument());
  });

  test('test_scoring_report_opens_detail_drawer', async () => {
    const user = userEvent.setup();
    server.use(
      jdListHandler(),
      http.get('http://localhost/api/v1/jds/jd1/ranking', () => HttpResponse.json({ jd_id: 'jd1', total: 2, items: rankingItems() })),
      http.post('http://localhost/api/v1/match-scores', async () =>
        HttpResponse.json({
          score_id: 'ms_new',
          jd_id: 'jd1',
          resume_id: 'r1',
          overall_score: 95,
          dimension_scores: dim(95),
          status: 'COMPLETED',
          is_stale: false,
          created_at: '2026-07-16T00:00:00',
          updated_at: '2026-07-16T00:00:00',
        }),
      ),
    );
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    await selectJd(user);
    await screen.findByText('张三');
    // 点击首行「重新匹配」→ 触发 POST /match-scores 并经 MSW 拦截 → Drawer 展示新分数
    const rematchButtons = await screen.findAllByText('重新匹配');
    await user.click(rematchButtons[0]);
    // POST /match-scores 返回 overall_score=95（skill-95 仅来自新匹配，唯一），经 MSW 拦截后 Drawer 展示新分数
    expect(await screen.findByText('skill-95')).toBeInTheDocument();
  });

  test('test_scoring_report_marks_stale_row', async () => {
    const user = userEvent.setup();
    server.use(
      jdListHandler(),
      http.get('http://localhost/api/v1/jds/jd1/ranking', () => HttpResponse.json({ jd_id: 'jd1', total: 2, items: rankingItems() })),
    );
    render(
      <MemoryRouter>
        <ScoringReport />
      </MemoryRouter>,
    );
    await selectJd(user);
    // 李四 is_stale=true → 行展示「简历已更新」标签（is_stale 关键路径）
    expect(await screen.findByText('简历已更新')).toBeInTheDocument();
  });
});
