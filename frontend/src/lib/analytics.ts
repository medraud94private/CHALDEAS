/**
 * Analytics initialization for CHALDEAS
 *
 * Supports cookie-free, GDPR-compliant analytics:
 * - Plausible Analytics (recommended)
 * - Self-hosted Umami
 *
 * Set VITE_PLAUSIBLE_DOMAIN in .env to enable Plausible.
 * Set VITE_UMAMI_WEBSITE_ID and VITE_UMAMI_URL for self-hosted Umami.
 */

interface AnalyticsConfig {
  plausibleDomain?: string
  umamiWebsiteId?: string
  umamiUrl?: string
}

let analyticsInitialized = false

/**
 * Initialize analytics based on environment variables
 */
export function initAnalytics(): void {
  if (analyticsInitialized) return

  const config: AnalyticsConfig = {
    plausibleDomain: import.meta.env.VITE_PLAUSIBLE_DOMAIN,
    umamiWebsiteId: import.meta.env.VITE_UMAMI_WEBSITE_ID,
    umamiUrl: import.meta.env.VITE_UMAMI_URL,
  }

  // Plausible Analytics (cookie-free, GDPR compliant)
  if (config.plausibleDomain) {
    initPlausible(config.plausibleDomain)
    analyticsInitialized = true
    console.log('[Analytics] Plausible initialized for', config.plausibleDomain)
    return
  }

  // Self-hosted Umami (cookie-free, GDPR compliant)
  if (config.umamiWebsiteId && config.umamiUrl) {
    initUmami(config.umamiWebsiteId, config.umamiUrl)
    analyticsInitialized = true
    console.log('[Analytics] Umami initialized')
    return
  }

  console.log('[Analytics] No analytics configured')
}

/**
 * Initialize Plausible Analytics
 * https://plausible.io/docs/plausible-script
 */
function initPlausible(domain: string): void {
  const script = document.createElement('script')
  script.defer = true
  script.dataset.domain = domain
  script.src = 'https://plausible.io/js/script.js'
  document.head.appendChild(script)
}

/**
 * Initialize self-hosted Umami
 * https://umami.is/docs/tracker-functions
 */
function initUmami(websiteId: string, umamiUrl: string): void {
  const script = document.createElement('script')
  script.async = true
  script.dataset.websiteId = websiteId
  script.src = `${umamiUrl}/script.js`
  document.head.appendChild(script)
}

// Custom event tracking interface
declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string | number | boolean> }) => void
    umami?: {
      track: (event: string, data?: Record<string, string | number | boolean>) => void
    }
  }
}

/**
 * Track a custom event
 * Works with both Plausible and Umami
 */
export function trackEvent(eventName: string, props?: Record<string, string | number | boolean>): void {
  // Plausible
  if (window.plausible) {
    window.plausible(eventName, props ? { props } : undefined)
  }

  // Umami
  if (window.umami) {
    window.umami.track(eventName, props)
  }
}

/**
 * Common events to track
 */
export const AnalyticsEvents = {
  // Search events
  SEARCH_PERFORMED: 'search_performed',
  SEARCH_RESULT_CLICKED: 'search_result_clicked',

  // Entity view events
  EVENT_VIEWED: 'event_viewed',
  PERSON_VIEWED: 'person_viewed',
  LOCATION_VIEWED: 'location_viewed',

  // Globe interaction events
  GLOBE_ROTATED: 'globe_rotated',
  TIMELINE_CHANGED: 'timeline_changed',
  MARKER_CLICKED: 'marker_clicked',

  // Settings events
  LANGUAGE_CHANGED: 'language_changed',
  SETTINGS_OPENED: 'settings_opened',

  // Feature usage
  SHEBA_CHAT_OPENED: 'sheba_chat_opened',
  SHOWCASE_VIEWED: 'showcase_viewed',
  FILTER_APPLIED: 'filter_applied',
} as const
