/**
 * A labelled claim, and text that may name evidence ids (KIRO_UI_UPGRADE_SPEC.md Sections 6.2 and
 * 8.6).
 *
 * Every claim shows its basis as a chip and, where it cites sources, the numbered citation chips.
 * The claim text itself is shown exactly as the agents left it.
 *
 * Some free text the model wrote, such as a data-quality note, names evidence ids directly
 * ("sources S2 and S3"). Those ids are replaced by the same citation chips, so the reader never sees
 * an internal id and can open the source. The words around them are not changed.
 */

import { BasisChip, type Basis } from '@/components/BasisChip';
import { CitationChip, Citations } from '@/components/CitationChip';
import { cn } from '@/lib/cn';
import { type AnalysisKey, type SourceRecord, resolveSources, sourceKey, splitEvidenceIds } from '@/lib/results';

export interface LabelledItem {
  text: string;
  basis: Basis;
  source_ids?: string[];
}

export interface ClaimItemProps {
  item: LabelledItem;
  analysis: AnalysisKey;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
  className?: string;
}

export function ClaimItem({ item, analysis, sources, onOpenSource, className }: ClaimItemProps) {
  return (
    <li data-claim="" className={cn('space-y-2', className)}>
      <p className="max-w-prose text-body text-content-secondary">
        {item.text}{' '}
        <Citations sources={resolveSources(sources, analysis, item.source_ids)} onOpen={onOpenSource} />
      </p>
      <BasisChip basis={item.basis} />
    </li>
  );
}

export interface ClaimListProps {
  items: LabelledItem[];
  analysis: AnalysisKey;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
  /** Section 6.8: what to say when the list is empty. */
  empty: string;
  className?: string;
}

export function ClaimList({ items, analysis, sources, onOpenSource, empty, className }: ClaimListProps) {
  if (items.length === 0) {
    return <p className="max-w-prose text-small text-content-muted">{empty}</p>;
  }
  return (
    <ul className={cn('space-y-4', className)}>
      {items.map((item, index) => (
        <ClaimItem
          key={`${index}-${item.text.slice(0, 24)}`}
          item={item}
          analysis={analysis}
          sources={sources}
          onOpenSource={onOpenSource}
        />
      ))}
    </ul>
  );
}

export interface TextWithCitationsProps {
  text: string;
  analysis: AnalysisKey;
  sources: Map<string, SourceRecord>;
  onOpenSource: (key: string) => void;
}

/**
 * Free text with any evidence id it names shown as a citation chip. An id the result does not list
 * is left as it was written, rather than being dropped or guessed at.
 */
export function TextWithCitations({ text, analysis, sources, onOpenSource }: TextWithCitationsProps) {
  return (
    <>
      {splitEvidenceIds(text).map((part, index) => {
        if (typeof part === 'string') {
          return <span key={index}>{part}</span>;
        }
        const record = sources.get(sourceKey(analysis, part.id));
        return record ? (
          <CitationChip key={index} source={record} onOpen={onOpenSource} />
        ) : (
          <span key={index}>{part.id}</span>
        );
      })}
    </>
  );
}
