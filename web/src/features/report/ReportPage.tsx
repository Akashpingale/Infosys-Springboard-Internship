import { Loader2 } from 'lucide-react';
import * as React from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { useMeta } from '@/api/queries';
import { Alert } from '@/components/Alert';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { EmptyState } from '@/components/EmptyState';
import { StatusChip } from '@/components/StatusChip';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { REPORT_COPY } from '@/features/report/copy';
import { DownloadMenu } from '@/features/report/DownloadMenu';
import { ReportBanners } from '@/features/report/ReportBanners';
import { ReportBibliography } from '@/features/report/ReportBibliography';
import { ReportBlocks, sourceAnchor } from '@/features/report/ReportBlocks';
import { ReportToc, sectionAnchor } from '@/features/report/ReportToc';
import {
  canHaveReport,
  useGenerateReport,
  useReport,
  type GenerateReportInput,
  type ReportDocument,
  type ReportSection,
} from '@/features/report/useReport';
import { useRun, type RunDetail } from '@/features/run/useRun';
import { dateTime, MESSAGES } from '@/lib/format';

const COVER = 'cover';
const SOURCES = 'sources';
const UNFINISHED = new Set(['failed', 'skipped', 'cancelled']);

function allSections(document: ReportDocument): ReportSection[] {
  return [...(document.sections ?? []), ...(document.appendix_sections ?? [])];
}

function unfinishedParts(run: RunDetail | undefined, document: ReportDocument): string[] {
  const stages = (run?.stages ?? []).filter((stage) => UNFINISHED.has(stage.status)).map((stage) => stage.label);
  if (stages.length > 0) {
    return stages;
  }
  const titles = new Map(allSections(document).map((section) => [section.id, section.title]));
  return (document.meta.sections_missing ?? []).map((entry) => titles.get(entry.id) ?? entry.id);
}

function focusTarget(id: string): void {
  const target = document.getElementById(id);
  if (!target) {
    return;
  }
  target.scrollIntoView({ block: 'start' });
  target.focus({ preventScroll: true });
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : MESSAGES.backendDown;
}

function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <Skeleton className="h-9 w-80" />
      <div className="space-y-3 rounded-panel border border-line bg-surface p-6">
        {[0, 1, 2, 3].map((row) => (
          <Skeleton key={row} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

export function ReportPage() {
  const { runId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const run = useRun(runId);
  const meta = useMeta();
  const ready = canHaveReport(run.data);
  const report = useReport(runId, ready);
  const generate = useGenerateReport(runId);
  const controller = React.useRef<AbortController | null>(null);
  const cancelled = React.useRef(false);
  const asked = React.useRef(false);
  const [confirming, setConfirming] = React.useState(false);
  const [current, setCurrent] = React.useState<string | null>(null);

  const start = React.useCallback(
    (input: Omit<GenerateReportInput, 'signal'> = {}) => {
      controller.current?.abort();
      const next = new AbortController();
      controller.current = next;
      cancelled.current = false;
      generate.mutate({ ...input, signal: next.signal });
    },
    [generate],
  );

  function cancel(): void {
    cancelled.current = true;
    controller.current?.abort();
    generate.reset();
  }

  const wantsReport = Boolean((location.state as { generate?: boolean } | null)?.generate);
  React.useEffect(() => {
    if (!wantsReport || asked.current || !ready || !report.isSuccess || generate.isPending) {
      return;
    }
    asked.current = true;
    navigate(location.pathname, { replace: true, state: null });
    start();
  }, [wantsReport, ready, report.isSuccess, generate.isPending, navigate, location.pathname, start]);

  const shown = generate.data ?? report.data ?? null;
  const sections = React.useMemo(() => (shown ? allSections(shown) : []), [shown]);
  const entries = React.useMemo(
    () => sections.filter((section) => section.id !== COVER).map(({ id, title }) => ({ id, title })),
    [sections],
  );
  const titles = React.useMemo(() => new Map(sections.map((section) => [section.id, section.title])), [sections]);

  React.useEffect(() => {
    if (entries.length === 0 || typeof IntersectionObserver === 'undefined') {
      return;
    }
    const observer = new IntersectionObserver(
      (seen) => {
        const first = seen
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (first) {
          setCurrent(first.target.id.slice(sectionAnchor('').length));
        }
      },
      { rootMargin: '0px 0px -70% 0px' },
    );
    for (const entry of entries) {
      const target = document.getElementById(sectionAnchor(entry.id));
      if (target) {
        observer.observe(target);
      }
    }
    return () => observer.disconnect();
  }, [entries]);

  if (run.isError && !run.data) {
    const missing = run.error instanceof ApiError && run.error.status === 404;
    return (
      <div className="mx-auto max-w-form space-y-6">
        <h1>{missing ? 'That validation is not here' : 'Can\u2019t load this validation'}</h1>
        <Alert
          tone="error"
          action={
            missing ? (
              <Button asChild variant="secondary" size="small">
                <Link to="/history">Open history</Link>
              </Button>
            ) : (
              <Button variant="secondary" size="small" onClick={() => void run.refetch()}>
                {REPORT_COPY.tryAgain}
              </Button>
            )
          }
        >
          {errorText(run.error)}
        </Alert>
      </div>
    );
  }

  if (!run.data) {
    return <ReportSkeleton />;
  }

  const detail = run.data;
  const back = `/runs/${encodeURIComponent(detail.id)}`;
  const backButton = (
    <Button asChild variant="secondary">
      <Link to={back}>{REPORT_COPY.back}</Link>
    </Button>
  );

  if (!ready) {
    return (
      <div className="mx-auto max-w-form space-y-6">
        <h1>{detail.title}</h1>
        <Alert tone="info" action={backButton}>
          {REPORT_COPY.notFinished}
        </Alert>
      </div>
    );
  }

  const writing = generate.isPending;
  const failure = generate.isError && !cancelled.current ? errorText(generate.error) : null;
  const pdfAvailable = meta.data?.report?.pdf_available ?? false;

  function regenerate(existing: ReportDocument): void {
    if (existing.meta.narrative_status === 'ok') {
      setConfirming(true);
      return;
    }
    start({ force: true });
  }

  function select(id: string): void {
    setCurrent(id);
    focusTarget(sectionAnchor(id));
  }

  const progress = writing ? (
    <div className="flex flex-wrap items-center gap-3 rounded-panel border border-info-border bg-info-bg p-4" data-print-hide>
      <Loader2 className="size-5 shrink-0 animate-spin text-info" aria-hidden="true" />
      <p role="status" aria-live="polite" className="min-w-0 flex-1 text-body text-content-secondary">
        {REPORT_COPY.generating}
      </p>
      <Button variant="secondary" size="small" onClick={cancel}>
        {REPORT_COPY.cancel}
      </Button>
    </div>
  ) : null;

  const failed = failure ? (
    <Alert
      tone="error"
      title="The report was not written"
      action={
        <Button variant="secondary" size="small" onClick={() => start({ force: Boolean(shown) })}>
          {REPORT_COPY.tryAgain}
        </Button>
      }
    >
      {failure}
    </Alert>
  ) : null;

  if (!shown) {
    return (
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 className="min-w-0 font-condensed text-display">{detail.title}</h1>
          <div data-print-hide className="flex flex-wrap items-center gap-2">
            {backButton}
          </div>
        </div>
        {progress}
        {failed}
        {report.isError ? (
          <Alert
            tone="error"
            action={
              <Button variant="secondary" size="small" onClick={() => void report.refetch()}>
                {REPORT_COPY.tryAgain}
              </Button>
            }
          >
            {errorText(report.error)}
          </Alert>
        ) : null}
        {report.isPending || writing ? (
          <ReportSkeleton />
        ) : report.isSuccess ? (
          <EmptyState
            message={REPORT_COPY.notGenerated}
            action={
              <Button variant="primary" onClick={() => start()}>
                {REPORT_COPY.generate}
              </Button>
            }
          />
        ) : null}
      </div>
    );
  }

  const paper = shown;
  const cover = sections.find((section) => section.id === COVER);
  const stale = generate.data ? false : Boolean(detail.report?.stale);

  return (
    <div data-report-page className="space-y-6">
      <a
        href="#report-document"
        className="skip-link min-h-[44px] sm:min-h-0"
        onClick={(event) => {
          event.preventDefault();
          focusTarget('report-document');
        }}
      >
        Skip to the report
      </a>

      <div data-report-header className="space-y-3">
        <p className="text-small text-content-muted">{paper.title}</p>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <h1 id="report-title" className="min-w-0 font-condensed text-display">
            {paper.meta.idea_title}
          </h1>
          <div data-print-hide className="flex flex-wrap items-center gap-2">
            <DownloadMenu runId={detail.id} document={paper} pdfAvailable={pdfAvailable} />
            <Button variant="secondary" onClick={() => regenerate(paper)} disabled={writing}>
              {REPORT_COPY.regenerate}
            </Button>
            {backButton}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-pill border border-line bg-raised px-3 py-1 text-micro text-content-secondary">
            {paper.meta.industry}
          </span>
          <StatusChip kind={paper.meta.run_status} />
          <span className="text-small text-content-muted">Generated {dateTime(paper.meta.generated_at)}</span>
        </div>
        <p className="text-small text-content-muted">
          Version {paper.meta.app_version}, report format {paper.schema_version}
          {paper.meta.prompt_version ? `, summary prompt ${paper.meta.prompt_version}` : ''}
        </p>
        <p className="max-w-prose text-small text-content-secondary">{REPORT_COPY.limits}</p>
      </div>

      {progress}
      {failed}

      <ReportBanners
        document={paper}
        stale={stale}
        unfinished={unfinishedParts(detail, paper)}
        busy={writing}
        onRegenerate={() => start({ force: true })}
        onRetryNarrative={() => start({ force: true })}
      />

      <div className="gap-8 lg:grid lg:grid-cols-[16rem_minmax(0,1fr)]">
        <div className="mb-6 lg:mb-0">
          <ReportToc entries={entries} current={current} onSelect={select} />
        </div>

        <article
          id="report-document"
          tabIndex={-1}
          aria-labelledby="report-title"
          aria-busy={writing || undefined}
          className="min-w-0 max-w-prose space-y-12"
        >
          {paper.subtitle !== paper.meta.idea_title ? <p className="text-body text-content-secondary">{paper.subtitle}</p> : null}
          {cover ? (
            <div className="space-y-4">
              <ReportBlocks blocks={cover.blocks} onCite={(number) => focusTarget(sourceAnchor(number))} />
            </div>
          ) : null}
          {sections
            .filter((section) => section.id !== COVER)
            .map((section) => (
              <section
                key={section.id}
                id={sectionAnchor(section.id)}
                tabIndex={-1}
                aria-labelledby={`${sectionAnchor(section.id)}-title`}
                data-report-section
                className="scroll-mt-6 space-y-4"
              >
                <h2 id={`${sectionAnchor(section.id)}-title`}>{section.title}</h2>
                <ReportBlocks blocks={section.blocks} onCite={(number) => focusTarget(sourceAnchor(number))} />
                {section.id === SOURCES ? (
                  <ReportBibliography entries={paper.bibliography ?? []} sectionTitles={titles} />
                ) : null}
              </section>
            ))}
        </article>
      </div>

      <ConfirmDialog
        open={confirming}
        title={REPORT_COPY.confirmTitle}
        confirmLabel={REPORT_COPY.regenerate}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          start({ force: true });
        }}
      >
        <p>{REPORT_COPY.confirmBody}</p>
      </ConfirmDialog>
    </div>
  );
}
