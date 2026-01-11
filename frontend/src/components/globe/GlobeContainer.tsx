import { useRef, useMemo, useEffect, useState, useCallback } from 'react'
import Globe, { GlobeMethods } from 'react-globe.gl'
import { useGlobeStore } from '../../store/globeStore'
import { useTimelineStore } from '../../store/timelineStore'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Event } from '../../types'
import './GlobeHeatmap.css'

// Globe marker from new API
interface GlobeMarker {
  id: number
  type: 'event' | 'person' | 'location'
  lat: number
  lng: number
  year: number | null
  year_end: number | null
  category: string | null
  title: string
  description: string | null
  certainty: string | null
  color: string | null
}

// Globe arc from Historical Chain API
interface GlobeArc {
  connection_id: number
  source_event_id: number
  target_event_id: number
  source_title: string
  target_title: string
  source_lat: number
  source_lng: number
  target_lat: number
  target_lng: number
  source_year: number | null
  target_year: number | null
  layer_type: string
  connection_type: string | null
  direction: string
  strength: number
}

// Layer colors for Historical Chain
const LAYER_COLORS: Record<string, string> = {
  person: '#fbbf24',    // Gold
  location: '#34d399',  // Emerald
  causal: '#f472b6',    // Pink
  thematic: '#a78bfa',  // Purple
}

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
  showHeatmap?: boolean
  onHeatmapToggle?: (show: boolean) => void
}

// Cluster marker interface
interface ClusterMarker {
  id: string
  lat: number
  lng: number
  count: number
  markers: GlobeMarker[]
  isCluster: true
}

// Union type for display markers
type DisplayMarker = GlobeMarker | ClusterMarker

// Haversine distance calculation (returns km)
function haversineDistance(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371 // Earth's radius in km
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

// Simple clustering function
function clusterMarkers(markers: GlobeMarker[], clusterRadius: number): DisplayMarker[] {
  if (markers.length === 0) return []

  const clustered: DisplayMarker[] = []
  const used = new Set<number>()

  for (let i = 0; i < markers.length; i++) {
    if (used.has(i)) continue

    const marker = markers[i]
    const nearby: GlobeMarker[] = [marker]
    used.add(i)

    // Find nearby markers
    for (let j = i + 1; j < markers.length; j++) {
      if (used.has(j)) continue
      const other = markers[j]
      const dist = haversineDistance(marker.lat, marker.lng, other.lat, other.lng)
      if (dist < clusterRadius) {
        nearby.push(other)
        used.add(j)
      }
    }

    if (nearby.length === 1) {
      // Single marker, no cluster
      clustered.push(marker)
    } else {
      // Create cluster
      const avgLat = nearby.reduce((sum, m) => sum + m.lat, 0) / nearby.length
      const avgLng = nearby.reduce((sum, m) => sum + m.lng, 0) / nearby.length
      clustered.push({
        id: `cluster-${i}`,
        lat: avgLat,
        lng: avgLng,
        count: nearby.length,
        markers: nearby,
        isCluster: true,
      })
    }
  }

  return clustered
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

export function GlobeContainer({
  onEventClick,
  globeStyle = 'default',
  showHeatmap: externalShowHeatmap,
  onHeatmapToggle,
}: GlobeContainerProps) {
  const globeRef = useRef<GlobeMethods>()
  const {
    events,
    setEvents,
    selectedEvent,
    highlightedLocations,
  } = useGlobeStore()
  const { currentYear } = useTimelineStore()
  const [focusedLocation, setFocusedLocation] = useState<{ lat: number; lng: number } | null>(null)
  const [countries, setCountries] = useState<GeoJSONFeature[]>([])
  const [internalShowHeatmap, setInternalShowHeatmap] = useState(false)
  const [altitude, setAltitude] = useState(2.5) // Track zoom level for clustering
  const [enableClustering, setEnableClustering] = useState(true)

  // Use external control if provided, otherwise use internal state
  const showHeatmap = externalShowHeatmap !== undefined ? externalShowHeatmap : internalShowHeatmap

  const handleHeatmapToggle = useCallback(() => {
    const newValue = !showHeatmap
    if (onHeatmapToggle) {
      onHeatmapToggle(newValue)
    } else {
      setInternalShowHeatmap(newValue)
    }
  }, [showHeatmap, onHeatmapToggle])

  const handleClusteringToggle = useCallback(() => {
    setEnableClustering(prev => !prev)
  }, [])

  // Track altitude changes for clustering
  const handleZoom = useCallback(() => {
    if (globeRef.current) {
      const pov = globeRef.current.pointOfView()
      if (pov && typeof pov.altitude === 'number') {
        setAltitude(pov.altitude)
      }
    }
  }, [])

  // Load countries GeoJSON for HOLO mode
  useEffect(() => {
    fetch('https://raw.githubusercontent.com/vasturiano/react-globe.gl/master/example/datasets/ne_110m_admin_0_countries.geojson')
      .then(res => res.json())
      .then((data: GeoJSONData) => {
        // Filter out Antarctica
        setCountries(data.features.filter(d => d.properties.ISO_A2 !== 'AQ'))
      })
  }, [])

  // Fetch globe markers from new API (events with coordinates)
  const { data: globeMarkers } = useQuery<GlobeMarker[]>({
    queryKey: ['globe-markers', currentYear],
    queryFn: async () => {
      const res = await api.get('/globe/markers', {
        params: {
          types: 'event',
          year_start: currentYear - 100,
          year_end: currentYear + 100,
          limit: 2000,
        },
      })
      return res.data
    },
    placeholderData: undefined,
  })

  // Fetch events from API (for marker click -> event detail)
  const { data: eventsData } = useQuery({
    queryKey: ['events', currentYear],
    queryFn: () =>
      api.get('/events', {
        params: {
          year_start: currentYear - 100,
          year_end: currentYear + 100,
          limit: 1000,
        },
      }),
    select: (res) => res.data.items,
    placeholderData: undefined,
  })

  // Fetch arcs for selected event (Historical Chain connections)
  const { data: eventArcs } = useQuery<GlobeArc[]>({
    queryKey: ['globe-arcs', selectedEvent?.id],
    queryFn: async () => {
      if (!selectedEvent?.id) return []
      const res = await api.get(`/globe/arcs/${selectedEvent.id}`, {
        params: { min_strength: 3.0, limit: 30 },
      })
      return res.data
    },
    enabled: !!selectedEvent?.id,
    placeholderData: [],
  })

  // Clear events when year changes, then set new data when it arrives
  useEffect(() => {
    setEvents([])  // Clear immediately on year change
  }, [currentYear, setEvents])

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

  // Filter globe markers for current time (from new API)
  const visibleMarkers = useMemo(() => {
    if (!globeMarkers) return []
    const TIME_RANGE = 20 // Show markers within ±20 years

    return globeMarkers.filter((marker) => {
      const start = marker.year
      if (start === null) return true // Show markers without year info

      const end = marker.year_end || start

      // Check time range
      if (currentYear < start - TIME_RANGE || currentYear > end + TIME_RANGE) {
        return false
      }

      return true
    })
  }, [globeMarkers, currentYear])

  // Calculate cluster radius based on altitude (zoom level)
  // Higher altitude = larger clusters, lower altitude = smaller/no clusters
  const clusterRadius = useMemo(() => {
    if (!enableClustering) return 0
    // Scale: altitude 4+ = 800km, altitude 1 = 100km, altitude 0.5 = 0km (no clustering)
    if (altitude < 0.8) return 0 // No clustering when zoomed in
    return Math.min(1000, Math.max(100, altitude * 200))
  }, [altitude, enableClustering])

  // Apply clustering to visible markers
  const displayMarkers = useMemo<DisplayMarker[]>(() => {
    if (clusterRadius === 0 || visibleMarkers.length === 0) {
      return visibleMarkers
    }
    return clusterMarkers(visibleMarkers, clusterRadius)
  }, [visibleMarkers, clusterRadius])

  // Helper to check if marker is a cluster
  const isCluster = (d: DisplayMarker): d is ClusterMarker => {
    return 'isCluster' in d && d.isCluster === true
  }

  // Note: Arc particle effects are achieved through dynamic arcDashLength,
  // arcDashGap, and arcDashAnimateTime props based on connection strength

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
        // Points Layer (Event Markers with Clustering)
        pointsData={displayMarkers}
        pointLat={(d) => (d as DisplayMarker).lat}
        pointLng={(d) => (d as DisplayMarker).lng}
        pointColor={(d) => {
          const marker = d as DisplayMarker
          if (isCluster(marker)) {
            // Cluster color - golden gradient based on count
            const count = marker.count
            if (count > 10) return '#ff6b6b' // Red for large clusters
            if (count > 5) return '#fbbf24'  // Gold for medium
            return '#00d4ff' // Cyan for small
          }
          // Single marker - category-based colors
          const cat = (marker as GlobeMarker).category?.toLowerCase() || ''
          const colors: Record<string, string> = {
            battle: '#ff3366',
            war: '#ff3366',
            politics: '#4a9eff',
            political: '#4a9eff',
            religion: '#ffa500',
            religious: '#ffa500',
            philosophy: '#9966ff',
            science: '#00ff88',
            discovery: '#00ff88',
            civilization: '#00d4ff',
            cultural: '#a855f7',
            evenementielle: '#00d4ff',
            conjoncture: '#22c55e',
            longue_duree: '#f59e0b',
          }
          return colors[cat] || (marker as GlobeMarker).color || '#00d4ff'
        }}
        pointAltitude={(d) => {
          const marker = d as DisplayMarker
          // Clusters are slightly higher
          return isCluster(marker) ? 0.05 + Math.min(0.1, marker.count * 0.005) : 0.03
        }}
        pointRadius={(d) => {
          const marker = d as DisplayMarker
          // Cluster size based on count
          if (isCluster(marker)) {
            return Math.min(3, 1 + Math.log2(marker.count) * 0.5)
          }
          return 0.8
        }}
        pointLabel={(d) => {
          const marker = d as DisplayMarker
          if (isCluster(marker)) {
            // Cluster tooltip
            const sampleTitles = marker.markers.slice(0, 3).map(m => m.title)
            const moreCount = marker.count - 3
            return `
              <div style="
                background: rgba(10, 14, 23, 0.95);
                border: 1px solid #fbbf24;
                border-radius: 6px;
                padding: 10px 14px;
                font-size: 12px;
                color: #d0e8f0;
                max-width: 280px;
              ">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                  <span style="
                    background: #fbbf24;
                    color: #000;
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-weight: 700;
                    font-size: 13px;
                  ">${marker.count}</span>
                  <span style="color: #fbbf24; font-weight: 600;">Events in this area</span>
                </div>
                <div style="color: #8ba4b4; font-size: 11px; line-height: 1.5;">
                  ${sampleTitles.map(t => `• ${t}`).join('<br/>')}
                  ${moreCount > 0 ? `<br/><span style="color: #64748b;">+${moreCount} more...</span>` : ''}
                </div>
                <div style="color: #64748b; font-size: 10px; margin-top: 8px; font-style: italic;">
                  Click to zoom in
                </div>
              </div>
            `
          }
          // Single marker tooltip
          const singleMarker = marker as GlobeMarker
          const year = singleMarker.year
          const yearStr = year !== null
            ? `${Math.abs(year)} ${year < 0 ? 'BC' : 'AD'}`
            : ''
          return `
          <div style="
            background: rgba(10, 14, 23, 0.95);
            border: 1px solid #1a3a4a;
            border-radius: 4px;
            padding: 8px 12px;
            font-size: 12px;
            color: #d0e8f0;
            max-width: 250px;
          ">
            <div style="color: #00d4ff; font-weight: 600; margin-bottom: 4px;">
              ${singleMarker.title}
            </div>
            ${yearStr ? `<div style="color: #8ba4b4; font-size: 11px;">${yearStr}</div>` : ''}
            ${singleMarker.category ? `<div style="color: #6b7280; font-size: 10px; margin-top: 2px;">${singleMarker.category}</div>` : ''}
          </div>
        `}}
        onPointClick={(point) => {
          const marker = point as DisplayMarker
          if (isCluster(marker)) {
            // Zoom in on cluster
            if (globeRef.current) {
              globeRef.current.pointOfView({ lat: marker.lat, lng: marker.lng, altitude: Math.max(0.5, altitude * 0.4) }, 800)
            }
            return
          }
          // Single marker - open detail
          const singleMarker = marker as GlobeMarker
          const matchingEvent = eventsData?.find((e: Event) => e.id === singleMarker.id)
          if (matchingEvent) {
            onEventClick(matchingEvent)
          } else {
            console.log('Marker clicked but no matching event:', singleMarker.id, singleMarker.title)
          }
        }}
        onPointHover={() => {}}
        onZoom={handleZoom}
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
        // Historical Chain Arcs - connections between events with particle animation
        arcsData={eventArcs || []}
        arcStartLat={(d) => (d as GlobeArc).source_lat}
        arcStartLng={(d) => (d as GlobeArc).source_lng}
        arcEndLat={(d) => (d as GlobeArc).target_lat}
        arcEndLng={(d) => (d as GlobeArc).target_lng}
        arcColor={(d: object) => {
          const arc = d as GlobeArc
          const color = LAYER_COLORS[arc.layer_type] || '#00d4ff'
          // Create glowing gradient effect
          return [`${color}ff`, `${color}88`, `${color}ff`]
        }}
        arcStroke={(d: object) => {
          const arc = d as GlobeArc
          // Dynamic stroke width based on strength (1.0 to 3.5)
          return Math.min(3.5, Math.max(1.0, arc.strength / 7))
        }}
        arcDashLength={(d: object) => {
          const arc = d as GlobeArc
          // Dynamic dash length - shorter for person links, longer for causal
          const baseLength = arc.layer_type === 'person' ? 0.15 : arc.layer_type === 'causal' ? 0.4 : 0.25
          return baseLength + (arc.strength / 50)
        }}
        arcDashGap={(d: object) => {
          const arc = d as GlobeArc
          // Dynamic gap - creates particle-like effect
          const baseGap = arc.layer_type === 'person' ? 0.3 : 0.15
          return baseGap
        }}
        arcDashAnimateTime={(d: object) => {
          const arc = d as GlobeArc
          // Faster animation for stronger connections (600-2500ms)
          const baseSpeed = 2500 - (arc.strength * 80)
          return Math.max(600, Math.min(2500, baseSpeed))
        }}
        arcAltitudeAutoScale={(d: object) => {
          const arc = d as GlobeArc
          // Higher arcs for stronger/longer connections
          return 0.3 + (arc.strength / 50)
        }}
        arcLabel={(d: object) => {
          const arc = d as GlobeArc
          const formatYear = (y: number | null) => {
            if (y === null) return '?'
            return y < 0 ? `${Math.abs(y)} BCE` : `${y} CE`
          }
          return `
            <div style="
              background: rgba(10, 14, 23, 0.95);
              border: 1px solid ${LAYER_COLORS[arc.layer_type] || '#00d4ff'};
              border-radius: 6px;
              padding: 10px 14px;
              font-size: 12px;
              color: #e2e8f0;
              max-width: 300px;
            ">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span style="
                  background: ${LAYER_COLORS[arc.layer_type] || '#00d4ff'};
                  padding: 2px 6px;
                  border-radius: 3px;
                  font-size: 10px;
                  font-weight: 600;
                  color: #000;
                  text-transform: uppercase;
                ">${arc.layer_type}</span>
                ${arc.connection_type ? `<span style="color: #64748b; font-size: 10px;">${arc.connection_type}</span>` : ''}
                <span style="color: #fbbf24; font-size: 11px; margin-left: auto;">⚡ ${arc.strength.toFixed(1)}</span>
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <div style="flex: 1; text-align: left;">
                  <div style="color: #00d4ff; font-weight: 500;">${arc.source_title}</div>
                  <div style="color: #64748b; font-size: 10px;">${formatYear(arc.source_year)}</div>
                </div>
                <div style="color: #64748b; font-size: 16px;">→</div>
                <div style="flex: 1; text-align: right;">
                  <div style="color: #00d4ff; font-weight: 500;">${arc.target_title}</div>
                  <div style="color: #64748b; font-size: 10px;">${formatYear(arc.target_year)}</div>
                </div>
              </div>
            </div>
          `
        }}
        onArcClick={(arc: object) => {
          const arcData = arc as GlobeArc
          // Click on arc navigates to the target event
          const targetEvent = eventsData?.find((e: Event) => e.id === arcData.target_event_id)
          if (targetEvent) {
            onEventClick(targetEvent)
          }
        }}
        // Heatmap Layer - Event density visualization using hex bins
        hexBinPointsData={showHeatmap ? visibleMarkers : []}
        hexBinPointLat={(d: object) => (d as GlobeMarker).lat}
        hexBinPointLng={(d: object) => (d as GlobeMarker).lng}
        hexBinPointWeight={() => 1}
        hexBinResolution={3}
        hexTopColor={(d: object) => {
          // FGO-style gradient based on point density
          const { sumWeight } = d as { sumWeight: number }
          const maxDensity = 20 // Adjust based on expected max density
          const t = Math.min(1, Math.pow(sumWeight / maxDensity, 0.6))
          if (t < 0.33) {
            return `rgba(0, 212, 255, ${0.3 + 0.3 * t * 3})`
          } else if (t < 0.66) {
            const s = (t - 0.33) / 0.33
            return `rgba(${Math.round(100 * s)}, ${Math.round(150 - 50 * s)}, 220, ${0.6 + 0.2 * s})`
          } else {
            const s = (t - 0.66) / 0.34
            return `rgba(${Math.round(100 + 155 * s)}, ${Math.round(100 - 68 * s)}, ${Math.round(220 + 35 * s)}, ${0.8 + 0.2 * s})`
          }
        }}
        hexSideColor={(d: object) => {
          const { sumWeight } = d as { sumWeight: number }
          const maxDensity = 20
          const t = Math.min(1, Math.pow(sumWeight / maxDensity, 0.6))
          return `rgba(0, 180, 220, ${0.2 + 0.3 * t})`
        }}
        hexAltitude={(d: object) => {
          const { sumWeight } = d as { sumWeight: number }
          const maxDensity = 20
          return Math.min(0.5, 0.02 + 0.48 * Math.pow(sumWeight / maxDensity, 0.5))
        }}
        hexBinMerge={true}
        hexLabel={(d: object) => {
          const { sumWeight, center } = d as { sumWeight: number; center: { lat: number; lng: number } }
          return `
            <div style="
              background: rgba(10, 14, 23, 0.95);
              border: 1px solid rgba(0, 212, 255, 0.5);
              border-radius: 6px;
              padding: 8px 12px;
              font-size: 12px;
              color: #e2e8f0;
            ">
              <div style="color: #00d4ff; font-weight: 600; margin-bottom: 4px;">
                Event Cluster
              </div>
              <div style="color: #8ba4b4;">${Math.round(sumWeight)} events</div>
              <div style="color: #64748b; font-size: 10px; margin-top: 4px;">
                ${center.lat.toFixed(1)}°, ${center.lng.toFixed(1)}°
              </div>
            </div>
          `
        }}
      />

      {/* Heatmap Toggle Button */}
      <button
        className={`globe-heatmap-toggle ${showHeatmap ? 'active' : ''}`}
        onClick={handleHeatmapToggle}
        title={showHeatmap ? 'Hide event density heatmap' : 'Show event density heatmap'}
      >
        <span className="heatmap-icon">{showHeatmap ? '🔥' : '🗺️'}</span>
        <span className="heatmap-label">{showHeatmap ? 'Heatmap ON' : 'Heatmap'}</span>
      </button>

      {/* Heatmap Legend */}
      {showHeatmap && (
        <div className="globe-heatmap-legend">
          <div className="legend-title">Event Density</div>
          <div className="legend-bar">
            <span className="legend-low">Low</span>
            <div className="legend-gradient" />
            <span className="legend-high">High</span>
          </div>
          <div className="legend-count">{visibleMarkers.length} events</div>
        </div>
      )}

      {/* Clustering Toggle Button */}
      <button
        className={`globe-cluster-toggle ${enableClustering ? 'active' : ''}`}
        onClick={handleClusteringToggle}
        title={enableClustering ? 'Disable marker clustering' : 'Enable marker clustering'}
      >
        <span className="cluster-icon">{enableClustering ? '🔘' : '📍'}</span>
        <span className="cluster-label">{enableClustering ? 'Clustered' : 'All Points'}</span>
      </button>
    </div>
  )
}
