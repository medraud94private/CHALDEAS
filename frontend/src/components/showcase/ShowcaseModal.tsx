/**
 * ShowcaseModal - FGO Style Content Showcase
 * Displays curated content like Singularities, Lostbelts, Servant columns
 */
import { useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import './showcase.css'

export interface ShowcaseContent {
  id: string
  type: 'singularity' | 'lostbelt' | 'servant' | 'article'
  title: string
  subtitle?: string
  chapter?: string
  era?: string
  year?: number
  location?: string
  image?: string
  description: string
  sections?: {
    title: string
    content: string
  }[]
  relatedEvents?: {
    id: number
    title: string
    year: number
  }[]
  relatedServants?: {
    name: string
    class: string
    rarity: number
  }[]
  historicalBasis?: string
  sources?: string[]
}

interface Props {
  isOpen: boolean
  content: ShowcaseContent | null
  onClose: () => void
  onEventClick?: (eventId: number) => void
}

export function ShowcaseModal({ isOpen, content, onClose, onEventClick }: Props) {
  const { t } = useTranslation()

  // Close on Escape key
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') onClose()
  }, [onClose])

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  if (!isOpen || !content) return null

  const getTypeLabel = () => {
    switch (content.type) {
      case 'singularity': return t('showcase.types.singularity')
      case 'lostbelt': return t('showcase.types.lostbelt')
      case 'servant': return t('showcase.types.servant')
      case 'article': return t('showcase.types.article')
      default: return ''
    }
  }

  const getTypeColor = () => {
    switch (content.type) {
      case 'singularity': return 'var(--chaldea-orange)'
      case 'lostbelt': return 'var(--chaldea-magenta)'
      case 'servant': return 'var(--chaldea-gold)'
      case 'article': return 'var(--chaldea-cyan)'
      default: return 'var(--chaldea-cyan)'
    }
  }

  const renderRarityStars = (rarity: number) => {
    return '★'.repeat(rarity)
  }

  return (
    <div className="showcase-overlay" onClick={onClose}>
      <div className="showcase-modal" onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button className="showcase-close" onClick={onClose}>
          ✕
        </button>

        {/* Header */}
        <div className="showcase-header" style={{ borderColor: getTypeColor() }}>
          <div className="showcase-type" style={{ color: getTypeColor() }}>
            <span className="type-icon">◈</span>
            {getTypeLabel()}
            {content.chapter && <span className="chapter-badge">{content.chapter}</span>}
          </div>
          <h1 className="showcase-title">{content.title}</h1>
          {content.subtitle && (
            <div className="showcase-subtitle">{content.subtitle}</div>
          )}
          <div className="showcase-meta">
            {content.era && <span className="meta-item">{content.era}</span>}
            {content.year && (
              <span className="meta-item">
                {content.year < 0 ? `${Math.abs(content.year)} BC` : `${content.year} AD`}
              </span>
            )}
            {content.location && <span className="meta-item">{content.location}</span>}
          </div>
        </div>

        {/* Content Body */}
        <div className="showcase-body">
          {/* Main Description */}
          <div className="showcase-description">
            {content.description}
          </div>

          {/* Sections */}
          {content.sections?.map((section, idx) => (
            <div key={idx} className="showcase-section">
              <h3 className="section-title">
                <span className="section-marker">▸</span>
                {section.title}
              </h3>
              <div className="section-content">{section.content}</div>
            </div>
          ))}

          {/* Historical Basis */}
          {content.historicalBasis && (
            <div className="showcase-section historical">
              <h3 className="section-title">
                <span className="section-marker">▸</span>
                {t('showcase.historicalBasis')}
              </h3>
              <div className="section-content">{content.historicalBasis}</div>
            </div>
          )}

          {/* Related Servants */}
          {content.relatedServants && content.relatedServants.length > 0 && (
            <div className="showcase-section">
              <h3 className="section-title">
                <span className="section-marker">▸</span>
                {t('showcase.relatedServants')}
              </h3>
              <div className="servant-grid">
                {content.relatedServants.map((servant, idx) => (
                  <div key={idx} className="servant-card">
                    <div className="servant-class">{servant.class}</div>
                    <div className="servant-name">{servant.name}</div>
                    <div className="servant-rarity" style={{ color: 'var(--chaldea-gold)' }}>
                      {renderRarityStars(servant.rarity)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Related Events */}
          {content.relatedEvents && content.relatedEvents.length > 0 && (
            <div className="showcase-section">
              <h3 className="section-title">
                <span className="section-marker">▸</span>
                {t('showcase.relatedEvents')}
              </h3>
              <div className="related-events-list">
                {content.relatedEvents.map((event) => (
                  <button
                    key={event.id}
                    className="related-event-btn"
                    onClick={() => onEventClick?.(event.id)}
                  >
                    <span className="event-year">
                      {event.year < 0 ? `${Math.abs(event.year)} BC` : `${event.year} AD`}
                    </span>
                    <span className="event-title">{event.title}</span>
                    <span className="event-arrow">→</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Sources */}
          {content.sources && content.sources.length > 0 && (
            <div className="showcase-sources">
              <div className="sources-label">{t('showcase.sources')}</div>
              <div className="sources-list">
                {content.sources.map((source, idx) => (
                  <span key={idx} className="source-item">{source}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="showcase-footer">
          <div className="footer-decoration">
            <span className="deco-line"></span>
            <span className="deco-text">CHALDEAS ARCHIVE</span>
            <span className="deco-line"></span>
          </div>
        </div>
      </div>
    </div>
  )
}
