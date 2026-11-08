import * as React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import { AppRoutes } from '@/app/router';
import { ErrorBoundary } from '@/app/ErrorBoundary';
import { Providers } from '@/app/providers';
import '@/styles/globals.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('The page is missing its #root element.');
}

ReactDOM.createRoot(container).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Providers>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </Providers>
    </ErrorBoundary>
  </React.StrictMode>,
);
