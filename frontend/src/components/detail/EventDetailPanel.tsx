/**
 * EventDetailPanel - FGO-style event detail with tabs (Overview / Connections)
 */
import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'

interface Props {
  event: Event | null
  allEvents: Event[]
  onClose: () => void
  onEventClick: (event: Event) => void
  onAskSheba: (query: string) => void
  onPersonClick?: (personId: number) => void
  onLocationClick?: (locationId: number) => void
}

interface Connection {
  id: number
  event_a: { id: number; title: string; date_start: number | null }
  event_b: { id: number; title: string; date_start: number | null }
  direction: string
  layer_type: string
  connection_type: string | null
  strength_score: number
}

type TabType = 'overview' | 'connections'

// Chain navigation state
interface ChainNav {
  mode: 'person' | 'location' | 'causal' | null
  entityId: number | null
  entityName: string | null
  events: Array<{ id: number; title: string; date_start: number | null }>
  currentIndex: number
}

export function EventDetailPanel({
  event,
  allEvents,
  onClose,
  onEventClick,
  onAskSheba,
  onPersonClick,
  onLocationClick
}: Props) {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [chainNav, setChainNav] = useState<ChainNav>({
    mode: null,
    entityId: null,
    entityName: null,
    events: [],
    currentIndex: -1
  })

  // Fetch connections for current event
  const { data: connectionsData, isLoading: connectionsLoading } = useQuery({
    queryKey: ['event-connections', event?.id],
    queryFn: () => api.get(`/chains/event/${event?.id}/connections`, {
      params: { limit: 50 }
    }),
    enabled: !!event?.id && activeTab === 'connections',
    select: (res) => res.data,
  })

  // Format year display
  const formatYear = (year: number | null) => {
    if (year === null) return '?'
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

  // Get connection type color
  const getTypeColor = (type: string | null) => {
    const colors: Record<string, string> = {
      causes: '#ef4444',
      leads_to: '#f97316',
      follows: '#3b82f6',
      part_of: '#a855f7',
      concurrent: '#22c55e',
      related: '#6b7280',
    }
    return colors[type || ''] || '#6b7280'
  }

  // Get direction symbol
  const getDirectionSymbol = (conn: Connection) => {
    if (!event) return '—'
    const isEventA = conn.event_a.id === event.id

    switch (conn.direction) {
      case 'forward': return isEventA ? '→' : '←'
      case 'backward': return isEventA ? '←' : '→'
      case 'bidirectional': return '↔'
      default: return '—'
    }
  }

  // Fetch chain events for navigation
  const { data: personChainData } = useQuery({
    queryKey: ['person-chain', chainNav.entityId],
    queryFn: () => api.get(`/chains/person/${chainNav.entityId}`),
    enabled: chainNav.mode === 'person' && !!chainNav.entityId,
    select: (res) => res.data,
  })

  const { data: locationChainData } = useQuery({
    queryKey: ['location-chain', chainNav.entityId],
    queryFn: () => api.get(`/chains/location/${chainNav.entityId}`),
    enabled: chainNav.mode === 'location' && !!chainNav.entityId,
    select: (res) => res.data,
  })

  // Update chain events when data is loaded
  useMemo(() => {
    if (chainNav.mode === 'person' && personChainData?.connections) {
      // Extract unique events from connections
      const eventsMap = new Map<number, { id: number; title: string; date_start: number | null }>()
      for (const conn of personChainData.connections) {
        if (!eventsMap.has(conn.event_a.id)) {
          eventsMap.set(conn.event_a.id, { id: conn.event_a.id, title: conn.event_a.title, date_start: conn.event_a.year })
        }
        if (!eventsMap.has(conn.event_b.id)) {
          eventsMap.set(conn.event_b.id, { id: conn.event_b.id, title: conn.event_b.title, date_start: conn.event_b.year })
        }
      }
      const events = Array.from(eventsMap.values()).sort((a, b) => (a.date_start || 0) - (b.date_start || 0))
      const currentIndex = events.findIndex(e => e.id === event?.id)
      setChainNav(prev => ({
        ...prev,
        entityName: personChainData.person?.name || prev.entityName,
        events,
        currentIndex: currentIndex >= 0 ? currentIndex : 0
      }))
    }
  }, [personChainData, chainNav.mode, event?.id])

  useMemo(() => {
    if (chainNav.mode === 'location' && locationChainData?.connections) {
      const eventsMap = new Map<number, { id: number; title: string; date_start: number | null }>()
      for (const conn of locationChainData.connections) {
        if (!eventsMap.has(conn.event_a.id)) {
          eventsMap.set(conn.event_a.id, { id: conn.event_a.id, title: conn.event_a.title, date_start: conn.event_a.year })
        }
        if (!eventsMap.has(conn.event_b.id)) {
          eventsMap.set(conn.event_b.id, { id: conn.event_b.id, title: conn.event_b.title, date_start: conn.event_b.year })
        }
      }
      const events = Array.from(eventsMap.values()).sort((a, b) => (a.date_start || 0) - (b.date_start || 0))
      const currentIndex = events.findIndex(e => e.id === event?.id)
      setChainNav(prev => ({
        ...prev,
        entityName: locationChainData.location?.name || prev.entityName,
        events,
        currentIndex: currentIndex >= 0 ? currentIndex : 0
      }))
    }
  }, [locationChainData, chainNav.mode, event?.id])

  // Start chain navigation
  const startChainNav = (mode: 'person' | 'location', entityId: number, entityName: string) => {
    setChainNav({
      mode,
      entityId,
      entityName,
      events: [],
      currentIndex: -1
    })
    setActiveTab('connections')
  }

  // Navigate to previous/next event in chain
  const navigateChain = (direction: 'prev' | 'next') => {
    if (chainNav.events.length === 0) return

    const newIndex = direction === 'prev'
      ? Math.max(0, chainNav.currentIndex - 1)
      : Math.min(chainNav.events.length - 1, chainNav.currentIndex + 1)

    if (newIndex !== chainNav.currentIndex) {
      const targetEvent = chainNav.events[newIndex]
      const fullEvent = allEvents.find(e => e.id === targetEvent.id)
      if (fullEvent) {
        setChainNav(prev => ({ ...prev, currentIndex: newIndex }))
        onEventClick(fullEvent)
      }
    }
  }

  // Exit chain navigation
  const exitChainNav = () => {
    setChainNav({
      mode: null,
      entityId: null,
      entityName: null,
      events: [],
      currentIndex: -1
    })
  }

  // Get the "other" event in the connection
  const getOtherEvent = (conn: Connection) => {
    if (!event) return null
    return conn.event_a.id === event.id ? conn.event_b : conn.event_a
  }

  // Handle clicking a connected event
  const handleConnectionClick = async (conn: Connection) => {
    const otherEvent = getOtherEvent(conn)
    if (!otherEvent) return

    // Try to find in allEvents first
    const fullEvent = allEvents.find(e => e.id === otherEvent.id)
    if (fullEvent) {
      onEventClick(fullEvent)
      return
    }

    // If not in allEvents, fetch from API
    try {
      const res = await api.get(`/events/${otherEvent.id}`)
      if (res.data) {
        onEventClick(res.data)
      }
    } catch (err) {
      console.error('Failed to fetch event:', otherEvent.id, err)
    }
  }

  // Group connections by type
  const groupedConnections = useMemo(() => {
    if (!connectionsData?.items) return {}

    const groups: Record<string, Connection[]> = {}
    for (const conn of connectionsData.items) {
      const type = conn.connection_type || 'unclassified'
      if (!groups[type]) groups[type] = []
      groups[type].push(conn)
    }
    return groups
  }, [connectionsData])

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

      {/* Chain Navigation Bar */}
      {chainNav.mode && chainNav.events.length > 0 && (
        <div className="chain-nav-bar">
          <div className="chain-nav-info">
            <span className={`chain-nav-mode ${chainNav.mode}`}>
              {chainNav.mode === 'person' ? '👤' : '📍'}
              {chainNav.entityName}
            </span>
            <span className="chain-nav-progress">
              {chainNav.currentIndex + 1} / {chainNav.events.length}
            </span>
          </div>
          <div className="chain-nav-controls">
            <button
              className="chain-nav-btn"
              onClick={() => navigateChain('prev')}
              disabled={chainNav.currentIndex <= 0}
              title={t('detail.previousEvent', 'Previous Event')}
            >
              ← {t('detail.prev', 'Prev')}
            </button>
            <button
              className="chain-nav-btn"
              onClick={() => navigateChain('next')}
              disabled={chainNav.currentIndex >= chainNav.events.length - 1}
              title={t('detail.nextEvent', 'Next Event')}
            >
              {t('detail.next', 'Next')} →
            </button>
            <button
              className="chain-nav-exit"
              onClick={exitChainNav}
              title={t('detail.exitChain', 'Exit Chain Navigation')}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="detail-tabs">
        <button
          className={`detail-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          {t('detail.tabs.overview', 'Overview')}
        </button>
        <button
          className={`detail-tab ${activeTab === 'connections' ? 'active' : ''}`}
          onClick={() => setActiveTab('connections')}
        >
          {t('detail.tabs.connections', 'Connections')}
          {connectionsData?.total ? ` (${connectionsData.total})` : ''}
        </button>
      </div>

      {/* Content */}
      <div className="detail-content">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <>
            {/* 4 Elements Grid: WHO / WHERE / WHEN / WHAT */}
            <div className="four-elements-grid">
              {/* WHEN */}
              <div className="element-card when">
                <div className="element-label">WHEN</div>
                <div className="element-value">
                  <span className="element-main">{Math.abs(event.date_start)}</span>
                  <span className="element-sub">{event.date_start < 0 ? 'BCE' : 'CE'}</span>
                </div>
                {event.date_end && event.date_end !== event.date_start && (
                  <div className="element-extra">
                    ~ {Math.abs(event.date_end)} {event.date_end < 0 ? 'BCE' : 'CE'}
                  </div>
                )}
              </div>

              {/* WHERE */}
              <div className="element-card where">
                <div className="element-label">WHERE</div>
                {(event.location || event.locations?.[0]) ? (
                  <>
                    <div className="element-value">
                      <span
                        className="element-main element-clickable"
                        onClick={() => {
                          const loc = event.location || event.locations?.[0]
                          if (loc) {
                            if (onLocationClick) {
                              onLocationClick(loc.id)
                            } else {
                              startChainNav('location', loc.id, loc.name)
                            }
                          }
                        }}
                        title={t('detail.followLocationChain', 'See history of this place')}
                      >
                        {event.location?.name || event.locations?.[0]?.name}
                      </span>
                    </div>
                    {(event.location?.country || event.locations?.[0]?.country) && (
                      <div className="element-extra">
                        {event.location?.country || event.locations?.[0]?.country}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="element-value">
                    <span className="element-main element-unknown">Unknown</span>
                  </div>
                )}
              </div>

              {/* WHO */}
              <div className="element-card who">
                <div className="element-label">WHO</div>
                {event.persons && event.persons.length > 0 ? (
                  <>
                    <div className="element-value">
                      <span
                        className="element-main element-clickable"
                        onClick={() => {
                          if (onPersonClick) {
                            onPersonClick(event.persons![0].id)
                          } else {
                            startChainNav('person', event.persons![0].id, event.persons![0].name)
                          }
                        }}
                        title={t('detail.followPersonChain', 'Follow this person\'s story')}
                      >
                        {event.persons[0].name}
                      </span>
                    </div>
                    {event.persons.length > 1 && (
                      <div className="element-extra">
                        +{event.persons.length - 1} {t('detail.others', 'others')}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="element-value">
                    <span className="element-main element-unknown">Various</span>
                  </div>
                )}
              </div>

              {/* WHAT (Category) */}
              <div className="element-card what">
                <div className="element-label">WHAT</div>
                <div className="element-value">
                  <span className={`element-main element-category ${category || 'general'}`}>
                    {t(`categories.${category || 'general'}`, category || 'Event')}
                  </span>
                </div>
              </div>
            </div>

            {/* Description */}
            <div className="detail-section">
              <div className="detail-section-header">{t('detail.description', 'Description')}</div>
              <p className="detail-description">
                {event.description || t('detail.pendingDescription')}
              </p>
            </div>

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
          </>
        )}

        {/* Connections Tab */}
        {activeTab === 'connections' && (
          <div className="connections-tab">
            {connectionsLoading && (
              <div className="connections-loading">
                {t('detail.loadingConnections', 'Loading connections...')}
              </div>
            )}

            {!connectionsLoading && connectionsData?.total === 0 && (
              <div className="connections-empty">
                {t('detail.noConnections', 'No historical connections found for this event.')}
              </div>
            )}

            {!connectionsLoading && Object.keys(groupedConnections).length > 0 && (
              <div className="connections-list">
                {Object.entries(groupedConnections).map(([type, conns]) => (
                  <div key={type} className="connection-group">
                    <div
                      className="connection-group-header"
                      style={{ borderLeftColor: getTypeColor(type) }}
                    >
                      <span className="connection-type-label">{type}</span>
                      <span className="connection-count">{conns.length}</span>
                    </div>

                    {conns.slice(0, 10).map((conn) => {
                      const otherEvent = getOtherEvent(conn)
                      if (!otherEvent) return null

                      return (
                        <div
                          key={conn.id}
                          className="connection-item"
                          onClick={() => handleConnectionClick(conn)}
                        >
                          <span className="connection-direction">
                            {getDirectionSymbol(conn)}
                          </span>
                          <div className="connection-event">
                            <span className="connection-event-title">
                              {otherEvent.title}
                            </span>
                            <span className="connection-event-year">
                              {formatYear(otherEvent.date_start)}
                            </span>
                          </div>
                          <span
                            className="connection-strength"
                            title={`Strength: ${conn.strength_score.toFixed(1)}`}
                          >
                            {conn.strength_score >= 10 ? '●●●' :
                             conn.strength_score >= 5 ? '●●○' : '●○○'}
                          </span>
                        </div>
                      )
                    })}

                    {conns.length > 10 && (
                      <div className="connection-more">
                        +{conns.length - 10} more
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* Connection Stats Summary */}
            {!connectionsLoading && connectionsData?.total > 0 && (
              <div className="connections-summary">
                <span>{t('detail.totalConnections', 'Total')}: {connectionsData.total}</span>
                {connectionsData.by_layer && (
                  <span className="connections-by-layer">
                    {Object.entries(connectionsData.by_layer).map(([layer, count]) => (
                      <span key={layer} className="layer-badge">
                        {layer}: {count as number}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            )}
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
