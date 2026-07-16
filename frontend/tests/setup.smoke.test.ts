import { server } from './mocks/server';
import { http, HttpResponse } from 'msw';

describe('MSW 拦截 smoke', () => {
  test('test_msw_server_intercepts_get', async () => {
    server.use(
      http.get('http://localhost/api/hello', () => HttpResponse.json({ msg: 'hi' })),
    );
    const res = await fetch('http://localhost/api/hello');
    const data = (await res.json()) as { msg: string };
    expect(data.msg).toBe('hi');
  });
});
