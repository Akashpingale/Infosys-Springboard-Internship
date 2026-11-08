import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { API_URL, ApiError, request } from '@/api/client';
import { server } from '@/test/server';

describe('API client', () => {
  it('reads its base URL from the environment, never a hard-coded host', () => {
    expect(API_URL).toMatch(/^https?:\/\//);
    expect(API_URL.endsWith('/')).toBe(false);
  });

  it('returns the parsed reply', async () => {
    server.use(http.get(`${API_URL}/api/meta`, () => HttpResponse.json({ app_name: 'x' })));

    await expect(request<{ app_name: string }>('/api/meta')).resolves.toEqual({ app_name: 'x' });
  });

  it("passes on the backend's own message and code, so a screen never interprets a status", async () => {
    server.use(
      http.get(`${API_URL}/api/runs/absent`, () =>
        HttpResponse.json(
          { error: { code: 'run_not_found', message: 'This validation could not be found.' } },
          { status: 404 },
        ),
      ),
    );

    const failure = await request('/api/runs/absent').catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(ApiError);
    const apiError = failure as ApiError;
    expect(apiError.message).toBe('This validation could not be found.');
    expect(apiError.code).toBe('run_not_found');
    expect(apiError.status).toBe(404);
    expect(apiError.isOffline).toBe(false);
  });

  it('says how to start the server when it cannot be reached', async () => {
    server.use(http.get(`${API_URL}/health`, () => HttpResponse.error()));

    const failure = (await request('/health').catch((error: unknown) => error)) as ApiError;

    expect(failure.isOffline).toBe(true);
    expect(failure.message).toContain('python app.py');
  });

  it('handles an error body it cannot read without showing internals', async () => {
    server.use(http.get(`${API_URL}/api/meta`, () => new HttpResponse('<html>502</html>', { status: 502 })));

    const failure = (await request('/api/meta').catch((error: unknown) => error)) as ApiError;

    expect(failure.message).toBe('The server answered with an error (HTTP 502).');
    expect(failure.code).toBe('unexpected_error');
  });

  it('resolves to undefined for the 204 a delete returns', async () => {
    server.use(http.delete(`${API_URL}/api/runs/r1`, () => new HttpResponse(null, { status: 204 })));

    await expect(request('/api/runs/r1', { method: 'DELETE' })).resolves.toBeUndefined();
  });

  it('reads the Markdown report as text', async () => {
    server.use(http.get(`${API_URL}/api/runs/r1/report.md`, () => new HttpResponse('# Report')));

    await expect(request<string>('/api/runs/r1/report.md', { as: 'text' })).resolves.toBe('# Report');
  });

  it('sends a JSON body with its content type', async () => {
    let seen: { body: unknown; type: string | null } = { body: null, type: null };
    server.use(
      http.post(`${API_URL}/api/runs`, async ({ request: received }) => {
        seen = { body: await received.json(), type: received.headers.get('Content-Type') };
        return HttpResponse.json({ run_id: 'r1', state: 'queued' }, { status: 202 });
      }),
    );

    await request('/api/runs', { method: 'POST', body: { submission: { industry: 'AgriTech' } } });

    expect(seen.type).toBe('application/json');
    expect(seen.body).toEqual({ submission: { industry: 'AgriTech' } });
  });
});
