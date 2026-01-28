/**
 * SettingsPage - User preferences and configuration
 *
 * Sections:
 * - Language preferences (auto/ko/ja/en)
 * - Display settings (hide empty descriptions, globe style)
 * - SHEBA API key management
 * - License information (CC BY-SA for Wikipedia)
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSettingsStore, type PreferredLanguage, type GlobeStyleOption } from '../../store/settingsStore'
import './SettingsPage.css'

interface Props {
  isOpen: boolean
  onClose: () => void
}

export function SettingsPage({ isOpen, onClose }: Props) {
  const { t } = useTranslation()
  const {
    preferredLanguage,
    hideEmptyDescriptions,
    globeStyle,
    shebaApiKey,
    setPreferredLanguage,
    setHideEmptyDescriptions,
    setGlobeStyle,
    setShebaApiKey,
    clearShebaApiKey,
    resetSettings,
  } = useSettingsStore()

  const [apiKeyInput, setApiKeyInput] = useState(shebaApiKey || '')
  const [showApiKey, setShowApiKey] = useState(false)

  if (!isOpen) return null

  const handleSaveApiKey = () => {
    if (apiKeyInput.trim()) {
      setShebaApiKey(apiKeyInput.trim())
    }
  }

  const handleClearApiKey = () => {
    clearShebaApiKey()
    setApiKeyInput('')
  }

  const handleReset = () => {
    if (window.confirm(t('settings.confirmReset', 'Reset all settings to defaults?'))) {
      resetSettings()
      setApiKeyInput('')
    }
  }

  const languageOptions: { value: PreferredLanguage; label: string; desc: string }[] = [
    { value: 'auto', label: t('settings.langAuto', 'Auto'), desc: t('settings.langAutoDesc', 'Use browser language') },
    { value: 'en', label: 'English', desc: t('settings.langEnDesc', 'Display in English') },
    { value: 'ko', label: '한국어', desc: t('settings.langKoDesc', 'Display in Korean') },
    { value: 'ja', label: '日本語', desc: t('settings.langJaDesc', 'Display in Japanese') },
  ]

  const globeStyleOptions: { value: GlobeStyleOption; label: string }[] = [
    { value: 'default', label: t('globe.styles.default', 'Default') },
    { value: 'holo', label: t('globe.styles.holo', 'Holographic') },
    { value: 'night', label: t('globe.styles.night', 'Night') },
  ]

  return (
    <div className="settings-overlay" onClick={onClose} role="presentation">
      <div
        className="settings-page"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        {/* Header */}
        <div className="settings-header">
          <h2 id="settings-title">{t('settings.title', 'Settings')}</h2>
          <button className="settings-close" onClick={onClose} aria-label="Close settings">
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="settings-content">
          {/* Language Section */}
          <section className="settings-section">
            <div className="section-header">
              <span className="section-icon">🌐</span>
              <h3>{t('settings.language', 'Language Preferences')}</h3>
            </div>
            <p className="section-desc">
              {t('settings.languageDesc', 'Choose your preferred language for entity descriptions.')}
            </p>
            <div className="language-options">
              {languageOptions.map((opt) => (
                <button
                  key={opt.value}
                  className={`language-option ${preferredLanguage === opt.value ? 'active' : ''}`}
                  onClick={() => setPreferredLanguage(opt.value)}
                >
                  <span className="lang-label">{opt.label}</span>
                  <span className="lang-desc">{opt.desc}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Display Section */}
          <section className="settings-section">
            <div className="section-header">
              <span className="section-icon">🎨</span>
              <h3>{t('settings.display', 'Display Settings')}</h3>
            </div>

            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">
                  {t('settings.hideEmpty', 'Hide items without descriptions')}
                </span>
                <span className="setting-desc">
                  {t('settings.hideEmptyDesc', 'Filter out events/persons/locations that have no description')}
                </span>
              </div>
              <label className="toggle-switch">
                <input
                  type="checkbox"
                  checked={hideEmptyDescriptions}
                  onChange={(e) => setHideEmptyDescriptions(e.target.checked)}
                  aria-label={t('settings.hideEmpty', 'Hide items without descriptions')}
                />
                <span className="toggle-slider" aria-hidden="true" />
              </label>
            </div>

            <div className="setting-row">
              <div className="setting-info">
                <span className="setting-label">
                  {t('settings.globeStyle', 'Globe Style')}
                </span>
              </div>
              <div className="style-options">
                {globeStyleOptions.map((opt) => (
                  <button
                    key={opt.value}
                    className={`style-option ${globeStyle === opt.value ? 'active' : ''}`}
                    onClick={() => setGlobeStyle(opt.value)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* API Key Section */}
          <section className="settings-section">
            <div className="section-header">
              <span className="section-icon">🔑</span>
              <h3>{t('settings.apiKey', 'SHEBA API Key')}</h3>
            </div>
            <p className="section-desc">
              {t('settings.apiKeyDesc', 'Optional API key for enhanced SHEBA queries. Contact support for access.')}
            </p>
            <div className="api-key-input-row">
              <div className="api-key-input-wrapper">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={t('settings.apiKeyPlaceholder', 'Enter API key...')}
                  className="api-key-input"
                />
                <button
                  className="api-key-toggle"
                  onClick={() => setShowApiKey(!showApiKey)}
                  title={showApiKey ? 'Hide' : 'Show'}
                  aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                >
                  {showApiKey ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
              <div className="api-key-actions">
                <button
                  className="api-key-save"
                  onClick={handleSaveApiKey}
                  disabled={!apiKeyInput.trim() || apiKeyInput === shebaApiKey}
                >
                  {t('settings.save', 'Save')}
                </button>
                {shebaApiKey && (
                  <button className="api-key-clear" onClick={handleClearApiKey}>
                    {t('settings.clear', 'Clear')}
                  </button>
                )}
              </div>
            </div>
            {shebaApiKey && (
              <div className="api-key-status">
                <span className="status-dot active" />
                {t('settings.apiKeyActive', 'API key is active')}
              </div>
            )}
          </section>

          {/* License Section */}
          <section className="settings-section license-section">
            <div className="section-header">
              <span className="section-icon">📜</span>
              <h3>{t('settings.license', 'Data Sources & Licenses')}</h3>
            </div>
            <div className="license-content">
              <div className="license-item">
                <div className="license-icon">
                  <img
                    src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/80/Wikipedia-logo-v2.svg/48px-Wikipedia-logo-v2.svg.png"
                    alt="Wikipedia"
                    width="24"
                    height="24"
                  />
                </div>
                <div className="license-info">
                  <span className="license-name">Wikipedia</span>
                  <span className="license-type">
                    <a
                      href="https://creativecommons.org/licenses/by-sa/4.0/"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      CC BY-SA 4.0
                    </a>
                  </span>
                </div>
              </div>
              <p className="license-notice">
                {t('settings.licenseNotice',
                  'Entity descriptions marked with Wikipedia source are licensed under Creative Commons Attribution-ShareAlike 4.0. Click on source links to view original articles.'
                )}
              </p>
              <div className="license-item">
                <div className="license-icon">🔗</div>
                <div className="license-info">
                  <span className="license-name">Wikidata</span>
                  <span className="license-type">
                    <a
                      href="https://creativecommons.org/publicdomain/zero/1.0/"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      CC0 1.0
                    </a>
                  </span>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="settings-footer">
          <button className="settings-reset" onClick={handleReset}>
            {t('settings.resetAll', 'Reset All Settings')}
          </button>
          <div className="settings-version">
            CHALDEAS v0.7.0
          </div>
        </div>
      </div>
    </div>
  )
}
