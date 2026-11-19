import { Download, FileJson, FileText, Loader2 } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

import { ApiError } from '@/api/client';
import { Alert } from '@/components/Alert';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { REPORT_COPY } from '@/features/report/copy';
import {
  downloadReport,
  reportFileName,
  type FileFormat,
  type ReportDocument,
} from '@/features/report/useReport';
import { saveBlob, saveText } from '@/lib/download';
import { MESSAGES } from '@/lib/format';

export const SAVE_REFUSED = 'This browser would not let the page save a file.';

export interface DownloadMenuProps {
  runId: string;
  document: ReportDocument;
  pdfAvailable: boolean;
}

export function DownloadMenu({ runId, document, pdfAvailable }: DownloadMenuProps) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<FileFormat | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [saved, setSaved] = React.useState<string | null>(null);

  function report(message: string | null, failure: string | null): void {
    setSaved(message);
    setError(failure);
  }

  async function fetchFile(format: FileFormat): Promise<void> {
    setBusy(format);
    report(null, null);
    try {
      const reply = await downloadReport(runId, format);
      const name = reply.fileName ?? reportFileName(document, format);
      const ok = saveBlob(reply.blob, name);
      report(ok ? `Saved as ${name}.` : null, ok ? null : SAVE_REFUSED);
    } catch (cause) {
      report(null, cause instanceof ApiError ? cause.message : MESSAGES.backendDown);
    } finally {
      setBusy(null);
    }
  }

  function saveJson(): void {
    const name = reportFileName(document, 'json');
    const ok = saveText(JSON.stringify(document, null, 2), name, 'application/json');
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
        <Button variant="primary">
          <Download aria-hidden="true" />
          {REPORT_COPY.download}
        </Button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-2" aria-label="Download this report">
        <ul className="space-y-1">
          <li>
            <MenuItem
              icon={busy === 'pdf' ? Loader2 : FileText}
              spinning={busy === 'pdf'}
              disabled={!pdfAvailable || busy !== null}
              title="PDF"
              hint={pdfAvailable ? 'A printable document with page numbers and a table of contents.' : 'Not available.'}
              onClick={() => void fetchFile('pdf')}
            />
          </li>
          <li>
            <MenuItem
              icon={busy === 'markdown' ? Loader2 : FileText}
              spinning={busy === 'markdown'}
              disabled={busy !== null}
              title="Markdown"
              hint="The same report as plain text with headings and tables."
              onClick={() => void fetchFile('markdown')}
            />
          </li>
          <li>
            <MenuItem
              icon={FileJson}
              disabled={busy !== null}
              title="JSON"
              hint="The stored report document, unchanged."
              onClick={saveJson}
            />
          </li>
        </ul>

        {pdfAvailable ? null : <p className="px-3 py-2 text-small text-content-secondary">{REPORT_COPY.fontsMissing}</p>}
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
  icon: LucideIcon;
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
      className="flex min-h-[44px] w-full items-start gap-3 rounded-control px-3 py-2 text-left hover:bg-raised disabled:opacity-50"
    >
      <Icon className={`mt-0.5 size-4 shrink-0 text-content-muted${spinning ? ' animate-spin' : ''}`} aria-hidden="true" />
      <span className="min-w-0 flex-1">
        <span className="block text-body text-content">{title}</span>
        <span className="block text-micro text-content-muted">{hint}</span>
      </span>
    </button>
  );
}
