import { useRef, useCallback, useMemo, useEffect, useState } from 'react'
import Globe, { GlobeMethods } from 'react-globe.gl'
import { useGlobeStore } from '../../store/globeStore'
import { useTimelineStore } from '../../store/timelineStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'

// GeoJSON type
interface GeoJSONFeature {
  type: string
  properties: Record<string, unknown>
  geometry: {
    type: string
    coordinates: number[][][] | number[][][][]
  }
}

interface GeoJSONData {
  type: string
  features: GeoJSONFeature[]
}

interface GlobeContainerProps {
  onEventClick: (event: Event) => void
  globeStyle?: string
  selectedEventId?: string | number | null
}

// Globe texture URLs for different styles
const GLOBE_TEXTURES: Record<string, string> = {
  default: '//unpkg.com/three-globe/example/img/earth-blue-marble.jpg',
  // FGO Part 1 style - dark with visible land
  holo: '//unpkg.com/three-globe/example/img/earth-dark.jpg',
  // Night lights style
  night: '//unpkg.com/three-globe/example/img/earth-night.jpg',
}

// Generate graticule (lat/long grid lines) data
function generateGraticules() {
  const graticules: Array<{ coords: [number, number][] }> = []

  // Latitude lines (every 20 degrees)
  for (let lat = -80; lat <= 80; lat += 20) {
    const line: [number, number][] = []
    for (let lng = -180; lng <= 180; lng += 5) {
      line.push([lng, lat])
    }
    graticules.push({ coords: line })
  }

  // Longitude lines (every 20 degrees)
  for (let lng = -180; lng < 180; lng += 20) {
    const line: [number, number][] = []
    for (let lat = -90; lat <= 90; lat += 5) {
      line.push([lng, lat])
    }
    graticules.push({ coords: line })
  }

  return graticules
}

const GRATICULES = generateGraticules()

export function GlobeContainer({ onEventClick, globeStyle = 'default', selectedEventId }: GlobeContainerProps) {
  const globeRef = useRef<GlobeMethods>()
  const {
    events,
    setEvents,
    hoveredEvent,
    setHoveredEvent,
    selectedCategories,
    minImportance,
    selectedEvent,
  } = useGlobeStore()
  const { currentYear } = useTimelineStore()
  const [focusedLocation, setFocusedLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [countries, setCountries] = useState<GeoJSONFeature[]>([])

  // Load countries GeoJSON for HOLO mode
  useEffect(() => {
    fetch('https://raw.githubusercontent.com/vasturiano/react-globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson')
      .then(res => res.json())
      .then((data: GeoJSONData) => {
        // Filter out Antarctica
        setCountries(data.features.filter(d => d.properties.ISO_A2 !== 'AQ'))
      })
  }, [])

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

  // Auto-rotate globe
  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.controls().autoRotate = true
      globeRef.current.controls().autoRotateSpeed = 0.3
    }
  }, [])

  // Focus on selected event - rotate globe to that location
  useEffect(() => {
    if (selectedEvent && globeRef.current) {
      const lat = selectedEvent.latitude || selectedEvent.location?.latitude
      const lng = selectedEvent.longitude || selectedEvent.location?.longitude

      if (lat && lng) {
        // Stop auto-rotate when focusing
        globeRef.current.controls().autoRotate = false

        // Rotate globe to focus on the location
        globeRef.current.pointOfView({ lat, lng, altitude: 2 }, 1000)

        // Set focused location for ring effect
        setFocusedLocation({ lat, lng })
      }
    } else {
      // Resume auto-rotate when no selection
      if (globeRef.current) {
        globeRef.current.controls().autoRotate = true
      }
      setFocusedLocation(null)
    }
  }, [selectedEvent])

  // Filter events for current time
  const visibleEvents = useMemo(() => {
    return events.filter((event) => {
      const start = event.date_start
      const end = event.date_end || start

      // Check time range (within 50 years)
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

  // Marker color - cyan for most, magenta for selected/hovered
  const getMarkerColor = useCallback((event: Event) => {
    const cat = typeof event.category === 'string'
      ? event.category
      : event.category?.slug || 'general'

    // Color by category
    const colors: Record<string, string> = {
      battle: '#ff3366',     // Magenta
      war: '#ff3366',
      politics: '#4a9eff',   // Blue
      religion: '#ffa500',   // Orange
      philosophy: '#9966ff', // Purple
      science: '#00ff88',    // Green
      civilization: '#00d4ff', // Cyan
      general: '#00d4ff',
    }
    return colors[cat] || '#00d4ff'
  }, [])

  // Marker size based on importance
  const getMarkerSize = useCallback((event: Event) => {
    return 0.4 + event.importance * 0.2
  }, [])

  // Marker altitude (pulse effect for hovered)
  const getMarkerAltitude = useCallback(
    (event: Event) => {
      return hoveredEvent?.id === event.id ? 0.1 : 0.02
    },
    [hoveredEvent]
  )

  // Arcs data for connections (optional)
  const arcsData = useMemo(() => {
    // Create arcs between related events
    return []
  }, [visibleEvents])

  const globeTexture = GLOBE_TEXTURES[globeStyle] || GLOBE_TEXTURES.default
  const isHoloStyle = globeStyle === 'holo'

  // Atmosphere color based on style
  const atmosphereColor = '#00d4ff'

  const isShifted = !!selectedEvent

  return (
    <div className={`globe-container style-${globeStyle} ${isShifted ? 'shifted' : ''}`} key={globeStyle}>
      <Globe
        ref={globeRef}
        // Globe appearance based on style
        globeImageUrl={isHoloStyle ? undefined : globeTexture}
        bumpImageUrl={isHoloStyle ? undefined : "//unpkg.com/three-globe/example/img/earth-topology.png"}
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        showGlobe={true}
        showAtmosphere={true}
        atmosphereColor={atmosphereColor}
        atmosphereAltitude={isHoloStyle ? 0.2 : 0.15}
        // For holo: show graticule lines
        pathsData={isHoloStyle ? GRATICULES : []}
        pathPoints="coords"
        pathColor={() => 'rgba(0, 212, 255, 0.5)'}
        pathStroke={1.5}
        // Polygons Layer (Countries) - for HOLO mode
        polygonsData={isHoloStyle ? countries : []}
        polygonCapColor={() => 'rgba(0, 180, 220, 0.6)'}
        polygonSideColor={() => 'rgba(0, 212, 255, 0.2)'}
        polygonStrokeColor={() => 'rgba(0, 212, 255, 0.8)'}
        polygonAltitude={0.01}
        // Points Layer (Event Markers)
        pointsData={visibleEvents}
        pointLat={(d: Event) => d.latitude || d.location?.latitude || 0}
        pointLng={(d: Event) => d.longitude || d.location?.longitude || 0}
        pointColor={getMarkerColor}
        pointAltitude={getMarkerAltitude}
        pointRadius={getMarkerSize}
        pointLabel={(d: Event) => `
          <div style="
            background: rgba(10, 14, 23, 0.95);
            border: 1px solid #1a3a4a;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 12px;
            color: #d0e8f0;
            max-width: 200px;
          ">
            <div style="color: #00d4ff; font-weight: 600; margin-bottom: 4px;">
              ${d.title}
            </div>
            <div style="color: #8ba4b4; font-size: 11px;">
              ${Math.abs(d.date_start)} ${d.date_start < 0 ? 'BC' : 'AD'}
            </div>
          </div>
        `}
        onPointClick={(point) => onEventClick(point as Event)}
        onPointHover={(point) => setHoveredEvent(point as Event | null)}
        // Ring effect - at focused location or hidden
        ringsData={focusedLocation ? [focusedLocation] : (isHoloStyle ? [{ lat: 0, lng: 0 }] : [])}
        ringColor={() => focusedLocation ? 'rgba(255, 51, 102, 0.6)' : 'rgba(0, 212, 255, 0.3)'}
        ringMaxRadius={focusedLocation ? 8 : 90}
        ringPropagationSpeed={focusedLocation ? 3 : 2}
        ringRepeatPeriod={focusedLocation ? 800 : 2000}
      />
    </div>
  )
}
