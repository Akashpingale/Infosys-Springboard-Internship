/**
 * Asking the browser about the viewport (KIRO_UI_UPGRADE_SPEC.md Sections 6.9 and Prompt J).
 *
 * Most of the responsive work is plain CSS. Two screens need more than that: a wide data table
 * cannot be made readable at 390 px by hiding columns, so the sources list and the history become
 * cards instead. Choosing in JavaScript rather than rendering both and hiding one keeps a single
 * copy in the document, so a screen reader is never read the same row twice and the keyboard never
 * walks through invisible controls.
 *
 * The default when a browser cannot answer is the wide layout, which is the one with the full
 * table: a reader who gets the wrong one still gets everything.
 */

import * as React from 'react';

/** Below the `lg` breakpoint in tailwind.config.js, where the tables stop fitting. */
export const NARROW = '(max-width: 1023px)';

function read(query: string): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia(query).matches;
}

/** True while the viewport matches. Follows the viewport as it changes. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = React.useState(() => read(query));

  React.useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return;
    }
    const list = window.matchMedia(query);
    setMatches(list.matches);

    function onChange(event: MediaQueryListEvent): void {
      setMatches(event.matches);
    }
    // addListener is the old name; some browsers in use still only have that one.
    if (typeof list.addEventListener === 'function') {
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    }
    list.addListener(onChange);
    return () => list.removeListener(onChange);
  }, [query]);

  return matches;
}
