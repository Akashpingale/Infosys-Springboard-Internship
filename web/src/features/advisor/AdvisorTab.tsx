import { MessageSquare, SendHorizontal } from 'lucide-react';
import * as React from 'react';
import { Link } from 'react-router-dom';

import { ApiError } from '@/api/client';
import { useMeta } from '@/api/queries';
import { Alert, type AlertTone } from '@/components/Alert';
import { Chip } from '@/components/Chip';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Field, TextArea } from '@/components/Field';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ChatMessageItem, SECTION_LABELS, type AdvisorSection } from '@/features/advisor/ChatMessage';
import { isCancelled, useChatThread, useClearChat, useSendChat, type ChatMessage } from '@/features/advisor/useChat';
import { isActive, useGenerateStrategy, type RunDetail } from '@/features/run/useRun';
import { COPY as STRATEGY_COPY, canBuildStrategy, errorText } from '@/features/strategy/StrategyStates';
import { count } from '@/lib/format';
import type { PipelineResult, SourceRecord } from '@/lib/results';

export const ADVISOR_COPY = {
  title: 'Ask about this validation',
  intro: "Answers use only this validation's results. They can be wrong. Check important points against the sources.",
  uses: 'The Advisor can use:',
  empty: 'Ask about your market, competitors, risks, MVP or launch plan.',
  ask: 'Ask the advisor about this',
  label: 'Your question',
  helper: 'Enter sends. Shift+Enter starts a new line.',
  send: 'Send',
  thinking: 'Thinking',
  answering: 'Advisor is answering',
  replied: 'Advisor replied.',
  full: 'This conversation is full.',
  clear: 'Clear conversation',
  clearTitle: 'Clear this conversation?',
  clearConfirm: 'Clear it',
  clearBody: 'Every question and answer in this conversation will be removed. The validation results stay as they are.',
  clearFailed: 'The conversation was not cleared',
  busy: 'The AI service is busy. Try again in a minute.',
  rephrase: 'Try rephrasing the question.',
  offline: 'Lost connection. Your question is still here.',
  cancelled: 'Cancelled. Your question is still here.',
  writeFirst: 'Write a question first.',
  missingStrategy: 'Strategy has not been generated yet.',
  strategyCost: 'This uses 3 AI requests.',
  strategyNotStarted: 'The strategy was not started',
  unavailable: 'Questions open once the validation has finished.',
  backToOverview: 'Open the overview',
} as const;

export const ADVISOR_QUESTIONS = {
  market: 'What does the market analysis say about my priority segment?',
  competitors: 'Which competitor is closest to my idea, and why?',
  swot: 'Which strengths and weaknesses in my SWOT matter most?',
  risks: 'Which risk should I deal with first, and how could I reduce it?',
  mvp: 'Why are these features in the first release?',
  gtm: 'Why is this the channel to start with, and what is the first experiment?',
} as const;

export const LIMIT_WARNING_AT = 5;
const MAX_ROWS = 6;
const DEFAULT_MAX_CHARS = 1000;
const STRATEGY_SECTIONS: AdvisorSection[] = ['swot', 'risks', 'mvp', 'gtm'];
const AVAILABLE_STATUSES = ['complete', 'partial'];
const PENDING_ID = 'pending-question';
const LLM_NOT_CONFIGURED = 'llm_not_configured';

export function advisorAvailable(run: RunDetail, result: PipelineResult | null): boolean {
  return run.state === 'done' && result !== null && AVAILABLE_STATUSES.includes(result.status);
}

export function questionsLeft(remaining: number): string | null {
  return remaining > 0 && remaining <= LIMIT_WARNING_AT ? `${count(remaining, 'question')} left` : null;
}

export function sendProblem(error: unknown): { tone: AlertTone; text: string } {
  if (isCancelled(error)) {
    return { tone: 'info', text: ADVISOR_COPY.cancelled };
  }
  if (!(error instanceof ApiError) || error.isOffline) {
    return { tone: 'error', text: ADVISOR_COPY.offline };
  }
  if (error.status >= 500 && error.code !== LLM_NOT_CONFIGURED) {
    const rephrase = error.message.includes(ADVISOR_COPY.rephrase);
    return { tone: 'error', text: rephrase ? `${ADVISOR_COPY.busy} ${ADVISOR_COPY.rephrase}` : ADVISOR_COPY.busy };
  }
  if (error.code === 'chat_busy' || error.code === 'chat_cooldown') {
    return { tone: 'warning', text: error.message };
  }
  return { tone: 'error', text: error.message };
}

export function AskAdvisorButton({ onClick, describedBy }: { onClick: () => void; describedBy?: string }) {
  return (
    <div data-print-hide>
      <Button variant="text" size="small" className="px-0" aria-describedby={describedBy} onClick={onClick}>
        <MessageSquare aria-hidden="true" />
        {ADVISOR_COPY.ask}
      </Button>
    </div>
  );
}

type Problem = { kind: 'field'; text: string } | { kind: 'send'; error: unknown } | { kind: 'clear'; error: unknown };

export interface AdvisorTabProps {
  run: RunDetail;
  result: PipelineResult | null;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
  draft?: string;
  onDraftChange?: (draft: string) => void;
  focusComposer?: boolean;
  onComposerFocused?: () => void;
  onShowOverview?: () => void;
}

export function AdvisorTab({
  run,
  result,
  sources,
  onOpenSource,
  draft,
  onDraftChange,
  focusComposer = false,
  onComposerFocused,
  onShowOverview,
}: AdvisorTabProps) {
  const available = advisorAvailable(run, result);
  const thread = useChatThread(run.id, available);
  const send = useSendChat(run.id);
  const clear = useClearChat(run.id);
  const generate = useGenerateStrategy(run.id);
  const meta = useMeta();
  const [ownDraft, setOwnDraft] = React.useState('');
  const text = draft ?? ownDraft;
  const setText = onDraftChange ?? setOwnDraft;
  const latest = React.useRef(text);
  latest.current = text;
  const [asked, setAsked] = React.useState<string | null>(null);
  const [problem, setProblem] = React.useState<Problem | null>(null);
  const [announcement, setAnnouncement] = React.useState('');
  const [confirming, setConfirming] = React.useState(false);
  const composer = React.useRef<HTMLTextAreaElement>(null);
  const composing = React.useRef(false);

  const settled = thread.isSuccess || thread.isError;
  React.useEffect(() => {
    if (!focusComposer || !settled) {
      return;
    }
    const box = composer.current;
    if (box) {
      box.focus();
      box.setSelectionRange(box.value.length, box.value.length);
    }
    onComposerFocused?.();
  }, [focusComposer, settled, onComposerFocused]);

  React.useLayoutEffect(() => {
    const box = composer.current;
    if (!box) {
      return;
    }
    box.style.height = 'auto';
    const style = window.getComputedStyle(box);
    const line = Number.parseFloat(style.lineHeight);
    const height = box.scrollHeight;
    if (!height || !Number.isFinite(line)) {
      box.style.height = '';
      return;
    }
    const padding = Number.parseFloat(style.paddingTop) + Number.parseFloat(style.paddingBottom);
    const border = Number.parseFloat(style.borderTopWidth) + Number.parseFloat(style.borderBottomWidth);
    box.style.height = `${Math.min(height, line * MAX_ROWS + padding) + border}px`;
  }, [text, settled]);

  const replyId = send.data?.message.id;
  React.useEffect(() => {
    if (!replyId) {
      return;
    }
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    document.getElementById(`chat-${replyId}`)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'nearest' });
  }, [replyId]);

  const unavailableError =
    thread.error instanceof ApiError && thread.error.code === 'chat_unavailable' ? thread.error : null;

  if (!available || unavailableError) {
    const reason = unavailableError
      ? unavailableError.message
      : isActive(run.state)
        ? ADVISOR_COPY.unavailable
        : `${ADVISOR_COPY.unavailable} This one ${run.state === 'cancelled' ? 'was cancelled' : 'did not finish'}.`;
    return (
      <section aria-labelledby="advisor-heading" className="space-y-4 rounded-panel border border-line bg-surface p-6">
        <MessageSquare className="size-5 text-content-muted" aria-hidden="true" />
        <h2 id="advisor-heading">{ADVISOR_COPY.title}</h2>
        <p className="max-w-prose text-body text-content-secondary">{reason}</p>
        <Link
          to={`/runs/${encodeURIComponent(run.id)}`}
          onClick={(event) => {
            if (onShowOverview) {
              event.preventDefault();
              onShowOverview();
            }
          }}
          className="inline-flex min-h-[44px] items-center text-body text-primary underline-offset-4 hover:underline sm:min-h-0"
        >
          {ADVISOR_COPY.backToOverview}
        </Link>
      </section>
    );
  }

  const data = thread.data;
  const messages = data?.messages ?? [];
  const sections = data?.available_sections ?? [];
  const remaining = data?.remaining_turns ?? 0;
  const maxChars = data?.limits.max_message_chars ?? meta.data?.chat?.max_message_chars ?? DEFAULT_MAX_CHARS;
  const pending = send.isPending;
  const reply = send.isSuccess ? send.data.message : null;
  const stored = reply ? messages.some((message) => message.id === reply.id) : false;
  const extra: ChatMessage[] = [];
  if (asked && (pending || (reply && !stored))) {
    extra.push({
      id: PENDING_ID,
      role: 'user',
      created_at: '',
      text: asked,
      paragraphs: [],
      follow_ups: [],
      status: 'ok',
      used_sections: [],
    });
  }
  if (reply && !stored) {
    extra.push(reply);
  }
  const shown = [...messages, ...extra];
  const last = shown[shown.length - 1];
  const followUps = !pending && last?.role === 'assistant' ? (last.follow_ups ?? []) : [];
  const strategyMissing = thread.isSuccess && !sections.some((section) => STRATEGY_SECTIONS.includes(section));
  const canGenerate = Boolean(meta.data?.strategy?.available) && result !== null && canBuildStrategy(result);
  const full = thread.isSuccess && remaining === 0;
  const fieldError = problem?.kind === 'field' ? problem.text : undefined;
  const shownProblem: { tone: AlertTone; text: string; title?: string } | null =
    problem?.kind === 'send'
      ? sendProblem(problem.error)
      : problem?.kind === 'clear'
        ? { tone: 'error', text: errorText(problem.error), title: ADVISOR_COPY.clearFailed }
        : null;

  function ask(question: string, fromComposer: boolean): void {
    const value = question.trim();
    if (!value) {
      setProblem({ kind: 'field', text: ADVISOR_COPY.writeFirst });
      return;
    }
    if (value.length > maxChars) {
      setProblem({ kind: 'field', text: `Write a question of up to ${maxChars} characters.` });
      return;
    }
    if (send.isPending) {
      return;
    }
    setProblem(null);
    setAsked(value);
    setAnnouncement(ADVISOR_COPY.answering);
    if (fromComposer) {
      setText('');
    }
    composer.current?.focus();
    send.mutate(value, {
      onSuccess: () => setAnnouncement(ADVISOR_COPY.replied),
      onError: (error) => {
        setAnnouncement('');
        setAsked(null);
        if (!latest.current.trim()) {
          setText(value);
        }
        setProblem({ kind: 'send', error });
        if (error instanceof ApiError && error.code === 'chat_limit_reached') {
          void thread.refetch();
        }
      },
    });
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }
    if (composing.current || event.nativeEvent.isComposing || event.keyCode === 229) {
      return;
    }
    event.preventDefault();
    ask(text, true);
  }

  return (
    <div className="space-y-6">
      <section aria-labelledby="advisor-heading" className="space-y-3 rounded-panel border border-line bg-surface p-6">
        <h2 id="advisor-heading">{ADVISOR_COPY.title}</h2>
        <p className="max-w-prose text-small text-content-muted">{ADVISOR_COPY.intro}</p>
        {sections.length > 0 ? (
          <div className="space-y-2">
            <p id="advisor-uses" className="text-small text-content-secondary">
              {ADVISOR_COPY.uses}
            </p>
            <ul aria-labelledby="advisor-uses" className="flex flex-wrap gap-2">
              {sections.map((section) => (
                <li key={section}>
                  <Chip>{SECTION_LABELS[section]}</Chip>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {strategyMissing ? (
          <div data-print-hide className="space-y-3 border-t border-line pt-4">
            <p className="max-w-prose text-body text-content">{ADVISOR_COPY.missingStrategy}</p>
            {canGenerate ? (
              <>
                <p className="max-w-prose text-small text-content-muted">{ADVISOR_COPY.strategyCost}</p>
                <Button
                  variant="secondary"
                  size="small"
                  loading={generate.isPending}
                  onClick={() => generate.mutate({ mode: 'missing' })}
                >
                  {STRATEGY_COPY.generate}
                </Button>
              </>
            ) : null}
            {generate.isError ? (
              <Alert tone="error" title={ADVISOR_COPY.strategyNotStarted}>
                {errorText(generate.error)}
              </Alert>
            ) : null}
          </div>
        ) : null}
      </section>

      {thread.isPending ? (
        <div aria-busy="true" className="space-y-3">
          {[0, 1].map((row) => (
            <Skeleton key={row} className="h-16 w-full" />
          ))}
        </div>
      ) : thread.isError ? (
        <Alert
          tone="error"
          title="The conversation could not be loaded"
          action={
            <Button variant="secondary" size="small" onClick={() => void thread.refetch()}>
              Try again
            </Button>
          }
        >
          {errorText(thread.error)}
        </Alert>
      ) : (
        <div className="space-y-6">
          {shown.length === 0 ? (
            <div className="space-y-4">
              <p className="max-w-prose text-body text-content-secondary">{ADVISOR_COPY.empty}</p>
              {(data?.suggestions ?? []).length > 0 ? (
                <ul aria-label="Suggested questions" className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                  {(data?.suggestions ?? []).map((suggestion) => (
                    <li key={suggestion}>
                      <Button
                        variant="secondary"
                        size="small"
                        className="h-auto whitespace-normal py-2 text-left"
                        disabled={pending || full}
                        onClick={() => ask(suggestion, false)}
                      >
                        {suggestion}
                      </Button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <>
              {!full ? (
                <div data-print-hide className="flex justify-end">
                  <Button
                    variant="text"
                    size="small"
                    disabled={pending}
                    onClick={() => {
                      clear.reset();
                      setConfirming(true);
                    }}
                  >
                    {ADVISOR_COPY.clear}
                  </Button>
                </div>
              ) : null}
              <ol aria-label="Conversation" className="space-y-6">
                {shown.map((message) => (
                  <ChatMessageItem
                    key={message.id}
                    message={message}
                    sources={sources}
                    onOpenSource={onOpenSource}
                    pending={message.id === PENDING_ID && pending}
                  />
                ))}
              </ol>
            </>
          )}

          {pending ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-panel border border-line bg-surface px-4 py-3">
              <span className="inline-flex items-center gap-2 text-body text-content-secondary">
                <MessageSquare className="size-4 text-content-muted" aria-hidden="true" />
                {ADVISOR_COPY.thinking}
              </span>
              <Button variant="secondary" size="small" onClick={() => send.cancel()}>
                Cancel
              </Button>
            </div>
          ) : null}

          {followUps.length > 0 && !full ? (
            <ul aria-label="Follow-up questions" className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {followUps.map((question) => (
                <li key={question}>
                  <Button
                    variant="secondary"
                    size="small"
                    className="h-auto whitespace-normal rounded-pill py-2 text-left"
                    onClick={() => ask(question, false)}
                  >
                    {question}
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}

      {shownProblem ? (
        <Alert tone={shownProblem.tone} {...(shownProblem.title ? { title: shownProblem.title } : {})}>
          {shownProblem.text}
        </Alert>
      ) : null}

      {full ? (
        <div data-print-hide className="space-y-3 rounded-panel border border-line bg-surface p-4">
          <p className="text-body text-content">{ADVISOR_COPY.full}</p>
          <Button
            variant="secondary"
            onClick={() => {
              clear.reset();
              setConfirming(true);
            }}
          >
            {ADVISOR_COPY.clear}
          </Button>
        </div>
      ) : thread.isSuccess ? (
        <form
          noValidate
          data-print-hide
          className="space-y-3 rounded-panel border border-line bg-surface p-4"
          onSubmit={(event) => {
            event.preventDefault();
            ask(text, true);
          }}
        >
          <Field
            id="advisor-question"
            label={ADVISOR_COPY.label}
            helper={ADVISOR_COPY.helper}
            error={fieldError}
            counter={{ value: text.length, max: maxChars }}
          >
            {(control) => (
              <TextArea
                {...control}
                ref={composer}
                rows={2}
                value={text}
                readOnly={pending}
                className="resize-none overflow-y-auto"
                onChange={(event) => {
                  setText(event.target.value);
                  if (problem?.kind === 'field') {
                    setProblem(null);
                  }
                }}
                onKeyDown={onKeyDown}
                onCompositionStart={() => {
                  composing.current = true;
                }}
                onCompositionEnd={() => {
                  composing.current = false;
                }}
              />
            )}
          </Field>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-small text-content-muted">{questionsLeft(remaining)}</span>
            <Button type="submit" disabled={pending}>
              <SendHorizontal aria-hidden="true" />
              {ADVISOR_COPY.send}
            </Button>
          </div>
        </form>
      ) : null}

      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      <ConfirmDialog
        open={confirming}
        title={ADVISOR_COPY.clearTitle}
        confirmLabel={ADVISOR_COPY.clearConfirm}
        busy={clear.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          clear.mutate(undefined, {
            onSuccess: () => {
              setConfirming(false);
              send.reset();
              setAsked(null);
              setAnnouncement('');
              setProblem(null);
            },
            onError: (error) => {
              setConfirming(false);
              setProblem({ kind: 'clear', error });
            },
          })
        }
      >
        <p>{ADVISOR_COPY.clearBody}</p>
      </ConfirmDialog>
    </div>
  );
}
