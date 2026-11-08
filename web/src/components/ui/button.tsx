/**
 * Button (KIRO_UI_UPGRADE_SPEC.md Section 6.5), in the shadcn/ui shape: a Radix Slot so it can
 * render as a link, and variants through class-variance-authority.
 *
 * Primary is a solid blue with dark text; secondary carries a 1 px border; text has neither. All
 * are at least 40 px high, and 44 px on a touch screen (Section 6.9).
 */

import { Slot } from '@radix-ui/react-slot';
import { type VariantProps, cva } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/lib/cn';

const buttonVariants = cva(
  cn(
    'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control',
    'text-body font-medium transition-colors duration-tab',
    'disabled:pointer-events-none disabled:opacity-50',
    '[&_svg]:size-5 [&_svg]:shrink-0',
  ),
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-contrast hover:bg-primary-hover',
        secondary: 'border border-line-strong bg-transparent text-content hover:bg-raised',
        text: 'bg-transparent text-primary hover:text-primary-hover hover:underline',
        danger: 'border border-danger-border bg-danger-bg text-danger hover:bg-raised',
      },
      size: {
        // Section 6.4: an action row is 40 px high, 44 px where a finger is used.
        default: 'h-10 min-h-[44px] px-4 sm:min-h-10',
        // 32 px from the small breakpoint up, 44 px below it, where a finger is used (Section 6.9).
        small: 'h-8 min-h-[44px] px-3 text-small sm:min-h-8',
        icon: 'size-10 min-h-[44px] p-0 sm:min-h-10',
      },
      full: { true: 'w-full', false: '' },
    },
    defaultVariants: { variant: 'primary', size: 'default', full: false },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  /** Shows a spinner and blocks the click, for a request in flight (Section 8.1). */
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, full, asChild = false, loading = false, disabled, children, ...props },
  ref,
) {
  const Component = asChild ? Slot : 'button';
  return (
    <Component
      ref={ref}
      className={cn(buttonVariants({ variant, size, full }), className)}
      disabled={disabled ?? loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <>
          <Loader2 className="animate-spin" aria-hidden="true" />
          {children}
        </>
      ) : (
        children
      )}
    </Component>
  );
});

export { buttonVariants };
