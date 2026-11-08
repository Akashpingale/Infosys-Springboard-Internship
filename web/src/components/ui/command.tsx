import { Command as CommandPrimitive } from 'cmdk';
import { Search } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/lib/cn';

/**
 * Command list (KIRO_UI_UPGRADE_SPEC.md Section 6.5), the searchable list inside the industry
 * combobox. cmdk gives the listbox roles and arrow-key movement; the styling is ours.
 */

export const Command = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive>
>(function Command({ className, ...props }, ref) {
  return (
    <CommandPrimitive
      ref={ref}
      className={cn('flex w-full flex-col overflow-hidden rounded-panel bg-surface', className)}
      {...props}
    />
  );
});

export const CommandInput = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Input>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Input>
>(function CommandInput({ className, ...props }, ref) {
  return (
    <div className="flex items-center gap-2 border-b border-line px-3">
      <Search className="size-4 shrink-0 text-content-muted" aria-hidden="true" />
      <CommandPrimitive.Input
        ref={ref}
        className={cn(
          'h-10 w-full bg-transparent text-body text-content outline-none placeholder:text-content-muted',
          className,
        )}
        {...props}
      />
    </div>
  );
});

export const CommandList = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.List>
>(function CommandList({ className, ...props }, ref) {
  return (
    <CommandPrimitive.List
      ref={ref}
      className={cn('max-h-64 overflow-y-auto overflow-x-hidden p-1', className)}
      {...props}
    />
  );
});

export const CommandEmpty = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Empty>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Empty>
>(function CommandEmpty({ className, ...props }, ref) {
  return (
    <CommandPrimitive.Empty
      ref={ref}
      className={cn('px-3 py-4 text-small text-content-muted', className)}
      {...props}
    />
  );
});

export const CommandGroup = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Group>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Group>
>(function CommandGroup({ className, ...props }, ref) {
  return <CommandPrimitive.Group ref={ref} className={cn('overflow-hidden', className)} {...props} />;
});

export const CommandItem = React.forwardRef<
  React.ElementRef<typeof CommandPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof CommandPrimitive.Item>
>(function CommandItem({ className, ...props }, ref) {
  return (
    <CommandPrimitive.Item
      ref={ref}
      className={cn(
        'flex cursor-pointer select-none items-center gap-2 rounded-control px-3 py-2 text-body text-content',
        'data-[selected=true]:bg-raised data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50',
        className,
      )}
      {...props}
    />
  );
});
