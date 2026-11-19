import { FileText } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { REPORT_COPY } from '@/features/report/copy';
import { canHaveReport, useIsGenerating } from '@/features/report/useReport';
import type { RunDetail } from '@/features/run/useRun';

export type ReportButtonState = 'generate' | 'generating' | 'view' | 'update';

export const REPORT_BUTTON_LABELS: Record<ReportButtonState, string> = {
  generate: REPORT_COPY.generate,
  generating: REPORT_COPY.generatingButton,
  view: REPORT_COPY.view,
  update: REPORT_COPY.update,
};

export function reportButtonState(run: RunDetail, generating: boolean): ReportButtonState {
  if (generating) {
    return 'generating';
  }
  if (!run.report?.exists) {
    return 'generate';
  }
  return run.report.stale ? 'update' : 'view';
}

export function ReportButton({ run }: { run: RunDetail }) {
  const navigate = useNavigate();
  const generating = useIsGenerating(run.id);
  if (!canHaveReport(run)) {
    return null;
  }
  const state = reportButtonState(run, generating);
  const path = `/runs/${encodeURIComponent(run.id)}/report`;
  const label = REPORT_BUTTON_LABELS[state];
  if (state === 'generating') {
    return (
      <Button variant="primary" loading>
        {label}
      </Button>
    );
  }
  if (state === 'view') {
    return (
      <Button asChild variant="primary">
        <Link to={path}>
          <FileText aria-hidden="true" />
          {label}
        </Link>
      </Button>
    );
  }
  return (
    <Button variant="primary" onClick={() => navigate(path, { state: { generate: true } })}>
      <FileText aria-hidden="true" />
      {label}
    </Button>
  );
}
