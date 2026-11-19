import type { components } from '@/api/types.gen';

type Versions = components['schemas']['Versions'];

export const VERSIONS_NOT_RECORDED =
  'Not recorded for this run. Runs made before version recording was added do not have them.';

export const AGENT_LABELS: Record<string, string> = {
  extraction: 'Understanding your idea',
  market: 'Market analysis',
  competitors: 'Competitor analysis',
  swot: 'Strengths and risks',
  mvp: 'MVP features',
  gtm: 'Go-to-market',
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-content-secondary">{label}</dt>
      <dd className="font-mono text-micro text-content">{value}</dd>
    </div>
  );
}

export function VersionsPanel({ versions }: { versions: Versions | null | undefined }) {
  const prompts = Object.entries(versions?.prompt_versions ?? {});
  return (
    <section aria-labelledby="versions-heading" className="space-y-4">
      <div className="space-y-1">
        <h3 id="versions-heading">Versions</h3>
        <p className="max-w-prose text-small text-content-muted">Which query and prompt set produced this result.</p>
      </div>
      {versions ? (
        <div className="rounded-panel border border-line bg-surface px-4 py-2">
          <dl className="divide-y divide-line text-small">
            <Row label="Query profile" value={versions.query_profile} />
            <Row label="Prompt profile" value={versions.prompt_profile} />
            <Row label="App version" value={versions.app_version} />
            {prompts.map(([agent, version]) => (
              <Row key={agent} label={`Prompt: ${AGENT_LABELS[agent] ?? agent}`} value={version} />
            ))}
          </dl>
        </div>
      ) : (
        <p className="max-w-prose text-small text-content-secondary">{VERSIONS_NOT_RECORDED}</p>
      )}
    </section>
  );
}
