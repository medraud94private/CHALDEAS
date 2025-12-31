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

export function GlobeContainer({ onEventClick, globeStyle = 'default' }: GlobeContainerProps) {
  const globeRef = useRef<GlobeMethods>()
  const {
    events,
    setEvents,
    hoveredEvent,
    setHoveredEvent,
    selectedCategories,
    minImportance,
    selectedEvent,
    highlightedLocations,
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
          limit: 1000,  // Backend max limit
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
    const TIME_RANGE = 10 // Show events within ±10 years

    return events.filter((event) => {
      const start = event.date_start
      const end = event.date_end || start

      // Check time range: current year should be within [start - TIME_RANGE, end + TIME_RANGE]
      if (currentYear < start - TIME_RANGE || currentYear > end + TIME_RANGE) {
        return false
      }

      // Check category filter (handle both string and object category)
      if (selectedCategories.length > 0 && event.category) {
        const catId = typeof event.category === 'string'
          ? event.category
          : event.category.id
        if (!selectedCategories.includes(catId as number)) return false
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

  // Arcs data for connections (optional) - reserved for future use
  // const arcsData = useMemo(() => {
  //   // Create arcs between related events
  //   return []
  // }, [visibleEvents])

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
        pointLat={(d) => (d as Event).latitude || (d as Event).location?.latitude || 0}
        pointLng={(d) => (d as Event).longitude || (d as Event).location?.longitude || 0}
        pointColor={(d) => getMarkerColor(d as Event)}
        pointAltitude={(d) => getMarkerAltitude(d as Event)}
        pointRadius={(d) => getMarkerSize(d as Event)}
        pointLabel={(d) => {
          const event = d as Event
          return `
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
              ${event.title}
            </div>
            <div style="color: #8ba4b4; font-size: 11px;">
              ${Math.abs(event.date_start)} ${event.date_start < 0 ? 'BC' : 'AD'}
            </div>
          </div>
        `}}
        onPointClick={(point) => onEventClick(point as Event)}
        onPointHover={(point) => setHoveredEvent(point as Event | null)}
        // Ring effect - for focused location and highlighted locations from SHEBA search
        ringsData={[
          ...(focusedLocation ? [{ ...focusedLocation, type: 'focused' }] : []),
          ...highlightedLocations.map(loc => ({ lat: loc.lat, lng: loc.lng, title: loc.title, type: 'highlighted' })),
          ...(isHoloStyle && !focusedLocation && highlightedLocations.length === 0 ? [{ lat: 0, lng: 0, type: 'ambient' }] : [])
        ]}
        ringColor={(d: { type?: string }) =>
          d.type === 'focused' ? 'rgba(255, 51, 102, 0.6)' :
          d.type === 'highlighted' ? 'rgba(255, 215, 0, 0.8)' :  // Golden glow for SHEBA results
          'rgba(0, 212, 255, 0.3)'
        }
        ringMaxRadius={(d: { type?: string }) => d.type === 'ambient' ? 90 : 8}
        ringPropagationSpeed={(d: { type?: string }) => d.type === 'ambient' ? 2 : 3}
        ringRepeatPeriod={(d: { type?: string }) => d.type === 'ambient' ? 2000 : 800}
        // Custom HTML elements for highlighted location labels
        htmlElementsData={highlightedLocations}
        htmlLat={(d) => (d as { lat: number }).lat}
        htmlLng={(d) => (d as { lng: number }).lng}
        htmlAltitude={0.05}
        htmlElement={(d) => {
          const loc = d as { lat: number; lng: number; title: string }
          const el = document.createElement('div')
          el.innerHTML = `
            <div style="
              background: rgba(255, 215, 0, 0.9);
              color: #000;
              padding: 4px 8px;
              border-radius: 4px;
              font-size: 11px;
              font-weight: bold;
              white-space: nowrap;
              cursor: pointer;
              box-shadow: 0 0 10px rgba(255, 215, 0, 0.8);
              animation: pulse 1.5s infinite;
            ">
              📍 ${loc.title}
            </div>
          `
          el.style.pointerEvents = 'auto'
          el.onclick = () => {
            // Find and click the event if it exists
            const event = events.find(e =>
              Math.abs((e.latitude || 0) - loc.lat) < 0.1 &&
              Math.abs((e.longitude || 0) - loc.lng) < 0.1
            )
            if (event) onEventClick(event)
          }
          return el
        }}
      />
    </div>
  )
}
