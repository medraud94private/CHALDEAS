/**
 * LanguageSelector - 언어 선택 컴포넌트
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { SUPPORTED_LANGUAGES, changeLanguage } from '../../i18n'

export function LanguageSelector() {
  const { i18n } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  const currentLang = SUPPORTED_LANGUAGES.find(l => l.code === i18n.language)
    || SUPPORTED_LANGUAGES[0]

  const handleSelect = (code: 'ko' | 'ja' | 'en') => {
    changeLanguage(code)
    setIsOpen(false)
  }

  return (
    <div className="language-selector">
      <button
        className="language-btn"
        onClick={() => setIsOpen(!isOpen)}
        title="Change Language"
      >
        <span className="lang-code">{currentLang.code.toUpperCase()}</span>
        <span className="lang-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="language-dropdown">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              className={`language-option ${lang.code === i18n.language ? 'active' : ''}`}
              onClick={() => handleSelect(lang.code as 'ko' | 'ja' | 'en')}
            >
              <span className="lang-native">{lang.nativeName}</span>
              <span className="lang-code-small">{lang.code.toUpperCase()}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
