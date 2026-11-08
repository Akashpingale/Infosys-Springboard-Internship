/**
 * Export menu (KIRO_UI_UPGRADE_SPEC.md Section 7.4).
 *
 * Three ways out of the result. Markdown comes from the backend's own report endpoint, so the file
 * is the report the project already produces rather than something this page writes. JSON is the
 * untouched result. PDF uses the browser's print dialogue with the print stylesheet, which is why
 * it asks the page to lay every section out first.
 *
 * It is a popover of buttons, not a menu widget: Radix gives the focus trap, Escape and the return
 * of focus that Section 6.9 requires, and no further dependency is needed.
 */

import { Download, FileJson, FileText, Loader2, Printer } from 'lucide-react';
import * as React from 'react';

import { ApiError, request } from '@/api/client';
import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import type { RunDetail } from '@/features/run/useRun';
import { saveText } from '@/lib/download';
import { MESSAGES } from '@/lib/format';
import { downloadName } from '@/lib/runDetails';
import type { PipelineResult } from '@/lib/results';

export const SAVE_REFUSED = 'This browser would not let the page save a file.';
export const PDF_HINT = 'Opens the browser\u2019s print dialogue. Choose "Save as PDF" there.';

export interface ExportMenuProps {
  run: RunDetail;
  result: PipelineResult | null;
  /**
   * Lays every section out and then prints. The results workspace shows one tab at a time, so the
   * page has to render the rest before the print dialogue opens or they would be missing.
   */
  onPrint: () => void;
}

export function ExportMenu({ run, result, onPrint }: ExportMenuProps) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState<string | null>(null);

  function report(message: string | null, failure: string | null): void {
    setSaved(message);
    setError(failure);
  }

  async function exportMarkdown(): Promise<void> {
    setBusy(true);
    report(null, null);
    try {
      const text = await request<string>(`/api/runs/${encodeURIComponent(run.id)}/report.md`, { as: 'text' });
      const name = downloadName(run, 'md');
      const ok = saveText(text, name, 'text/markdown');
      report(ok ? `Saved as ${name}.` : null, ok ? null : SAVE_REFUSED);
    } catch (cause) {
      report(null, cause instanceof ApiError ? cause.message : MESSAGES.backendDown);
    } finally {
      setBusy(false);
    }
  }

  function exportJson(): void {
    if (!result) {
      report(null, 'This run produced no result to save.');
      return;
    }
    const name = downloadName(run, 'json');
    const ok = saveText(JSON.stringify(result, null, 2), name, 'application/json');
    report(ok ? `Saved as ${name}.` : null, ok ? null : SAVE_REFUSED);
  }

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          report(null, null);
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="secondary">
          <Download aria-hidden="true" />
          Export
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-2" aria-label="Export this result">
        <ul className="space-y-1">
          <li>
            <MenuItem
              icon={busy ? Loader2 : FileText}
              spinning={busy}
              disabled={busy}
              title="Markdown report"
              hint="The full written report from the server."
              onClick={() => void exportMarkdown()}
            />
          </li>
          <li>
            <MenuItem
              icon={FileJson}
              disabled={!result}
              title="JSON result"
              hint={result ? 'Exactly what the backend returned.' : 'There is no result to save.'}
              onClick={exportJson}
            />
          </li>
          <li>
            <MenuItem
              icon={Printer}
              title="PDF"
              hint={PDF_HINT}
              onClick={() => {
                setOpen(false);
                onPrint();
              }}
            />
          </li>
        </ul>

        {saved ? (
          <p role="status" className="px-3 py-2 text-small text-content-secondary">
            {saved}
          </p>
        ) : null}
        {error ? (
          <Alert tone="error" className="mt-2">
            {error}
          </Alert>
        ) : null}
      </PopoverContent>
    </Popover>
  );
}

interface MenuItemProps {
  icon: typeof FileText;
  title: string;
  hint: string;
  onClick: () => void;
  disabled?: boolean;
  spinning?: boolean;
}

function MenuItem({ icon: Icon, title, hint, onClick, disabled, spinning }: MenuItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex w-full items-start gap-3 rounded-control px-3 py-2 text-left hover:bg-raised disabled:opacity-50"
    >
      <Icon className={`mt-0.5 size-4 shrink-0 text-content-muted${spinning ? ' animate-spin' : ''}`} aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block text-body text-content">{title}</span>
        <span className="block text-micro text-content-muted">{hint}</span>
      </span>
    </button>
  );
}
