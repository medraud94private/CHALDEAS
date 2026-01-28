import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { trackEvent, AnalyticsEvents } from '../lib/analytics'

export type PreferredLanguage = 'auto' | 'ko' | 'ja' | 'en'
export type GlobeStyleOption = 'default' | 'holo' | 'night'

interface SettingsState {
  // Language preferences
  preferredLanguage: PreferredLanguage

  // Display settings
  hideEmptyDescriptions: boolean
  globeStyle: GlobeStyleOption

  // API settings
  shebaApiKey: string | null

  // Actions
  setPreferredLanguage: (lang: PreferredLanguage) => void
  setHideEmptyDescriptions: (hide: boolean) => void
  setGlobeStyle: (style: GlobeStyleOption) => void
  setShebaApiKey: (key: string | null) => void
  clearShebaApiKey: () => void
  resetSettings: () => void
}

const defaultSettings = {
  preferredLanguage: 'auto' as PreferredLanguage,
  hideEmptyDescriptions: false,
  globeStyle: 'default' as GlobeStyleOption,
  shebaApiKey: null,
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      // Initial state
      ...defaultSettings,

      // Actions
      setPreferredLanguage: (lang) => {
        trackEvent(AnalyticsEvents.LANGUAGE_CHANGED, { language: lang })
        set({ preferredLanguage: lang })
      },

      setHideEmptyDescriptions: (hide) => set({ hideEmptyDescriptions: hide }),

      setGlobeStyle: (style) => set({ globeStyle: style }),

      setShebaApiKey: (key) => set({ shebaApiKey: key }),

      clearShebaApiKey: () => set({ shebaApiKey: null }),

      resetSettings: () => set(defaultSettings),
    }),
    {
      name: 'chaldeas-settings',
      version: 1,
    }
  )
)

/**
 * Get the effective language based on user preference and browser settings.
 */
export function getEffectiveLanguage(preferredLanguage: PreferredLanguage): 'ko' | 'ja' | 'en' {
  if (preferredLanguage !== 'auto') {
    return preferredLanguage
  }

  // Auto-detect from browser
  const browserLang = navigator.language.toLowerCase()
  if (browserLang.startsWith('ko')) return 'ko'
  if (browserLang.startsWith('ja')) return 'ja'
  return 'en'
}

/**
 * Get localized text from an entity with multilingual fields.
 * Falls back to English if preferred language is not available.
 */
export function getLocalizedText<T extends Record<string, unknown>>(
  entity: T,
  fieldPrefix: string,
  preferredLanguage: PreferredLanguage
): string {
  const lang = getEffectiveLanguage(preferredLanguage)

  // Try preferred language first
  const preferredField = lang === 'en' ? fieldPrefix : `${fieldPrefix}_${lang}`
  const preferredValue = entity[preferredField]
  if (preferredValue && typeof preferredValue === 'string' && preferredValue.trim()) {
    return preferredValue
  }

  // Fallback to English
  const englishValue = entity[fieldPrefix]
  if (englishValue && typeof englishValue === 'string' && englishValue.trim()) {
    return englishValue
  }

  // Try other languages as fallback
  for (const fallbackLang of ['ko', 'ja']) {
    if (fallbackLang === lang) continue
    const fallbackField = `${fieldPrefix}_${fallbackLang}`
    const fallbackValue = entity[fallbackField]
    if (fallbackValue && typeof fallbackValue === 'string' && fallbackValue.trim()) {
      return fallbackValue
    }
  }

  return ''
}

/**
 * Get source information for display.
 */
export interface SourceInfo {
  type: 'wikipedia' | 'llm' | 'manual' | 'unknown'
  language?: string
  url?: string
}

export function parseSourceInfo(source: string | null | undefined, sourceUrl: string | null | undefined): SourceInfo {
  if (!source) {
    return { type: 'unknown' }
  }

  if (source.startsWith('wikipedia_')) {
    const lang = source.replace('wikipedia_', '')
    return {
      type: 'wikipedia',
      language: lang,
      url: sourceUrl || undefined
    }
  }

  if (source === 'llm' || source === 'ai') {
    return { type: 'llm' }
  }

  if (source === 'manual') {
    return { type: 'manual' }
  }

  return { type: 'unknown' }
}
