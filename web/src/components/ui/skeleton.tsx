import { cn } from '@/lib/cn';

/**
 * A loading placeholder (KIRO_UI_UPGRADE_SPEC.md Section 6.5). It takes the space its content will
 * take, so nothing shifts when the content arrives, and it is hidden from assistive technology
 * because the surrounding region announces the loading state.
 */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn('animate-pulse rounded-control bg-raised', className)}
      {...props}
    />
  );
}
