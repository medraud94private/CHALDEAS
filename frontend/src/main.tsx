import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import * as Sentry from '@sentry/react'
import App from './App'
import { initSentry, ErrorFallback } from './lib/sentry'
import { initAnalytics } from './lib/analytics'
import './i18n'  // i18n 초기화
import './styles/globals.css'

// Initialize Sentry error tracking
initSentry()

// Initialize cookie-free analytics (Plausible/Umami)
initAnalytics()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes - data considered fresh
      gcTime: 1000 * 60 * 10,   // 10 minutes - cache retention
      refetchOnWindowFocus: false, // Prevent refetch on tab focus
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={ErrorFallback}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </Sentry.ErrorBoundary>
  </React.StrictMode>,
)
