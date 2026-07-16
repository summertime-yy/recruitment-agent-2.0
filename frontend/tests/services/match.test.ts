import { server } from '../mocks/server';
import { http, HttpResponse } from 'msw';
import { matchApi } from '@/services/match';

function dim(score = 80) {
  return {
    skill_match: { score, rationale: `skill-${score}` },
    experience_match: { score, rationale: `exp-${score}` },
    education_match: { score, rationale: `edu-${score}` },
    overall_reasoning: 'overall-reasoning-text',
  };
}

describe('matchApi (S4-10)', () => {
  test('test_matchApi_matchOne_serializes_body', async () => {
    let captured: any = null;
    server.use(
      http.post('http://localhost/api/v1/match-scores', async ({ request }) => {
        captured = await request.json();
        return HttpResponse.json({
          score_id: 'ms_abc',
          jd_id: captured.jd_id,
          resume_id: captured.resume_id,
          overall_score: 79,
          dimension_scores: dim(79),
          status: 'COMPLETED',
          is_stale: false,
          created_at: '2026-07-16T00:00:00',
          updated_at: '2026-07-16T00:00:00',
        });
      }),
    );
    const data = { jd_id: 'jd1', resume_id: 'r1', force: false };
    const res = await matchApi.matchOne(data);
    expect(captured).toEqual(data);
    expect(res.score_id).toBe('ms_abc');
    expect(res.overall_score).toBe(79);
    expect(res.dimension_scores.skill_match.score).toBe(79);
  });

  test('test_matchApi_rankByJd_reads_items', async () => {
    server.use(
      http.get('http://localhost/api/v1/jds/jd1/ranking', () =>
        HttpResponse.json({
          jd_id: 'jd1',
          total: 3,
          items: [
            { score_id: 's1', resume_id: 'r1', candidate_name: 'A', overall_score: 90, dimension_scores: dim(90), is_stale: false, created_at: '' },
            { score_id: 's2', resume_id: 'r2', candidate_name: 'B', overall_score: 80, dimension_scores: dim(80), is_stale: false, created_at: '' },
            { score_id: 's3', resume_id: 'r3', candidate_name: 'C', overall_score: 70, dimension_scores: dim(70), is_stale: true, created_at: '' },
          ],
        }),
      ),
    );
    const res = await matchApi.rankByJd('jd1', { limit: 10 });
    expect(res.items.length).toBe(3);
    expect(typeof res.items[0].overall_score).toBe('number');
    expect(res.items[0].overall_score).toBe(90);
  });

  test('test_matchApi_batchMatch_returns_task_id', async () => {
    server.use(
      http.post('http://localhost/api/v1/match-scores/batch', () =>
        HttpResponse.json({ task_id: 't1', jd_id: 'jd1', total_submitted: 5, submitted_at: '2026-07-16T00:00:00' }),
      ),
    );
    const res = await matchApi.batchMatch({ jd_id: 'jd1', limit: 5 });
    expect(res.task_id).toBe('t1');
  });

  test('test_matchApi_getBatchStatus_polls_completed', async () => {
    let calls = 0;
    server.use(
      http.get('http://localhost/api/v1/match-scores/batch/t1', () => {
        calls += 1;
        const status = calls >= 3 ? 'COMPLETED' : 'RUNNING';
        return HttpResponse.json({
          task_id: 't1',
          jd_id: 'jd1',
          total: 5,
          completed: calls >= 3 ? 5 : calls,
          failed: 0,
          status,
          started_at: '2026-07-16T00:00:00',
          finished_at: calls >= 3 ? '2026-07-16T00:01:00' : null,
        });
      }),
    );
    const r1 = await matchApi.getBatchStatus('t1');
    const r2 = await matchApi.getBatchStatus('t1');
    const r3 = await matchApi.getBatchStatus('t1');
    expect(r1.status).toBe('RUNNING');
    expect(r2.status).toBe('RUNNING');
    expect(r3.status).toBe('COMPLETED');
  });
});
