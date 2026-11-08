/**
 * History (KIRO_UI_UPGRADE_SPEC.md Sections 7.5, 6.7 and 8.2).
 *
 * The saved validations, newest first, with the three things worth doing to one: open it, rename it
 * and delete it. Renaming happens in place, so the list never moves under the reader; deleting is
 * asked for first, because the backend removes the row and its result for good.
 *
 * A title is not checked for length here. The backend owns that limit (models/api.RunRename), and
 * its own message is shown if it refuses, so the limit is stated in exactly one place.
 */

import { Check, Pencil, Trash2, X } from 'lucide-react';
import * as React from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { useDeleteRun, useRenameRun } from '@/api/mutations';
import { useRuns, type RunSummary } from '@/api/queries';
import { Alert } from '@/components/Alert';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { EmptyState } from '@/components/EmptyState';
import { controlClassName } from '@/components/Field';
import { StatusChip, type StatusKind } from '@/components/StatusChip';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { MESSAGES, dateTime, duration } from '@/lib/format';
import { NARROW, useMediaQuery } from '@/lib/useMediaQuery';

interface RenameFieldProps {
  row: RunSummary;
  value: string;
  busy: boolean;
  onChange: (title: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

/**
 * Renaming in place, used by both the table and the cards.
 *
 * Enter saves and Escape abandons, which is what a reader who has just typed a title expects. The
 * length is not checked here: the backend owns that limit and its message is shown if it refuses.
 */
function RenameField({ row, value, busy, onChange, onSave, onCancel }: RenameFieldProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`rename-${row.id}`}>
        New title for {row.title}
      </label>
      <input
        id={`rename-${row.id}`}
        autoFocus
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            onSave();
          }
          if (event.key === 'Escape') {
            event.preventDefault();
            onCancel();
          }
        }}
        className={cn(controlClassName, 'min-h-[44px] w-full py-1 text-small sm:min-h-0 sm:w-56')}
      />
      <Button variant="secondary" size="small" onClick={onSave} loading={busy} disabled={!value.trim()}>
        <Check aria-hidden="true" />
        Save
      </Button>
      <Button variant="text" size="small" onClick={onCancel}>
        <X aria-hidden="true" />
        Cancel
      </Button>
    </div>
  );
}

/** The chip for a saved row: the result's status once it is done, otherwise the run's own state. */
export function summaryStatus(row: RunSummary): { kind: StatusKind; label?: string } {
  if (row.state === 'queued' || row.state === 'running' || row.state === 'cancelled') {
    return { kind: row.state };
  }
  if (row.state === 'done' && row.status) {
    return { kind: row.status };
  }
  return { kind: 'failed' };
}

export function HistoryPage() {
  const runs = useRuns();
  const rename = useRenameRun();
  const remove = useDeleteRun();

  const narrow = useMediaQuery(NARROW);
  const [editing, setEditing] = React.useState<{ id: string; title: string } | null>(null);
  const [confirming, setConfirming] = React.useState<RunSummary | null>(null);

  const failure = rename.isError ? rename.error : remove.isError ? remove.error : null;

  function save(): void {
    if (!editing || !editing.title.trim()) {
      return;
    }
    rename.mutate(
      { id: editing.id, title: editing.title.trim() },
      { onSuccess: () => setEditing(null) },
    );
  }

  function cancelRename(): void {
    setEditing(null);
    rename.reset();
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1>History</h1>
        <p className="max-w-prose text-body text-content-secondary">
          Every validation saved on this machine. Results stay in a local database until you delete
          them.
        </p>
      </div>

      {failure ? (
        <Alert tone="error" title="That did not work">
          {failure instanceof ApiError ? failure.message : MESSAGES.backendDown}
        </Alert>
      ) : null}

      {runs.isPending ? (
        <div className="space-y-3 rounded-panel border border-line bg-surface p-6" aria-busy="true">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-10 w-full" />
          ))}
        </div>
      ) : runs.isError ? (
        <Alert
          tone="error"
          title="Can't load the history"
          action={
            <Button variant="secondary" size="small" onClick={() => void runs.refetch()}>
              Try again
            </Button>
          }
        >
          {runs.error instanceof ApiError ? runs.error.message : MESSAGES.backendDown}
        </Alert>
      ) : (runs.data ?? []).length === 0 ? (
        <EmptyState
          message={MESSAGES.emptyHistory}
          action={
            <Button asChild variant="primary">
              <Link to="/">Start a new validation</Link>
            </Button>
          }
        />
      ) : narrow ? (
        /* At 390 px the six columns cannot be read, so each row becomes a card with its actions
           on a full-width row of their own (Prompt J). */
        <ul className="space-y-3">
          {(runs.data ?? []).map((row) => {
            const status = summaryStatus(row);
            return (
              <li key={row.id} className="space-y-3 rounded-panel border border-line bg-surface p-4">
                {editing?.id === row.id ? (
                  <RenameField
                    row={row}
                    value={editing.title}
                    busy={rename.isPending}
                    onChange={(title) => setEditing({ id: row.id, title })}
                    onSave={save}
                    onCancel={cancelRename}
                  />
                ) : (
                  <h2 className="text-h3 font-sans">
                    <Link
                      to={`/runs/${row.id}`}
                      className="flex min-h-[44px] items-center text-content underline-offset-2 hover:underline"
                    >
                      {row.title}
                    </Link>
                  </h2>
                )}

                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-micro">
                  <div className="col-span-2">
                    <dt className="text-content-muted">Industry</dt>
                    <dd className="text-content-secondary">{row.industry}</dd>
                  </div>
                  <div>
                    <dt className="text-content-muted">Status</dt>
                    <dd className="mt-1">
                      <StatusChip kind={status.kind} {...(status.label ? { label: status.label } : {})} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-content-muted">Took</dt>
                    <dd className="tabular text-content-secondary">{duration(row.duration_s)}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-content-muted">Started</dt>
                    <dd className="text-content-secondary">{dateTime(row.created_at)}</dd>
                  </div>
                </dl>

                {editing?.id === row.id ? null : (
                  <div className="grid grid-cols-3 gap-2 border-t border-line pt-3">
                    <Button asChild variant="secondary">
                      <Link to={`/runs/${row.id}`}>Open</Link>
                    </Button>
                    <Button
                      variant="secondary"
                      aria-label={`Rename ${row.title}`}
                      onClick={() => {
                        rename.reset();
                        setEditing({ id: row.id, title: row.title });
                      }}
                    >
                      Rename
                    </Button>
                    <Button
                      variant="secondary"
                      aria-label={`Delete ${row.title}`}
                      onClick={() => {
                        remove.reset();
                        setConfirming(row);
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="overflow-x-auto rounded-panel border border-line bg-surface">
          <table className="w-full min-w-[48rem] text-small">
            <caption className="sr-only">Saved validations, newest first.</caption>
            <thead>
              <tr className="border-b border-line text-content-secondary">
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Title
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Industry
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Status
                </th>
                <th scope="col" className="px-4 py-3 text-left font-medium">
                  Started
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium">
                  Took
                </th>
                <th scope="col" className="px-4 py-3 text-right font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {(runs.data ?? []).map((row) => {
                const status = summaryStatus(row);
                const open = editing?.id === row.id;
                return (
                  <tr key={row.id} className="border-b border-line last:border-0">
                    <th scope="row" className="max-w-[20rem] px-4 py-3 text-left font-normal">
                      {open ? (
                        <RenameField
                          row={row}
                          value={editing.title}
                          busy={rename.isPending}
                          onChange={(title) => setEditing({ id: row.id, title })}
                          onSave={save}
                          onCancel={cancelRename}
                        />
                      ) : (
                        <Link
                          to={`/runs/${row.id}`}
                          className="text-content underline-offset-2 hover:underline"
                        >
                          {row.title}
                        </Link>
                      )}
                    </th>
                    <td className="px-4 py-3 text-content-secondary">{row.industry}</td>
                    <td className="px-4 py-3">
                      <StatusChip kind={status.kind} {...(status.label ? { label: status.label } : {})} />
                    </td>
                    <td className="px-4 py-3 text-content-secondary">{dateTime(row.created_at)}</td>
                    <td className="tabular px-4 py-3 text-right text-content-secondary">
                      {duration(row.duration_s)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <Button asChild variant="secondary" size="small">
                          <Link to={`/runs/${row.id}`}>Open</Link>
                        </Button>
                        {open ? null : (
                          <>
                            <Button
                              variant="secondary"
                              size="small"
                              aria-label={`Rename ${row.title}`}
                              onClick={() => {
                                rename.reset();
                                setEditing({ id: row.id, title: row.title });
                              }}
                            >
                              <Pencil aria-hidden="true" />
                              Rename
                            </Button>
                            <Button
                              variant="secondary"
                              size="small"
                              aria-label={`Delete ${row.title}`}
                              onClick={() => {
                                remove.reset();
                                setConfirming(row);
                              }}
                            >
                              <Trash2 aria-hidden="true" />
                              Delete
                            </Button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={confirming !== null}
        title="Delete this validation?"
        confirmLabel="Delete it"
        busy={remove.isPending}
        onCancel={() => setConfirming(null)}
        onConfirm={() => {
          if (!confirming) {
            return;
          }
          remove.mutate(confirming.id, { onSuccess: () => setConfirming(null) });
        }}
      >
        <p>
          <span className="text-content">{confirming?.title}</span> and its result will be removed
          from this machine. This cannot be undone.
        </p>
      </ConfirmDialog>
    </div>
  );
}
