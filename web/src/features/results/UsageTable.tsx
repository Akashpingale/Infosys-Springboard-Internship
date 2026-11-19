import type { components } from '@/api/types.gen';
import type { RunStage } from '@/features/run/useRun';

type Usage = components['schemas']['Usage'];

export const USAGE_NOT_RECORDED =
  'Not recorded for this run. Runs made before request counting was added do not have these numbers.';

export interface UsageRow {
  key: string;
  label: string;
  llm: number;
  search: number;
}

export function usageRows(usage: Usage, stages: RunStage[]): UsageRow[] {
  const byStage = usage.by_stage ?? {};
  const labels = new Map(stages.map((stage) => [stage.key, stage.label]));
  const ordered = stages.map((stage) => stage.key).filter((key) => key in byStage);
  for (const key of Object.keys(byStage)) {
    if (!ordered.includes(key)) {
      ordered.push(key);
    }
  }
  return ordered.map((key) => ({
    key,
    label: labels.get(key) ?? key,
    llm: byStage[key]?.llm_calls ?? 0,
    search: byStage[key]?.search_calls ?? 0,
  }));
}

export function UsageTable({ usage, stages }: { usage: Usage | null | undefined; stages: RunStage[] }) {
  return (
    <section aria-labelledby="usage-heading" className="space-y-4">
      <div className="space-y-1">
        <h3 id="usage-heading">Usage</h3>
        <p className="max-w-prose text-small text-content-muted">
          AI requests and searches each stage sent, counting every retry and the fallback model.
        </p>
      </div>
      {usage ? (
        <div className="overflow-x-auto rounded-panel border border-line" tabIndex={0} aria-label="Usage per stage, scrolls sideways">
          <table className="w-full border-collapse text-small">
            <caption className="sr-only">AI requests and searches per stage</caption>
            <thead className="bg-raised">
              <tr>
                <th scope="col" className="border-b border-line px-3 py-2 text-left font-medium text-content-secondary">
                  Stage
                </th>
                <th scope="col" className="border-b border-line px-3 py-2 text-right font-medium text-content-secondary">
                  AI requests
                </th>
                <th scope="col" className="border-b border-line px-3 py-2 text-right font-medium text-content-secondary">
                  Searches
                </th>
              </tr>
            </thead>
            <tbody>
              {usageRows(usage, stages).map((row) => (
                <tr key={row.key} className="border-b border-line">
                  <th scope="row" className="bg-surface px-3 py-2 text-left font-normal text-content">
                    {row.label}
                  </th>
                  <td className="tabular bg-surface px-3 py-2 text-right text-content-secondary">{row.llm}</td>
                  <td className="tabular bg-surface px-3 py-2 text-right text-content-secondary">{row.search}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" className="bg-surface px-3 py-2 text-left font-medium text-content">
                  Total
                </th>
                <td className="tabular bg-surface px-3 py-2 text-right font-medium text-content">{usage.llm_calls}</td>
                <td className="tabular bg-surface px-3 py-2 text-right font-medium text-content">{usage.search_calls}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      ) : (
        <p className="max-w-prose text-small text-content-secondary">{USAGE_NOT_RECORDED}</p>
      )}
    </section>
  );
}
