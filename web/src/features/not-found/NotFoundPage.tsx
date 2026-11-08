import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/EmptyState';

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-form space-y-6">
      <h1>That page does not exist</h1>
      <EmptyState
        message="The address you opened is not part of this app. Start a new validation instead."
        action={
          <Button asChild variant="secondary">
            <Link to="/">Go to new validation</Link>
          </Button>
        }
      />
    </div>
  );
}
