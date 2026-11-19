/**
 * Status (KIRO_UI_UPGRADE_SPEC.md Sections 7.6 and 10.1).
 *
 * Whether the backend answers, and which providers it has been given keys for. The two sources are
 * GET /health and GET /api/meta, and neither returns a key, a key fragment or a key length, so
 * there is nothing secret for this page to leak.
 *
 * "Configured" means a key and a model name are set. No provider is called, so it is not a claim
 * that the provider works; the page says so rather than implying a green light.
 */

import { CheckCircle2, CircleDashed } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { useHealth, useMeta, type MetaResponse } from '@/api/queries';
import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { MESSAGES, duration } from '@/lib/format';

export const CONFIGURED_NOTE =
  'Configured means a key and a model name are set. This page calls no provider, so it cannot say ' +
  'whether one is working.';
export const NO_KEY_NOTE = 'No key is ever sent to this page or shown here.';

function ProviderCard({
  name,
  role,
  configured,
  model,
}: {
  name: string;
  role: string;
  configured: boolean;
  model?: string | null;
}) {
  const Icon = configured ? CheckCircle2 : CircleDashed;
  return (
    <section
      aria-labelledby={`provider-${name}`}
      className="space-y-2 rounded-panel border border-line bg-surface p-4"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={`provider-${name}`} className="text-h3 font-sans">
          {name}
        </h2>
        <span
          className={cn(
            'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro',
            configured
              ? 'border-success-border bg-success-bg text-success'
              : 'border-line bg-raised text-content-secondary',
          )}
        >
          <Icon className="size-3.5 shrink-0" aria-hidden="true" />
          {configured ? 'Configured' : 'Not configured'}
        </span>
      </div>
      <p className="text-small text-content-muted">{role}</p>
      {/* Only the models have one to name; the search provider has no model, so no row is shown. */}
      {model ? (
        <dl className="space-y-1 text-small">
          <div className="flex gap-2">
            <dt className="text-content-muted">Model</dt>
            <dd className="font-mono text-micro text-content-secondary">{model}</dd>
          </div>
        </dl>
      ) : null}
      {configured ? null : (
        <p className="text-small text-content-secondary">
          Add its key to the backend&rsquo;s .env file and restart the server.
        </p>
      )}
    </section>
  );
}

function Limits({ limits }: { limits: MetaResponse['run_limits'] }) {
  const rows: [string, string][] = [
    ['Time limit for one run', duration(limits.time_limit_s)],
    ['Runs at once', String(limits.max_concurrent_runs)],
    ['Extra competitor searches', String(limits.competitor_max_extra_queries)],
    ['Results kept per search', String(limits.competitor_results_per_query)],
    ['Evidence items per analysis', String(limits.evidence_max_items)],
  ];
  return (
    <section aria-labelledby="limits-heading" className="rounded-panel border border-line bg-surface p-4">
      <h2 id="limits-heading" className="text-h3 font-sans">
        Limits
      </h2>
      <dl className="mt-3 divide-y divide-line text-small">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-4 py-2">
            <dt className="text-content-secondary">{label}</dt>
            <dd className="tabular text-content">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function ReportSettings({
  report,
  profiles,
}: {
  report: NonNullable<MetaResponse['report']>;
  profiles: NonNullable<MetaResponse['profiles']>;
}) {
  const rows: [string, string][] = [
    ['PDF fonts', report.pdf_available ? 'Installed' : 'Not installed'],
    ['Query profile', profiles.query_profile],
    ['Prompt profile', profiles.prompt_profile],
    ['Time limit for the written summary', duration(report.time_limit_s)],
  ];
  return (
    <section aria-labelledby="report-heading" className="rounded-panel border border-line bg-surface p-4">
      <h2 id="report-heading" className="text-h3 font-sans">
        Report and profiles
      </h2>
      <dl className="mt-3 divide-y divide-line text-small">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-4 py-2">
            <dt className="text-content-secondary">{label}</dt>
            <dd className="tabular text-content">{value}</dd>
          </div>
        ))}
      </dl>
      {report.pdf_available ? null : (
        <p className="mt-2 text-small text-content-secondary">
          Reports can still be downloaded as Markdown and JSON. The setup guide explains how to add the fonts.
        </p>
      )}
    </section>
  );
}

export function StatusPage() {
  const health = useHealth();
  const meta = useMeta();

  const reachable = health.isSuccess && !health.isError;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1>System status</h1>
        <p className="max-w-prose text-body text-content-secondary">
          {CONFIGURED_NOTE} {NO_KEY_NOTE}
        </p>
      </div>

      {health.isPending || meta.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2" aria-busy="true">
          {[0, 1, 2, 3].map((card) => (
            <Skeleton key={card} className="h-32 w-full" />
          ))}
        </div>
      ) : (
        <>
          <section
            aria-labelledby="backend-heading"
            className="space-y-2 rounded-panel border border-line bg-surface p-4"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="backend-heading" className="text-h3 font-sans">
                Backend
              </h2>
              <span
                className={cn(
                  'inline-flex h-6 items-center gap-2 rounded-pill border px-3 text-micro',
                  reachable
                    ? 'border-success-border bg-success-bg text-success'
                    : 'border-danger-border bg-danger-bg text-danger',
                )}
              >
                {reachable ? 'Reachable' : 'Not reachable'}
              </span>
            </div>
            {reachable ? (
              <dl className="space-y-1 text-small">
                <div className="flex gap-2">
                  <dt className="text-content-muted">Reported</dt>
                  <dd className="text-content-secondary">{health.data?.status ?? '\u2014'}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-content-muted">Version</dt>
                  <dd className="tabular text-content-secondary">{meta.data?.version ?? '\u2014'}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="text-content-muted">Application</dt>
                  <dd className="text-content-secondary">{meta.data?.app_name ?? '\u2014'}</dd>
                </div>
              </dl>
            ) : (
              <Alert
                tone="error"
                action={
                  <Button
                    variant="secondary"
                    size="small"
                    onClick={() => {
                      void health.refetch();
                      void meta.refetch();
                    }}
                  >
                    Try again
                  </Button>
                }
              >
                {health.error instanceof ApiError ? health.error.message : MESSAGES.backendDown}
              </Alert>
            )}
          </section>

          {meta.data ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <ProviderCard
                  name={meta.data.providers.llm.name}
                  role="Writes and checks the analyses."
                  configured={meta.data.providers.llm.configured}
                  model={meta.data.providers.llm.model}
                />
                <ProviderCard
                  name={meta.data.providers.fallback_llm.name}
                  role="Takes over when the first model is unavailable."
                  configured={meta.data.providers.fallback_llm.configured}
                  model={meta.data.providers.fallback_llm.model}
                />
                <ProviderCard
                  name={meta.data.providers.search.name}
                  role="Searches the web for the evidence."
                  configured={meta.data.providers.search.configured}
                  model={null}
                />
              </div>
              <Limits limits={meta.data.run_limits} />
              {meta.data.report && meta.data.profiles ? (
                <ReportSettings report={meta.data.report} profiles={meta.data.profiles} />
              ) : null}
            </>
          ) : meta.isError ? (
            <Alert
              tone="error"
              title="Can't read the configuration"
              action={
                <Button variant="secondary" size="small" onClick={() => void meta.refetch()}>
                  Try again
                </Button>
              }
            >
              {meta.error instanceof ApiError ? meta.error.message : MESSAGES.backendDown}
            </Alert>
          ) : null}
        </>
      )}

      <p className="text-small text-content-muted">
        Starting a validation needs {meta.data?.providers.llm.name ?? 'the model'} and{' '}
        {meta.data?.providers.search.name ?? 'the search provider'}.{' '}
        {/*
          Underlined, not just coloured. This link sits inside a sentence, where colour alone does
          not distinguish it (WCAG 1.4.1, and Section 6.9's rule that nothing relies on colour).
        */}
        <Link to="/" className="text-primary underline underline-offset-2">
          Start a new validation
        </Link>
        .
      </p>
    </div>
  );
}
