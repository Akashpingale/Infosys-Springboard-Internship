import * as PopoverPrimitive from '@radix-ui/react-popover';
import * as React from 'react';

import { cn } from '@/lib/cn';

/**
 * Popover (KIRO_UI_UPGRADE_SPEC.md Section 6.9): Radix handles the focus trap, Escape to close and
 * returning focus to the trigger. A shadow is allowed here, because it is an overlay (Section 6.4).
 */

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverAnchor = PopoverPrimitive.Anchor;

export const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(function PopoverContent({ className, align = 'start', sideOffset = 4, ...props }, ref) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          'z-50 w-[--radix-popover-trigger-width] rounded-panel border border-line bg-surface',
          'text-content shadow-overlay outline-none',
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
});
