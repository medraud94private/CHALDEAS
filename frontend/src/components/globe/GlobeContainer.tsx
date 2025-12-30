import { useRef, useCallback, useMemo, useEffect } from 'react'
import Globe, { GlobeMethods } from 'react-globe.gl'
import { useGlobeStore } from '../../store/globeStore'
import { useTimelineStore } from '../../store/timelineStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'

interface GlobeContainerProps {
  onEventClick: (event: Event) => void
}

export function GlobeContainer({ onEventClick }: GlobeContainerProps) {
  const globeRef = useRef<GlobeMethods>()
  const {
    events,
    setEvents,
    cameraPosition,
    autoRotate,
    hoveredEvent,
    setHoveredEvent,
    selectedCategories,
    minImportance,
  } = useGlobeStore()
  const { currentYear } = useTimelineStore()

  // Fetch events from API
  const { data: eventsData } = useQuery({
    queryKey: ['events', currentYear],
    queryFn: () =>
      api.get('/events', {
        params: {
          year_start: currentYear - 50,
          year_end: currentYear + 50,
          importance_min: minImportance,
          limit: 500,
        },
      }),
    select: (res) => res.data.items,
  })

  useEffect(() => {
    if (eventsData) {
      setEvents(eventsData)
    }
  }, [eventsData, setEvents])

  // Category colors
  const categoryColors: Record<string, string> = {
    battle: '#EF4444',      // Red
    war: '#DC2626',         // Dark red
    political: '#3B82F6',   // Blue
    cultural: '#8B5CF6',    // Purple
    scientific: '#10B981',  // Green
    religious: '#F59E0B',   // Amber
    general: '#6B7280',     // Gray
  }

  // Filter events for current time
  const visibleEvents = useMemo(() => {
    return events.filter((event) => {
      const start = event.date_start
      const end = event.date_end || start

      // Check time range (within 50 years for more visibility)
      if (Math.abs(currentYear - start) > 50 && currentYear < start) return false
      if (Math.abs(currentYear - end) > 50 && currentYear > end) return false

      // Check category filter (handle both string and object category)
      if (selectedCategories.length > 0 && event.category) {
        const catId = typeof event.category === 'string'
          ? event.category
          : event.category.id
        if (!selectedCategories.includes(catId)) return false
      }

      // Check importance filter
      if (event.importance < minImportance) return false

      return true
    })
  }, [events, currentYear, selectedCategories, minImportance])

  // Marker color based on category
  const getMarkerColor = useCallback((event: Event) => {
    const cat = typeof event.category === 'string'
      ? event.category
      : event.category?.slug || 'general'
    return categoryColors[cat] || '#3B82F6'
  }, [])

  // Marker size based on importance
  const getMarkerSize = useCallback((event: Event) => {
    return 0.3 + event.importance * 0.15
  }, [])

  // Marker altitude (pulse effect for hovered)
  const getMarkerAltitude = useCallback(
    (event: Event) => {
      return hoveredEvent?.id === event.id ? 0.05 : 0.01
    },
    [hoveredEvent]
  )

  return (
    <div className="globe-container">
      <Globe
        ref={globeRef}
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        // Points Layer (Event Markers)
        pointsData={visibleEvents}
        pointLat={(d: Event) => d.latitude || d.location?.latitude || 0}
        pointLng={(d: Event) => d.longitude || d.location?.longitude || 0}
        pointColor={getMarkerColor}
        pointAltitude={getMarkerAltitude}
        pointRadius={getMarkerSize}
        pointLabel={(d: Event) => `
          <div class="marker-tooltip">
            <strong>${d.title}</strong><br/>
            <span>${d.date_display}</span>
            ${d.category ? `<br/><span style="color:${d.category.color}">${d.category.name}</span>` : ''}
          </div>
        `}
        onPointClick={(point) => onEventClick(point as Event)}
        onPointHover={(point) => setHoveredEvent(point as Event | null)}
        // Camera settings
        pointOfView={cameraPosition}
        // Animation
        animateIn={true}
        // Auto rotation
        // Note: autoRotate controlled via ref in production
      />
    </div>
  )
}
