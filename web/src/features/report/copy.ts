export const REPORT_COPY = {
  generate: 'Generate report',
  generatingButton: 'Generating',
  view: 'View report',
  update: 'Update report',
  generating: 'Writing the report. This takes up to a minute.',
  stale: 'This report was made before the latest changes to this validation.',
  narrativeFailed: 'The written summary could not be generated. Everything else is complete.',
  fontsMissing: 'PDF is not available because the report fonts are not installed. Markdown and JSON are available.',
  notGenerated: 'No report yet. Generate one to get a single document with every part of this validation.',
  limits: 'Interpretations are labelled. They are not predictions.',
  partial: 'Some parts of this validation did not finish: {list}.',
  notFinished: 'A report can be made once the validation has finished with results.',
  regenerate: 'Regenerate',
  tryAgain: 'Try again',
  back: 'Back to results',
  cancel: 'Cancel',
  download: 'Download',
  engineSummary: 'The search engine wrote this summary of its results. It is not a page you can open.',
  scrollHint: 'Scroll sideways to see every column.',
  confirmTitle: 'Replace the written summary?',
  confirmBody:
    'Regenerating writes a new report and a new summary with the AI service. The current summary will be replaced.',
} as const;

export function partialLine(names: string[]): string {
  return REPORT_COPY.partial.replace('{list}', names.join(', '));
}
