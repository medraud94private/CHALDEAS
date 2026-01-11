/**
 * PersonDetailView - FGO-style Person Detail with Timeline
 *
 * Shows a person's biography, timeline of events, and connected persons.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'
import './EntityDetailView.css'

interface PersonInfo {
  id: number
  name: string
  name_ko?: string
  birth_year?: number
  death_year?: number
  role?: string
  certainty?: string
  description?: string
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

interface Props {
  personId: number
  onClose: () => void
  onEventClick: (event: Event) => void
  onPersonClick: (personId: number) => void
}

export function PersonDetailView({ personId, onClose, onEventClick, onPersonClick }: Props) {
  // Fetch person details
  const { data: person, isLoading: personLoading } = useQuery<PersonInfo>({
    queryKey: ['person-detail', personId],
    queryFn: async () => {
      const res = await api.get(`/persons/${personId}`)
      return res.data
    },
  })

  // Fetch person's events
  const { data: eventsData } = useQuery({
    queryKey: ['person-events', personId],
    queryFn: async () => {
      const res = await api.get(`/persons/${personId}/events`)
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

  // Find connected persons (from events that share this person)
  const connectedPersons = useMemo(() => {
    if (!eventsData?.events) return []

    const personsMap = new Map<number, { id: number; name: string; count: number }>()
    for (const event of eventsData.events) {
      if (event.persons) {
        for (const p of event.persons) {
          if (p.id !== personId) {
            const existing = personsMap.get(p.id)
            if (existing) {
              existing.count++
            } else {
              personsMap.set(p.id, { id: p.id, name: p.name, count: 1 })
            }
          }
        }
      }
    }

    return Array.from(personsMap.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  }, [eventsData, personId])

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
          <span className="stat-value">{connectedPersons.length}</span>
          <span className="stat-label">Connected</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{chainData?.total_connections || 0}</span>
          <span className="stat-label">Links</span>
        </div>
      </div>

      {/* Description */}
      {person.description && (
        <div className="entity-description">
          <p>{person.description}</p>
        </div>
      )}

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

      {/* Connected Persons */}
      {connectedPersons.length > 0 && (
        <div className="entity-section">
          <div className="section-header">
            <span className="section-icon">🔗</span>
            <span className="section-title">Connected Figures</span>
          </div>
          <div className="connected-list">
            {connectedPersons.map((p) => (
              <div
                key={p.id}
                className="connected-item person"
                onClick={() => onPersonClick(p.id)}
              >
                <span className="connected-name">{p.name}</span>
                <span className="connected-count">{p.count} shared</span>
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
      </div>
    </div>
  )
}
