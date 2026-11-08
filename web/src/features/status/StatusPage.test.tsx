/**
 * The status screen (KIRO_UI_UPGRADE_SPEC.md Prompt I, Sections 7.6 and 10.1).
 *
 * The page reads /health and /api/meta, neither of which returns a key. The last test is the one
 * that matters most: a key planted in the replies must not appear anywhere on the page, so a future
 * change that starts rendering whatever the backend sends would fail here.
 */

import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { API_URL } from '@/api/client';
import type { MetaResponse } from '@/api/queries';
import { StatusPage } from '@/features/status/StatusPage';
import { META } from '@/test/fixtures';
import { renderWithApp } from '@/test/render';
import { server } from '@/test/server';

const HEALTH = { status: 'ok', llm_configured: true, search_configured: true };

function serve(meta: MetaResponse = META, health: Record<string, unknown> = HEALTH) {
  server.use(
    http.get(`${API_URL}/health`, () => HttpResponse.json(health)),
    http.get(`${API_URL}/api/meta`, () => HttpResponse.json(meta)),
  );
}

function card(name: string | RegExp) {
  return screen.getByRole('region', { name });
}

describe('Status: the backend', () => {
  it('says it is reachable, with the version it reports', async () => {
    serve();
    renderWithApp(<StatusPage />);

    const backend = await screen.findByRole('region', { name: 'Backend' });
    expect(within(backend).getByText('Reachable')).toBeInTheDocument();
    expect(within(backend).getByText('0.1.0')).toBeInTheDocument();
    expect(within(backend).getByText('AI Startup Idea Validator')).toBeInTheDocument();
    expect(within(backend).getByText('ok')).toBeInTheDocument();
  });

  it('says how to start the server when it is not answering, and offers a retry', async () => {
    let calls = 0;
    server.use(
      http.get(`${API_URL}/health`, () => {
        calls += 1;
        // The test query client does not retry, so the first answer is the one that is shown.
        return calls === 1 ? HttpResponse.error() : HttpResponse.json(HEALTH);
      }),
      http.get(`${API_URL}/api/meta`, () => HttpResponse.json(META)),
    );
    const user = userEvent.setup();
    renderWithApp(<StatusPage />);

    expect(await screen.findByText(/start it with/i, {}, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.getByText('Not reachable')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /try again/i }));

    expect(await screen.findByText('Reachable')).toBeInTheDocument();
  }, 20000);
});

describe('Status: the providers', () => {
  it('names each provider, its job and its model', async () => {
    serve();
    renderWithApp(<StatusPage />);

    const gemini = await screen.findByRole('region', { name: 'Gemini' });
    expect(within(gemini).getByText('Configured')).toBeInTheDocument();
    expect(within(gemini).getByText('gemini-3-flash-preview')).toBeInTheDocument();
    expect(within(gemini).getByText(/writes and checks the analyses/i)).toBeInTheDocument();

    const groq = card('Groq');
    expect(within(groq).getByText('openai/gpt-oss-120b')).toBeInTheDocument();
    expect(within(groq).getByText(/takes over when the first model is unavailable/i)).toBeInTheDocument();

    const tavily = card('Tavily');
    expect(within(tavily).getByText(/searches the web for the evidence/i)).toBeInTheDocument();
  });

  it('says what to do about a provider with no key, without naming the key', async () => {
    serve({
      ...META,
      providers: {
        ...META.providers,
        fallback_llm: { name: 'Groq', configured: false, model: 'openai/gpt-oss-120b' },
      },
    });
    renderWithApp(<StatusPage />);

    const groq = await screen.findByRole('region', { name: 'Groq' });
    expect(within(groq).getByText('Not configured')).toBeInTheDocument();
    expect(within(groq).getByText(/add its key to the backend\u2019s \.env file/i)).toBeInTheDocument();
  });

  it('never claims a configured provider works', async () => {
    serve();
    renderWithApp(<StatusPage />);

    await screen.findByRole('region', { name: 'Gemini' });
    expect(screen.getByText(/this page calls no provider, so it cannot say whether one is working/i)).toBeInTheDocument();
  });

  it('names no model for the provider that has none, rather than showing an empty row', async () => {
    serve();

    renderWithApp(<StatusPage />);

    const tavily = await screen.findByRole('region', { name: 'Tavily' });
    expect(within(tavily).queryByText('Model')).not.toBeInTheDocument();
    expect(within(within(screen.getByRole('region', { name: 'Gemini' })).getByText('Model').closest('div')!)
      .getByText('gemini-3-flash-preview')).toBeInTheDocument();
  });
});

describe('Status: the limits', () => {
  it("shows the backend's own run limits", async () => {
    serve();
    renderWithApp(<StatusPage />);

    const limits = await screen.findByRole('region', { name: 'Limits' });
    expect(within(limits).getByText('Time limit for one run').closest('div')).toHaveTextContent('2:42');
    expect(within(limits).getByText('Runs at once').closest('div')).toHaveTextContent('2');
    expect(within(limits).getByText('Extra competitor searches').closest('div')).toHaveTextContent('5');
    expect(within(limits).getByText('Results kept per search').closest('div')).toHaveTextContent('3');
    expect(within(limits).getByText('Evidence items per analysis').closest('div')).toHaveTextContent('12');
  });
});

describe('Status: secrets', () => {
  it('shows no key, and nothing of a key the backend might send by mistake', async () => {
    // Assembled rather than written out, so the repository holds no string shaped like a real key.
    const planted = ['AI', 'za', 'Sy', 'FAKE-FOR-THIS-TEST-ONLY', '0000000000'].join('');
    serve(
      {
        ...META,
        providers: {
          ...META.providers,
          llm: { name: 'Gemini', configured: true, model: 'gemini-3-flash-preview' },
        },
        // A field the page does not know about, as a leak would arrive.
        ...({ api_key: planted } as Partial<MetaResponse>),
      },
      { ...HEALTH, api_key: planted },
    );
    const { container } = renderWithApp(<StatusPage />);

    await screen.findByRole('region', { name: 'Gemini' });

    expect(container.textContent).not.toContain(planted);
    expect(container.textContent).not.toMatch(/AIza|gsk_|tvly-/);
    expect(screen.getByText(/no key is ever sent to this page or shown here/i)).toBeInTheDocument();
  });
});
