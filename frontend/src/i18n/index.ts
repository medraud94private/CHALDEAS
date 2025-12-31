import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import ko from './locales/ko.json'
import ja from './locales/ja.json'
import en from './locales/en.json'

const resources = {
  ko: { translation: ko },
  ja: { translation: ja },
  en: { translation: en },
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'ko',  // 기본 언어: 한국어
    supportedLngs: ['ko', 'ja', 'en'],

    interpolation: {
      escapeValue: false,
    },

    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
      lookupLocalStorage: 'chaldeas-language',
    },
  })

export default i18n

// 언어 변경 함수
export const changeLanguage = (lang: 'ko' | 'ja' | 'en') => {
  i18n.changeLanguage(lang)
  localStorage.setItem('chaldeas-language', lang)
}

// 현재 언어 가져오기
export const getCurrentLanguage = () => {
  return i18n.language as 'ko' | 'ja' | 'en'
}

// 지원 언어 목록
export const SUPPORTED_LANGUAGES = [
  { code: 'ko', name: '한국어', nativeName: '한국어' },
  { code: 'ja', name: '日本語', nativeName: '日本語' },
  { code: 'en', name: 'English', nativeName: 'English' },
] as const
