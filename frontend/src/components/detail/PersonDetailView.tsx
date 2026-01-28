/**
 * PersonDetailView - FGO-style Person Detail with Timeline
 *
 * Shows a person's biography, timeline of events, and connected persons.
 */
import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, personsApi } from '../../api/client'
import { StoryModal } from '../story'
import { ReportButton, SourceBadge } from '../common'
import { useSettingsStore, getLocalizedText } from '../../store/settingsStore'
import { trackEvent, AnalyticsEvents } from '../../lib/analytics'
import type { Event, PersonSourceList } from '../../types'
import './EntityDetailView.css'

interface PersonInfo {
  id: number
  name: string
  name_ko?: string
  name_ja?: string
  birth_year?: number
  death_year?: number
  role?: string
  certainty?: string
  biography?: string
  biography_ko?: string
  biography_ja?: string
  biography_source?: string
  biography_source_url?: string
}

interface ChainEvent {
  id: number
  title: string
  year: number | null
}

interface ChainConnection {
  id: number
  event_a: ChainEvent
  event_b: ChainEvent
  direction: string
  type: string | null
  strength: number
}

interface PersonRelation {
  id: number
  name: string
  name_ko?: string
  birth_year?: number
  death_year?: number
  strength: number
  time_distance?: number
  relationship_type?: string
  is_bidirectional: number
}

interface Props {
  personId: number
  onClose: () => void
  onEventClick: (event: Event) => void
  onPersonClick: (personId: number) => void
}

export function PersonDetailView({ personId, onClose, onEventClick, onPersonClick }: Props) {
  const [isStoryOpen, setIsStoryOpen] = useState(false)
  const { preferredLanguage } = useSettingsStore()

  // Track person view
  useEffect(() => {
    trackEvent(AnalyticsEvents.PERSON_VIEWED, { person_id: personId })
  }, [personId])

  // Fetch person details
  const { data: person, isLoading: personLoading } = useQuery<PersonInfo>({
    queryKey: ['person-detail', personId],
    queryFn: async () => {
      const res = await api.get(`/persons/${personId}`)
      return res.data
    },
  })

  // Fetch person chain (connections)
  const { data: chainData } = useQuery({
    queryKey: ['person-chain', personId],
    queryFn: async () => {
      const res = await api.get(`/chains/person/${personId}`)
      return res.data
    },
  })

  // Fetch related persons with strength
  const { data: relationsData } = useQuery<{ relations: PersonRelation[]; total: number }>({
    queryKey: ['person-relations', personId],
    queryFn: async () => {
      const res = await api.get(`/persons/${personId}/relations?limit=20&min_strength=5`)
      return res.data
    },
  })

  // Fetch sources (books) mentioning this person
  const { data: sourcesData } = useQuery<PersonSourceList>({
    queryKey: ['person-sources', personId],
    queryFn: async () => {
      const res = await personsApi.getSources(personId, { limit: 10, include_contexts: true, max_contexts: 2 })
      return res.data
    },
  })

  // Extract unique events from chain, sorted by year
  const timelineEvents = useMemo(() => {
    if (!chainData?.connections) return []

    const eventsMap = new Map<number, ChainEvent>()
    for (const conn of chainData.connections as ChainConnection[]) {
      if (!eventsMap.has(conn.event_a.id)) {
        eventsMap.set(conn.event_a.id, conn.event_a)
      }
      if (!eventsMap.has(conn.event_b.id)) {
        eventsMap.set(conn.event_b.id, conn.event_b)
      }
    }

    return Array.from(eventsMap.values())
      .sort((a, b) => (a.year || 0) - (b.year || 0))
  }, [chainData])

  // Use relations from API (with strength)
  const relatedPersons = useMemo(() => {
    if (!relationsData?.relations) return []
    return relationsData.relations
  }, [relationsData])

  // Format strength for display
  const formatStrength = (strength: number): string => {
    if (strength >= 1000) return `${(strength / 1000).toFixed(1)}k`
    if (strength >= 100) return strength.toFixed(0)
    return strength.toFixed(1)
  }

  // Get strength level for styling
  const getStrengthLevel = (strength: number): string => {
    if (strength >= 100) return 'very-strong'
    if (strength >= 30) return 'strong'
    if (strength >= 10) return 'medium'
    return 'weak'
  }

  const formatYear = (year: number | null | undefined) => {
    if (year === null || year === undefined) return '?'
    if (year < 0) return `${Math.abs(year)} BCE`
    return `${year} CE`
  }

  const handleEventClick = async (eventId: number) => {
    try {
      const res = await api.get(`/events/${eventId}`)
      if (res.data) {
        onEventClick(res.data)
      }
    } catch (err) {
      console.error('Failed to fetch event:', eventId, err)
    }
  }

  if (personLoading) {
    return (
      <div className="entity-detail-view">
        <div className="entity-loading">Loading...</div>
      </div>
    )
  }

  if (!person) {
    return (
      <div className="entity-detail-view">
        <div className="entity-error">Person not found</div>
      </div>
    )
  }

  return (
    <div className="entity-detail-view person-view">
      {/* Header */}
      <div className="entity-header">
        <button className="entity-close" onClick={onClose}>✕</button>
        <div className="entity-icon person">👤</div>
        <div className="entity-title-section">
          <h2 className="entity-name">{person.name}</h2>
          {person.name_ko && <div className="entity-name-alt">{person.name_ko}</div>}
        </div>
      </div>

      {/* Life Span */}
      <div className="entity-lifespan">
        <div className="lifespan-dates">
          <span className="lifespan-birth">{formatYear(person.birth_year)}</span>
          <span className="lifespan-separator">—</span>
          <span className="lifespan-death">{formatYear(person.death_year)}</span>
        </div>
        {person.role && <div className="entity-role">{person.role}</div>}
      </div>

      {/* Stats */}
      <div className="entity-stats">
        <div className="stat-item">
          <span className="stat-value">{timelineEvents.length}</span>
          <span className="stat-label">Events</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{relatedPersons.length}</span>
          <span className="stat-label">Relations</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{chainData?.total_connections || 0}</span>
          <span className="stat-label">Links</span>
        </div>
      </div>

      {/* Story Button */}
      {timelineEvents.length > 0 && (
        <button
          className="entity-story-btn"
          onClick={() => setIsStoryOpen(true)}
        >
          <span className="story-btn-icon">🗺</span>
          <span className="story-btn-text">View Story</span>
          <span className="story-btn-arrow">→</span>
        </button>
      )}

      {/* Biography */}
      {(() => {
        const biography = getLocalizedText(person as unknown as Record<string, unknown>, 'biography', preferredLanguage)
        return biography ? (
          <div className="entity-description">
            <p>{biography}</p>
            <div className="description-source">
              <SourceBadge
                source={person.biography_source}
                sourceUrl={person.biography_source_url}
              />
            </div>
          </div>
        ) : null
      })()}

      {/* Timeline */}
      <div className="entity-section">
        <div className="section-header">
          <span className="section-icon">📅</span>
          <span className="section-title">Timeline</span>
        </div>
        <div className="timeline-list">
          {timelineEvents.length > 0 ? (
            timelineEvents.map((event, index) => (
              <div
                key={event.id}
                className="timeline-item"
                onClick={() => handleEventClick(event.id)}
                style={{ animationDelay: `${index * 0.05}s` }}
              >
                <div className="timeline-dot" />
                <div className="timeline-year">{formatYear(event.year)}</div>
                <div className="timeline-title">{event.title}</div>
              </div>
            ))
          ) : (
            <div className="timeline-empty">No events found</div>
          )}
        </div>
      </div>

      {/* Related Persons with Strength */}
      {relatedPersons.length > 0 && (
        <div className="entity-section">
          <div className="section-header">
            <span className="section-icon">🔗</span>
            <span className="section-title">Related Figures</span>
          </div>
          <div className="connected-list">
            {relatedPersons.map((p) => (
              <div
                key={p.id}
                className={`connected-item person strength-${getStrengthLevel(p.strength)}`}
                onClick={() => onPersonClick(p.id)}
              >
                <div className="connected-main">
                  <span className="connected-name">{p.name}</span>
                  {p.time_distance && p.time_distance > 0 && (
                    <span className="connected-era historical">historical ref</span>
                  )}
                </div>
                <div className="connected-strength">
                  <span className="strength-value">{formatStrength(p.strength)}</span>
                  <span className="strength-bar">
                    <span
                      className="strength-fill"
                      style={{ width: `${Math.min(100, (p.strength / 100) * 100)}%` }}
                    />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sources (Books) mentioning this person */}
      {sourcesData && sourcesData.sources.length > 0 && (
        <div className="entity-section">
          <div className="section-header">
            <span className="section-icon">📚</span>
            <span className="section-title">Mentioned in Books</span>
            <span className="section-count">{sourcesData.total}</span>
          </div>
          <div className="sources-list">
            {sourcesData.sources.map((source) => (
              <div key={source.id} className="source-item">
                <div className="source-header">
                  <span className="source-title">{source.title || source.name}</span>
                  <span className="source-mentions">{source.mention_count}x</span>
                </div>
                {source.author && (
                  <div className="source-author">by {source.author}</div>
                )}
                {source.mentions.length > 0 && (
                  <div className="source-contexts">
                    {source.mentions.slice(0, 2).map((mention, idx) => (
                      <div key={idx} className="mention-context">
                        <span className="mention-quote">"{mention.context_text?.slice(0, 150)}..."</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="entity-footer">
        <span className="entity-id">PERSON #{personId}</span>
        {person.certainty && (
          <span className={`entity-certainty ${person.certainty}`}>
            {person.certainty}
          </span>
        )}
        <ReportButton entityType="person" entityId={personId} />
      </div>

      {/* Story Modal */}
      <StoryModal
        isOpen={isStoryOpen}
        personId={personId}
        onClose={() => setIsStoryOpen(false)}
        onEventClick={(eventId) => {
          setIsStoryOpen(false)
          handleEventClick(eventId)
        }}
      />
    </div>
  )
}
