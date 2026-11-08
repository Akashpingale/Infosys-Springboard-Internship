/**
 * Formatting and wording helpers (KIRO_UI_UPGRADE_SPEC.md Sections 6.7 and 6.8).
 *
 * Nothing here invents a value: a missing value gets the specified wording, never a zero or a dash
 * that could be read as data.
 */

/** Section 6.8: what to show when the sources gave nothing. */
export const MISSING = {
  price: 'Not found in the sources',
  weaknesses: 'None found in the sources',
  marketSize: 'Unavailable',
  website: '\u2014',
  websiteHint: 'No verified website in the sources',
  none: 'None found in the evidence.',
} as const;

/** Section 6.7: the messages the interface reuses, so wording cannot drift. */
export const MESSAGES = {
  backendDown: 'Can\u2019t reach the server. Start it with `python app.py`, then try again.',
  partial: 'Some parts could not be completed. What finished is shown below.',
  failed: 'We couldn\u2019t understand the idea. Check the text and try again.',
  marketSizeUnavailable: 'No reliable market size was found for this idea\u2019s own market.',
  gapCaveat: 'A missing result in search does not prove a competitor or a gap does not exist.',
  emptyHistory: 'No saved validations yet. Run one to see it here.',
  lostConnection: 'Lost connection. Retrying\u2026',
} as const;

/** A duration as "6.5 s", or "1:46" once it passes a minute. Never an empty string. */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return '\u2014';
  }
  if (seconds < 60) {
    return `${seconds.toFixed(1)} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.floor(seconds % 60);
  return `${minutes}:${String(rest).padStart(2, '0')}`;
}

/** A count with its noun, pluralised: "1 competitor", "3 competitors". */
export function count(value: number, singular: string, plural = `${singular}s`): string {
  return `${value} ${value === 1 ? singular : plural}`;
}

/** The domain of a URL, for showing a source's origin. Empty when the URL cannot be read. */
export function domainOf(url: string | null | undefined): string {
  if (!url) {
    return '';
  }
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/** An ISO timestamp as a readable local date and time, or a dash when it is missing or unreadable. */
export function dateTime(iso: string | null | undefined): string {
  if (!iso) {
    return '\u2014';
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return '\u2014';
  }
  return parsed.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
