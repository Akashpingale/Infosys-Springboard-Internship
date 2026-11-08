/**
 * The viewport hook (KIRO_UI_UPGRADE_SPEC.md Prompt J).
 *
 * The hook decides whether a screen shows its table or its cards, so the thing worth proving is
 * that it answers "wide" when the browser cannot tell it anything. A reader on an old browser then
 * gets the layout that holds every column, rather than a stripped-down one.
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { NARROW, useMediaQuery } from '@/lib/useMediaQuery';

type Listener = (event: MediaQueryListEvent) => void;

/** A matchMedia whose answer can be changed, as resizing a window would. */
function fakeMatchMedia(initial: boolean) {
  const listeners = new Set<Listener>();
  const list = {
    matches: initial,
    media: NARROW,
    onchange: null,
    addEventListener: (_type: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_type: string, listener: Listener) => listeners.delete(listener),
    addListener: (listener: Listener) => listeners.add(listener),
    removeListener: (listener: Listener) => listeners.delete(listener),
    dispatchEvent: () => false,
  };
  const matchMedia = vi.fn(() => list as unknown as MediaQueryList);
  Object.defineProperty(window, 'matchMedia', { writable: true, configurable: true, value: matchMedia });
  return {
    list,
    listeners,
    resize(matches: boolean) {
      list.matches = matches;
      for (const listener of listeners) {
        listener({ matches } as MediaQueryListEvent);
      }
    },
  };
}

const original = window.matchMedia;

afterEach(() => {
  Object.defineProperty(window, 'matchMedia', { writable: true, configurable: true, value: original });
  vi.restoreAllMocks();
});

describe('useMediaQuery', () => {
  it('reports what the browser says', () => {
    fakeMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery(NARROW));

    expect(result.current).toBe(true);
  });

  it('follows the viewport as it changes', () => {
    const media = fakeMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery(NARROW));

    expect(result.current).toBe(false);
    act(() => media.resize(true));
    expect(result.current).toBe(true);
    act(() => media.resize(false));
    expect(result.current).toBe(false);
  });

  it('stops listening when the screen goes away', () => {
    const media = fakeMatchMedia(true);
    const { unmount } = renderHook(() => useMediaQuery(NARROW));

    expect(media.listeners.size).toBe(1);
    unmount();
    expect(media.listeners.size).toBe(0);
  });

  it('answers "not narrow" when the browser has no matchMedia at all', () => {
    Object.defineProperty(window, 'matchMedia', { writable: true, configurable: true, value: undefined });

    const { result } = renderHook(() => useMediaQuery(NARROW));

    // The wide layout is the one with every column, so it is the safe answer.
    expect(result.current).toBe(false);
  });
});
