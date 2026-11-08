/**
 * The design page (KIRO_UI_UPGRADE_SPEC.md Prompt D): every token and base component on one
 * screen, so a change to the design system is visible at once. Development only, left out of a
 * production build by the router.
 */

import { Rocket } from 'lucide-react';

import { BasisChip, type Basis } from '@/components/BasisChip';
import { Chip } from '@/components/Chip';
import { EmptyState } from '@/components/EmptyState';
import { Field, TextArea, TextInput } from '@/components/Field';
import { MetricTile } from '@/components/MetricTile';
import { StatusChip, type StatusKind } from '@/components/StatusChip';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/cn';
import { MISSING } from '@/lib/format';

/*
 * Every class below is written out in full. Tailwind finds classes by scanning this file as text,
 * so a built-up name such as `bg-${token}` would never be generated and the swatch would show
 * nothing. This page caught exactly that.
 */
const SURFACES = [
  { name: 'canvas', className: 'bg-canvas' },
  { name: 'surface', className: 'bg-surface' },
  { name: 'raised', className: 'bg-raised' },
] as const;
const LINES = [
  { name: 'line', className: 'border-line' },
  { name: 'line-strong', className: 'border-line-strong' },
] as const;
const TEXTS = [
  { name: 'text-content', className: 'text-content' },
  { name: 'text-content-secondary', className: 'text-content-secondary' },
  { name: 'text-content-muted', className: 'text-content-muted' },
] as const;
const STATUSES: StatusKind[] = ['complete', 'partial', 'failed', 'running', 'queued', 'cancelled'];
const BASES: Basis[] = ['sourced', 'ai_interpretation', 'user_provided', 'assumption'];
const TYPE_SCALE = [
  { className: 'font-condensed text-display', label: 'Result title, 36 / 40' },
  { className: 'font-condensed text-h1', label: 'Page title, 28 / 34' },
  { className: 'font-condensed text-h2', label: 'Section title, 20 / 28' },
  { className: 'text-h3', label: 'Subsection, 16 / 24' },
  { className: 'text-body', label: 'Body, 15 / 24' },
  { className: 'text-small', label: 'Small, 13 / 20' },
  { className: 'text-micro', label: 'Micro, 12 / 16' },
] as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4 border-t border-line pt-8">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function DesignPage() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1>Design system</h1>
        <p className="max-w-prose text-body text-content-secondary">
          Every token and base component, on one page. Development only.
        </p>
      </div>

      <Section title="Surfaces and lines">
        <div className="flex flex-wrap gap-4">
          {SURFACES.map(({ name, className }) => (
            <div key={name} className="space-y-2">
              <div className={cn('size-20 rounded-panel border border-line', className)} />
              <p className="font-mono text-micro text-content-muted">{name}</p>
            </div>
          ))}
          {LINES.map(({ name, className }) => (
            <div key={name} className="space-y-2">
              <div className={cn('size-20 rounded-panel border-2 bg-surface', className)} />
              <p className="font-mono text-micro text-content-muted">{name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Text">
        <div className="space-y-2">
          {TEXTS.map(({ name, className }) => (
            <p key={name} className={cn('text-body', className)}>
              The quick brown fox jumps over the lazy dog.{' '}
              <span className="font-mono text-micro text-content-muted">{name}</span>
            </p>
          ))}
        </div>
      </Section>

      <Section title="Type scale">
        <div className="space-y-3">
          {TYPE_SCALE.map(({ className, label }) => (
            <div key={label} className="flex flex-wrap items-baseline gap-4">
              <span className={className}>Sentence case, never all caps</span>
              <span className="font-mono text-micro text-content-muted">{label}</span>
            </div>
          ))}
          <p className="font-mono text-small text-content">https://example.com/source — IBM Plex Mono</p>
          <p className="tabular text-kpi font-condensed">1,234.5</p>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Review my idea</Button>
          <Button variant="secondary">Clear</Button>
          <Button variant="text">Show details</Button>
          <Button variant="danger">Delete</Button>
          <Button loading>Validating</Button>
          <Button disabled>Disabled</Button>
          <Button size="small" variant="secondary">
            Small
          </Button>
          <Button size="icon" aria-label="Start a validation">
            <Rocket aria-hidden="true" />
          </Button>
        </div>
      </Section>

      <Section title="Status chips">
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((kind) => (
            <StatusChip key={kind} kind={kind} />
          ))}
        </div>
      </Section>

      <Section title="Basis chips">
        <div className="flex flex-wrap gap-2">
          {BASES.map((basis) => (
            <BasisChip key={basis} basis={basis} />
          ))}
        </div>
        <p className="max-w-prose text-small text-content-muted">
          The icon and the word carry the meaning; the colour only reinforces it.
        </p>
      </Section>

      <Section title="Chips">
        <div className="flex flex-wrap gap-2">
          <Chip>Small farmers</Chip>
          <Chip onRemove={() => undefined} removeLabel="Farming cooperatives">
            Farming cooperatives
          </Chip>
        </div>
      </Section>

      <Section title="Fields">
        <div className="max-w-form space-y-6">
          <Field
            id="design-idea"
            label="Your idea"
            required
            helper="30 to 2000 characters, at least 3 words."
            counter={{ value: 312, max: 2000 }}
          >
            {(control) => <TextArea {...control} placeholder="A mobile app that detects crop diseases from a leaf photo." />}
          </Field>
          <Field id="design-customers" label="Target customers" required error="Enter at least one target customer.">
            {(control) => <TextInput {...control} placeholder="Small farmers in Maharashtra" />}
          </Field>
        </div>
      </Section>

      <Section title="Metric tiles">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricTile label="Evidence strength" value="Moderate" detail="Sourced share, breadth and level." />
          <MetricTile
            label="Market size (TAM)"
            missing={MISSING.marketSize}
            status={{ kind: 'unavailable' }}
            detail="No source confirmed a figure for this idea's own market."
          />
          <MetricTile label="Competitors found" value="6" detail="3 direct, 2 indirect and 1 emerging." />
          <MetricTile label="Priority segment" value="Small farmers" detail="They feel the crop losses most directly." />
        </div>
      </Section>

      <Section title="Empty state and skeleton">
        <div className="grid gap-4 lg:grid-cols-2">
          <EmptyState message="No saved validations yet. Run one to see it here." />
          <div className="space-y-3 rounded-panel border border-line bg-surface p-4">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>
      </Section>
    </div>
  );
}
