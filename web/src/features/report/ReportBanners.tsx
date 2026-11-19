import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { REPORT_COPY, partialLine } from '@/features/report/copy';
import type { ReportDocument } from '@/features/report/useReport';

export interface ReportBannersProps {
  document: ReportDocument;
  stale: boolean;
  unfinished: string[];
  busy: boolean;
  onRegenerate: () => void;
  onRetryNarrative: () => void;
}

export function ReportBanners({ document, stale, unfinished, busy, onRegenerate, onRetryNarrative }: ReportBannersProps) {
  const failed = document.meta.narrative_status === 'failed';
  const partial = document.meta.run_status === 'partial';
  if (!stale && !failed && !partial) {
    return null;
  }
  return (
    <div className="space-y-3">
      {stale ? (
        <Alert
          tone="warning"
          action={
            <Button variant="secondary" size="small" onClick={onRegenerate} disabled={busy} data-print-hide>
              {REPORT_COPY.regenerate}
            </Button>
          }
        >
          {REPORT_COPY.stale}
        </Alert>
      ) : null}
      {failed ? (
        <Alert
          tone="warning"
          action={
            <Button variant="secondary" size="small" onClick={onRetryNarrative} disabled={busy} data-print-hide>
              {REPORT_COPY.tryAgain}
            </Button>
          }
        >
          {REPORT_COPY.narrativeFailed}
        </Alert>
      ) : null}
      {partial ? <Alert tone="info">{partialLine(unfinished)}</Alert> : null}
    </div>
  );
}
