/**
 * LocationDetailView - FGO-style Location Detail with History
 *
 * Shows a location's information, historical events, and connected locations.
 */
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'
import './EntityDetailView.css'

interface LocationInfo {
  id: number
  name: string
  name_ko?: string
  modern_name?: string
  country?: string
  region?: string
  latitude?: number
  longitude?: number
  type?: string
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
  locationId: number
  onClose: () => void
  onEventClick: (event: Event) => void
  onLocationClick: (locationId: number) => void
}

export function LocationDetailView({ locationId, onClose, onEventClick, onLocationClick: _onLocationClick }: Props) {
  // Note: _onLocationClick reserved for future connected locations navigation
  void _onLocationClick

  // Fetch location details from DB
  const { data: location, isLoading: locationLoading } = useQuery<LocationInfo>({
    queryKey: ['location-detail', locationId],
    queryFn: async () => {
      // Fetch location info from chain API
      const dbRes = await api.get(`/chains/location/${locationId}`)
      return dbRes.data?.location || { id: locationId, name: 'Unknown Location' }
    },
  })

  // Fetch location chain (connections and events)
  const { data: chainData, isLoading: chainLoading } = useQuery({
    queryKey: ['location-chain', locationId],
    queryFn: async () => {
      const res = await api.get(`/chains/location/${locationId}`)
      return res.data
    },
  })

  // Extract unique events from chain, sorted by year
  const historyEvents = useMemo(() => {
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

  // Calculate time span
  const timeSpan = useMemo(() => {
    if (historyEvents.length === 0) return null
    const years = historyEvents.filter(e => e.year !== null).map(e => e.year as number)
    if (years.length === 0) return null
    return {
      earliest: Math.min(...years),
      latest: Math.max(...years)
    }
  }, [historyEvents])

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

  if (locationLoading || chainLoading) {
    return (
      <div className="entity-detail-view">
        <div className="entity-loading">Loading...</div>
      </div>
    )
  }

  return (
    <div className="entity-detail-view location-view">
      {/* Header */}
      <div className="entity-header">
        <button className="entity-close" onClick={onClose}>✕</button>
        <div className="entity-icon location">📍</div>
        <div className="entity-title-section">
          <h2 className="entity-name">{location?.name || chainData?.location?.name || 'Unknown'}</h2>
          {(location?.name_ko || location?.modern_name) && (
            <div className="entity-name-alt">
              {location?.name_ko || location?.modern_name}
            </div>
          )}
        </div>
      </div>

      {/* Location Info */}
      <div className="entity-location-info">
        {(location?.country || location?.region) && (
          <div className="location-geo">
            {location?.region && <span className="geo-region">{location.region}</span>}
            {location?.region && location?.country && <span className="geo-sep">, </span>}
            {location?.country && <span className="geo-country">{location.country}</span>}
          </div>
        )}
        {location?.type && <div className="location-type">{location.type}</div>}
      </div>

      {/* Stats */}
      <div className="entity-stats">
        <div className="stat-item">
          <span className="stat-value">{historyEvents.length}</span>
          <span className="stat-label">Events</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{chainData?.total_connections || 0}</span>
          <span className="stat-label">Links</span>
        </div>
        {timeSpan && (
          <div className="stat-item span">
            <span className="stat-value">
              {formatYear(timeSpan.earliest)} ~ {formatYear(timeSpan.latest)}
            </span>
            <span className="stat-label">Time Span</span>
          </div>
        )}
      </div>

      {/* Coordinates */}
      {(location?.latitude && location?.longitude) && (
        <div className="entity-coords">
          <span className="coords-icon">🌐</span>
          <span className="coords-value">
            {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
          </span>
        </div>
      )}

      {/* Description */}
      {location?.description && (
        <div className="entity-description">
          <p>{location.description}</p>
        </div>
      )}

      {/* History Timeline */}
      <div className="entity-section">
        <div className="section-header">
          <span className="section-icon">📜</span>
          <span className="section-title">History at this Location</span>
        </div>
        <div className="timeline-list">
          {historyEvents.length > 0 ? (
            historyEvents.map((event, index) => (
              <div
                key={event.id}
                className="timeline-item"
                onClick={() => handleEventClick(event.id)}
                style={{ animationDelay: `${index * 0.05}s` }}
              >
                <div className="timeline-dot location" />
                <div className="timeline-year">{formatYear(event.year)}</div>
                <div className="timeline-title">{event.title}</div>
              </div>
            ))
          ) : (
            <div className="timeline-empty">No historical events found</div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="entity-footer">
        <span className="entity-id">LOCATION #{locationId}</span>
      </div>
    </div>
  )
}
