/**
 * Tailwind CSS v3 (KIRO_UI_UPGRADE_SPEC.md Section 6).
 *
 * Every colour, size and radius here points at a CSS variable in src/styles/tokens.css, so the
 * palette lives in exactly one place and a component never carries a hex value.
 */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'var(--canvas)',
        surface: 'var(--surface)',
        raised: 'var(--raised)',
        'raised-soft': 'var(--raised-soft)',
        line: 'var(--border)',
        'line-strong': 'var(--border-strong)',
        content: {
          DEFAULT: 'var(--text)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          contrast: 'var(--primary-contrast)',
        },
        ring: 'var(--focus-ring)',
        success: { DEFAULT: 'var(--success)', bg: 'var(--success-bg)', border: 'var(--success-border)' },
        warning: { DEFAULT: 'var(--warning)', bg: 'var(--warning-bg)', border: 'var(--warning-border)' },
        danger: { DEFAULT: 'var(--danger)', bg: 'var(--danger-bg)', border: 'var(--danger-border)' },
        info: { DEFAULT: 'var(--info)', bg: 'var(--info-bg)', border: 'var(--info-border)' },
        // Section 9, chart 3: the four stage-timing steps.
        step: {
          1: 'var(--chart-step-1)',
          2: 'var(--chart-step-2)',
          3: 'var(--chart-step-3)',
          4: 'var(--chart-step-4)',
        },
        // Each basis has its colour, its tint and its edge, named like the status colours above so
        // no component needs an opacity modifier (which these variable colours cannot take).
        sourced: {
          DEFAULT: 'var(--basis-sourced)',
          bg: 'var(--basis-sourced-bg)',
          border: 'var(--basis-sourced-border)',
        },
        interpretation: {
          DEFAULT: 'var(--basis-interpretation)',
          bg: 'var(--basis-interpretation-bg)',
          border: 'var(--basis-interpretation-border)',
        },
        provided: {
          DEFAULT: 'var(--basis-provided)',
          bg: 'var(--basis-provided-bg)',
          border: 'var(--basis-provided-border)',
        },
        assumption: {
          DEFAULT: 'var(--basis-assumption)',
          bg: 'var(--basis-assumption-bg)',
          border: 'var(--basis-assumption-border)',
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        condensed: ['IBM Plex Sans Condensed', 'IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      // Section 6.3, each size with the line height the specification gives.
      fontSize: {
        micro: ['0.75rem', { lineHeight: '1rem', fontWeight: '500' }],
        small: ['0.8125rem', { lineHeight: '1.25rem' }],
        body: ['0.9375rem', { lineHeight: '1.5rem' }],
        h3: ['1rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        h2: ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }],
        h1: ['1.75rem', { lineHeight: '2.125rem', fontWeight: '600' }],
        display: ['2.25rem', { lineHeight: '2.5rem', fontWeight: '600' }],
        kpi: ['2rem', { lineHeight: '2.25rem', fontWeight: '600' }],
      },
      // Section 6.4: the 4, 8, 12, 16, 24, 32, 48, 64 scale, named so it cannot drift.
      spacing: {
        1: '0.25rem',
        2: '0.5rem',
        3: '0.75rem',
        4: '1rem',
        6: '1.5rem',
        8: '2rem',
        12: '3rem',
        16: '4rem',
      },
      borderRadius: {
        control: '6px',
        panel: '10px',
        pill: '9999px',
      },
      maxWidth: {
        app: '1280px',
        form: '720px',
        prose: '72ch',
      },
      screens: {
        sm: '640px',
        lg: '1024px',
        xl: '1280px',
      },
      boxShadow: {
        // Section 6.4: borders only, except the drawer and menus.
        overlay: '0 16px 48px -24px rgba(0, 0, 0, 0.75)',
      },
      transitionDuration: {
        tab: '120ms',
        drawer: '180ms',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
