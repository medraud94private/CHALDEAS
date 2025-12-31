/**
 * EventDetailPanel - FGO-style event detail with related events and context
 */
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { Event } from '../../types'

interface Props {
  event: Event | null
  allEvents: Event[]
  onClose: () => void
  onEventClick: (event: Event) => void
  onAskSheba: (query: string) => void
}

export function EventDetailPanel({
  event,
  allEvents,
  onClose,
  onEventClick,
  onAskSheba
}: Props) {
  const { t } = useTranslation()

  // Format year display
  const formatYear = (year: number) => {
    const absYear = Math.abs(year)
    const era = year < 0 ? t('timeline.era.bce') : t('timeline.era.ce')
    return `${absYear} ${era}`
  }

  // Find related events (before/after within 50 years, same category)
  const relatedEvents = useMemo(() => {
    if (!event || !allEvents.length) return { before: [], after: [], related: [] }

    const eventYear = event.date_start
    const eventCat = typeof event.category === 'string' ? event.category : event.category?.slug

    // Events before (within 100 years)
    const before = allEvents
      .filter(e =>
        e.id !== event.id &&
        e.date_start < eventYear &&
        e.date_start >= eventYear - 100
      )
      .sort((a, b) => b.date_start - a.date_start)
      .slice(0, 3)

    // Events after (within 100 years)
    const after = allEvents
      .filter(e =>
        e.id !== event.id &&
        e.date_start > eventYear &&
        e.date_start <= eventYear + 100
      )
      .sort((a, b) => a.date_start - b.date_start)
      .slice(0, 3)

    // Related by category (same category, different time)
    const related = allEvents
      .filter(e => {
        if (e.id === event.id) return false
        const eCat = typeof e.category === 'string' ? e.category : e.category?.slug
        return eCat === eventCat && Math.abs(e.date_start - eventYear) > 100
      })
      .sort((a, b) => Math.abs(a.date_start - eventYear) - Math.abs(b.date_start - eventYear))
      .slice(0, 3)

    return { before, after, related }
  }, [event, allEvents])

  // Extract category info
  const category = useMemo(() => {
    if (!event) return null
    if (typeof event.category === 'string') return event.category
    return event.category?.slug || 'general'
  }, [event])

  if (!event) {
    return (
      <aside className="detail-panel hidden">
        <div />
      </aside>
    )
  }

  return (
    <aside className="detail-panel">
      <button className="close-btn" onClick={onClose}>
        ✕
      </button>

      {/* Header with Year */}
      <div className="detail-header">
        <div className="detail-meta">
          {event.sources && event.sources.length > 0 ? (
            <span className="source-ref" title={event.sources[0].name}>
              📜 {event.sources[0].type === 'primary' ? t('detail.primary') : t('detail.secondary')}: {event.sources[0].name?.slice(0, 30)}{event.sources[0].name && event.sources[0].name.length > 30 ? '...' : ''}
            </span>
          ) : (
            <span className="source-ref">📚 {t('detail.archiveId', { id: event.id })}</span>
          )}
        </div>
        <div className="detail-year">
          <div className="detail-year-number">
            {Math.abs(event.date_start)}
          </div>
          <div className="detail-year-era">
            {event.date_start < 0 ? t('timeline.era.bce') : t('timeline.era.ce')}
          </div>
        </div>
      </div>

      {/* Title */}
      <div className="detail-title">
        <h2>{event.title}</h2>
      </div>

      {/* Content */}
      <div className="detail-content">
        {/* Description */}
        <p className="detail-description">
          {event.description || t('detail.pendingDescription')}
        </p>

        {/* Category Badge */}
        {category && (
          <div style={{ marginBottom: '1rem' }}>
            <span className={`event-category-badge ${category}`}>
              {t(`categories.${category}`, category)}
            </span>
          </div>
        )}

        {/* Ask SHEBA Button */}
        <button
          className="ask-sheba-btn"
          onClick={() => onAskSheba(t('detail.askShebaQuery', { title: event.title }))}
        >
          {t('detail.askShebaAbout')}
        </button>

        {/* Chronological Context */}
        {(relatedEvents.before.length > 0 || relatedEvents.after.length > 0) && (
          <div className="detail-section">
            <div className="detail-section-header">
              {t('detail.chronologicalContext')}
            </div>

            {/* Events Before */}
            {relatedEvents.before.length > 0 && (
              <div className="related-events" style={{ marginBottom: '1rem' }}>
                <div style={{ fontSize: '0.65rem', color: 'var(--chaldea-magenta)', marginBottom: '0.5rem', letterSpacing: '0.1em' }}>
                  {t('detail.precedingEvents')}
                </div>
                {relatedEvents.before.map((e) => (
                  <div
                    key={e.id}
                    className="related-event-item before"
                    onClick={() => onEventClick(e)}
                  >
                    <span className="related-event-year">{formatYear(e.date_start)}</span>
                    <span className="related-event-title">{e.title}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Current Event Marker */}
            <div style={{
              textAlign: 'center',
              padding: '0.5rem',
              background: 'rgba(0, 212, 255, 0.1)',
              border: '1px solid var(--chaldea-cyan)',
              borderRadius: '4px',
              marginBottom: '1rem'
            }}>
              <span style={{ color: 'var(--chaldea-cyan)', fontSize: '0.75rem', fontWeight: 600 }}>
                {t('detail.currentEvent', { year: formatYear(event.date_start) })}
              </span>
            </div>

            {/* Events After */}
            {relatedEvents.after.length > 0 && (
              <div className="related-events">
                <div style={{ fontSize: '0.65rem', color: 'var(--chaldea-green)', marginBottom: '0.5rem', letterSpacing: '0.1em' }}>
                  {t('detail.followingEvents')}
                </div>
                {relatedEvents.after.map((e) => (
                  <div
                    key={e.id}
                    className="related-event-item after"
                    onClick={() => onEventClick(e)}
                  >
                    <span className="related-event-year">{formatYear(e.date_start)}</span>
                    <span className="related-event-title">{e.title}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Related Events by Category */}
        {relatedEvents.related.length > 0 && (
          <div className="detail-section">
            <div className="detail-section-header">
              {t('detail.relatedRecords', { category: t(`categories.${category}`, category || '').toUpperCase() })}
            </div>
            <div className="related-events">
              {relatedEvents.related.map((e) => (
                <div
                  key={e.id}
                  className="related-event-item"
                  onClick={() => onEventClick(e)}
                >
                  <span className="related-event-year">{formatYear(e.date_start)}</span>
                  <span className="related-event-title">{e.title}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Persons Section (if available) */}
        {event.persons && event.persons.length > 0 && (
          <div className="detail-section">
            <div className="detail-section-header">
              {t('detail.keyFigures')}
            </div>
            <div className="related-persons">
              {event.persons.map((person) => (
                <span key={person.id} className="person-tag">
                  {person.name}
                  {person.role && <span style={{ opacity: 0.6 }}> ({person.role})</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Sources Section (if available) */}
        {event.sources && event.sources.length > 0 && (
          <div className="detail-section">
            <div className="detail-section-header">
              {t('detail.historicalSources')}
            </div>
            <div className="sources-list">
              {event.sources.map((source) => (
                <div key={source.id} className="source-item">
                  <span>{source.name}</span>
                  {source.reliability && (
                    <span className="source-reliability">
                      {'★'.repeat(source.reliability)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="detail-footer">
        <div className="detail-coords">
          {t('detail.coordinates', {
            lat: event.latitude?.toFixed(4) || t('detail.notAvailable'),
            lng: event.longitude?.toFixed(4) || t('detail.notAvailable')
          })}
        </div>
        <div className="detail-status">
          {t('detail.verified')}
        </div>
      </div>
    </aside>
  )
}
