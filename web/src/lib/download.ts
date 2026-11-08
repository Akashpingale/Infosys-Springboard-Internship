/**
 * Saving a file from the page (KIRO_UI_UPGRADE_SPEC.md Section 7.6, export menu).
 *
 * The Markdown report, the raw JSON and the copy button all go through here, so the browser work
 * is written once and the screens stay readable. Nothing is uploaded and nothing is fetched: the
 * text is already in the page when these are called.
 */

/** Hand the text to the browser as a download. Returns false when the browser cannot do it. */
export function saveText(text: string, fileName: string, mimeType: string): boolean {
  if (typeof URL.createObjectURL !== 'function') {
    return false;
  }
  const url = URL.createObjectURL(new Blob([text], { type: `${mimeType};charset=utf-8` }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.rel = 'noreferrer noopener';
  document.body.append(link);
  link.click();
  link.remove();
  // Freed on the next tick, so the click has started before the URL goes away.
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  return true;
}

/** Copy the text to the clipboard. False when the browser refuses or has no clipboard. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard?.writeText) {
      return false;
    }
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
