import { BasisChip } from '@/components/BasisChip';
import { Citations } from '@/components/CitationChip';
import type { ChatMessage, ChatParagraph } from '@/features/advisor/useChat';
import { resolveStrategySources, type SourceRecord } from '@/lib/results';

export type AdvisorSection = NonNullable<ChatParagraph['sections']>[number];

export const SECTION_LABELS: Record<AdvisorSection, string> = {
  market: 'Market',
  competitors: 'Competitors',
  swot: 'SWOT',
  risks: 'Risks',
  mvp: 'MVP plan',
  gtm: 'Go-to-market',
  evidence: 'Sources',
  general: 'General',
};

export function fromLine(sections: AdvisorSection[] | undefined): string | null {
  const names = (sections ?? []).filter((section) => section !== 'general').map((section) => SECTION_LABELS[section]);
  return names.length > 0 ? `From: ${names.join(', ')}` : null;
}

export interface ChatMessageItemProps {
  message: ChatMessage;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
  pending?: boolean;
}

export function ChatMessageItem({ message, sources, onOpenSource, pending = false }: ChatMessageItemProps) {
  if (message.role === 'user') {
    return (
      <li id={`chat-${message.id}`} className="flex justify-end" aria-busy={pending || undefined}>
        <div className="min-w-0 max-w-[85%] space-y-1 rounded-panel border border-line bg-raised px-4 py-3">
          <p className="text-micro text-content-muted">You</p>
          <p className="whitespace-pre-wrap break-words text-body text-content">{message.text ?? ''}</p>
        </div>
      </li>
    );
  }
  return (
    <li id={`chat-${message.id}`} className="min-w-0 space-y-4">
      <p className="text-micro text-content-muted">Advisor</p>
      {(message.paragraphs ?? []).map((paragraph, index) => {
        const from = fromLine(paragraph.sections);
        return (
          <div key={index} className="space-y-2">
            <p className="whitespace-pre-wrap break-words text-body text-content-secondary">
              {paragraph.text}{' '}
              <Citations sources={resolveStrategySources(sources, paragraph.sources)} onOpen={onOpenSource} />
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <BasisChip basis={paragraph.basis} />
              {from ? <span className="text-small text-content-muted">{from}</span> : null}
            </div>
          </div>
        );
      })}
    </li>
  );
}
