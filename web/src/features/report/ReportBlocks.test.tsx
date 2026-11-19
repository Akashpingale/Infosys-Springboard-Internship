import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

import { REPORT_COPY } from '@/features/report/copy';
import { ReportBibliography, webAddress } from '@/features/report/ReportBibliography';
import { CALLOUT, ReportBlockView, ReportBlocks, SOURCES_COLUMN } from '@/features/report/ReportBlocks';
import type { BibEntry, ReportBlock } from '@/features/report/useReport';

const HOSTILE = '<b>bold</b> & <script>alert(1)</script> | `tick`';

function block(value: ReportBlock, onCite = vi.fn()) {
  render(<ReportBlockView block={value} onCite={onCite} />);
  return onCite;
}

describe('Report blocks', () => {
  it('shows a paragraph with its basis label and citation numbers', async () => {
    const onCite = block({ type: 'paragraph', text: 'Farmers lose crops.', basis: 'sourced', cites: [3, 5, 3], narrative: false });
    const user = userEvent.setup();

    expect(screen.getByText('Farmers lose crops.')).toBeInTheDocument();
    expect(screen.getByText('Sourced')).toBeInTheDocument();
    const links = screen.getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual(['Source [3]', 'Source [5]']);
    expect(links[1]).toHaveAttribute('href', '#report-source-5');

    await user.click(links[1]!);

    expect(onCite).toHaveBeenCalledWith(5);
  });

  it('shows a paragraph without a basis or citations as plain text', () => {
    block({ type: 'paragraph', text: 'Plain words.', basis: null, cites: [], narrative: false });

    expect(screen.getByText('Plain words.').tagName).toBe('P');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('shows bullets with their own labels', () => {
    block({
      type: 'bullets',
      narrative: true,
      items: [
        { text: 'First point', basis: 'ai_interpretation', cites: [1] },
        { text: 'Second point', basis: 'assumption', cites: [] },
        { text: 'Third point', basis: 'user_provided', cites: [] },
      ],
    });

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(within(items[0]!).getByText('AI interpretation')).toBeInTheDocument();
    expect(within(items[0]!).getByRole('link', { name: 'Source [1]' })).toBeInTheDocument();
    expect(within(items[1]!).getByText('Assumption')).toBeInTheDocument();
    expect(within(items[2]!).getByText('From your idea')).toBeInTheDocument();
  });

  it('shows a table with its caption, row headers, right-aligned numbers, sources and a scroll hint', () => {
    block({
      type: 'table',
      caption: 'Feature comparison',
      columns: ['Competitor', 'Users', 'Photo diagnosis'],
      rows: [
        ['Plantix', '10,000', '+ Evidence found'],
        ['LeafDoc', '2,500', '? Unclear'],
      ],
      col_align: ['left', 'right', 'left'],
      row_cites: [[4], []],
    });

    const table = screen.getByRole('table', { name: 'Feature comparison' });
    const headers = within(table).getAllByRole('columnheader').map((cell) => cell.textContent);
    expect(headers).toEqual(['Competitor', 'Users', 'Photo diagnosis', SOURCES_COLUMN]);
    const first = within(table).getByRole('rowheader', { name: 'Plantix' });
    expect(first.className).toContain('sticky');
    expect(within(table).getByText('10,000').className).toContain('text-right');
    expect(within(table).getByRole('link', { name: 'Source [4]' })).toBeInTheDocument();
    expect(screen.getByText(REPORT_COPY.scrollHint)).toBeInTheDocument();
    expect(table.parentElement).toHaveAttribute('tabindex', '0');
  });

  it('leaves the sources column out of a table that cites nothing', () => {
    block({ type: 'table', caption: 'Stage timings', columns: ['Stage', 'Seconds'], rows: [['Search', '18.2']], col_align: ['left', 'right'], row_cites: [] });

    expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Stage', 'Seconds']);
  });

  it.each(['note', 'caveat', 'warning'] as const)('shows a %s callout with its word, never colour alone', (kind) => {
    block({ type: 'callout', kind, text: 'Something to know.' });

    const note = screen.getByRole('note');
    expect(note).toHaveTextContent(`${CALLOUT[kind].word}: Something to know.`);
    expect(note.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });

  it('shows facts as a definition list', () => {
    block({ type: 'facts', pairs: [{ label: 'Run status', value: 'Complete' }, { label: 'Industry', value: 'AgriTech' }] });

    const terms = screen.getAllByRole('term').map((term) => term.textContent);
    const values = screen.getAllByRole('definition').map((value) => value.textContent);
    expect(terms).toEqual(['Run status', 'Industry']);
    expect(values).toEqual(['Complete', 'AgriTech']);
  });

  it('shows a subheading as a third-level heading', () => {
    block({ type: 'subheading', text: 'Market size' });

    expect(screen.getByRole('heading', { level: 3, name: 'Market size' })).toBeInTheDocument();
  });

  it('renders hostile text in every block type as text', () => {
    const blocks: ReportBlock[] = [
      { type: 'paragraph', text: HOSTILE, basis: null, cites: [], narrative: false },
      { type: 'bullets', items: [{ text: HOSTILE, basis: null, cites: [] }], narrative: false },
      { type: 'table', caption: HOSTILE, columns: [HOSTILE], rows: [[HOSTILE]], col_align: [], row_cites: [] },
      { type: 'callout', kind: 'warning', text: HOSTILE },
      { type: 'facts', pairs: [{ label: HOSTILE, value: HOSTILE }] },
      { type: 'subheading', text: HOSTILE },
    ];
    const { container } = render(<ReportBlocks blocks={blocks} onCite={() => undefined} />);

    expect(container.querySelector('b, script')).toBeNull();
    expect(container.textContent!.split(HOSTILE).length - 1).toBeGreaterThanOrEqual(8);
  });
});

describe('Report sources', () => {
  const ENTRIES: BibEntry[] = [
    { number: 1, title: 'Crop AI market report', url: 'https://reports.example/crop', domain: 'reports.example', analyses: ['market'], cited_in: ['market', 'next_steps'], has_page: true },
    { number: 2, title: 'Search engine summary (generated, not a page)', url: null, domain: '', analyses: ['market'], cited_in: ['market'], has_page: false },
    { number: 3, title: 'Odd link', url: 'ftp://files.example/x', domain: 'files.example', analyses: ['competitors'], cited_in: [], has_page: true },
  ];
  const TITLES = new Map([
    ['market', 'Market opportunity'],
    ['next_steps', 'Recommended next steps'],
  ]);

  it('numbers each source, links web pages in a new tab and says where each is cited', () => {
    render(<ReportBibliography entries={ENTRIES} sectionTitles={TITLES} />);

    const items = screen.getAllByRole('listitem');
    expect(items.map((item) => item.id)).toEqual(['report-source-1', 'report-source-2', 'report-source-3']);
    const link = within(items[0]!).getByRole('link');
    expect(link).toHaveAttribute('href', 'https://reports.example/crop');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(within(items[0]!).getByText('Cited in: Market opportunity, Recommended next steps.')).toBeInTheDocument();
  });

  it('explains that the search engine summary is not a page', () => {
    render(<ReportBibliography entries={ENTRIES} sectionTitles={TITLES} />);

    const summary = screen.getAllByRole('listitem')[1]!;
    expect(within(summary).getByText(REPORT_COPY.engineSummary)).toBeInTheDocument();
    expect(within(summary).queryByRole('link')).not.toBeInTheDocument();
  });

  it('shows an address that is not a web page as text, never as a link', () => {
    render(<ReportBibliography entries={ENTRIES} sectionTitles={TITLES} />);

    const odd = screen.getAllByRole('listitem')[2]!;
    expect(within(odd).getByText('ftp://files.example/x')).toBeInTheDocument();
    expect(within(odd).queryByRole('link')).not.toBeInTheDocument();
    expect(webAddress('javascript:alert(1)')).toBeNull();
    expect(webAddress('HTTPS://example.org')).toBe('HTTPS://example.org');
  });
});

describe('The report files', () => {
  it('render text only, so the raw-HTML guard has nothing to find in them', () => {
    const folder = join(process.cwd(), 'src', 'features', 'report');
    const files = readdirSync(folder).filter((name) => /\.tsx?$/.test(name) && !name.includes('.test.'));
    const forbidden = new RegExp(['dangerously', 'Set', 'Inner', 'HTML'].join(''));

    expect(files).toEqual(
      expect.arrayContaining(['ReportPage.tsx', 'ReportBlocks.tsx', 'ReportBibliography.tsx', 'ReportToc.tsx', 'DownloadMenu.tsx']),
    );
    for (const file of files) {
      expect(forbidden.test(readFileSync(join(folder, file), 'utf8')), file).toBe(false);
    }
  });
});
