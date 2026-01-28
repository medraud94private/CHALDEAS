/**
 * StoryGlobe - Globe visualization for Person Story
 *
 * Simplified globe focused on showing a person's journey through locations.
 * Features:
 * - Node markers at event locations
 * - Path lines connecting nodes in sequence
 * - Camera auto-focus on current node
 * - FGO-style visual effects
 */
import { useRef, useEffect, useMemo } from 'react'
import Globe, { GlobeMethods } from 'react-globe.gl'

interface StoryLocation {
  name: string
  name_ko?: string
  lat: number
  lng: number
}

interface StoryNode {
  order: number
  event_id: number
  title: string
  title_ko?: string
  year: number | null
  year_end?: number | null
  location: StoryLocation | null
  node_type: string
  description?: string
}

interface Props {
  nodes: StoryNode[]
  currentIndex: number
  onNodeClick: (index: number) => void
}

// Node type colors
const NODE_COLORS: Record<string, string> = {
  birth: '#22c55e',
  death: '#ef4444',
  battle: '#f97316',
  major: '#fbbf24',
  political: '#a855f7',
  religious: '#f472b6',
  default: '#00d4ff',
}

export function StoryGlobe({ nodes, currentIndex, onNodeClick }: Props) {
  const globeRef = useRef<GlobeMethods>()

  // Filter nodes that have valid locations
  const validNodes = useMemo(() =>
    nodes.filter(n => n.location && n.location.lat && n.location.lng),
    [nodes]
  )

  // Convert nodes to marker data
  const markers = useMemo(() =>
    validNodes.map((node) => {
      const originalIndex = nodes.findIndex(n => n.event_id === node.event_id)
      return {
        ...node,
        originalIndex,
        lat: node.location!.lat,
        lng: node.location!.lng,
        color: NODE_COLORS[node.node_type] || NODE_COLORS.default,
        isActive: originalIndex === currentIndex,
        isVisited: originalIndex < currentIndex,
      }
    }),
    [validNodes, nodes, currentIndex]
  )

  // Create path data connecting sequential nodes
  const paths = useMemo(() => {
    if (validNodes.length < 2) return []

    const pathData: Array<{
      coords: [number, number][]
      color: string
      visited: boolean
    }> = []

    for (let i = 0; i < validNodes.length - 1; i++) {
      const from = validNodes[i]
      const to = validNodes[i + 1]
      const fromIdx = nodes.findIndex(n => n.event_id === from.event_id)

      pathData.push({
        coords: [
          [from.location!.lng, from.location!.lat],
          [to.location!.lng, to.location!.lat],
        ],
        color: fromIdx < currentIndex ? '#00d4ff' : 'rgba(255, 255, 255, 0.2)',
        visited: fromIdx < currentIndex,
      })
    }

    return pathData
  }, [validNodes, nodes, currentIndex])

  // Focus camera on current node
  useEffect(() => {
    if (!globeRef.current) return

    const currentNode = nodes[currentIndex]
    if (currentNode?.location) {
      // Stop any existing auto-rotate
      globeRef.current.controls().autoRotate = false

      // Animate to current location
      globeRef.current.pointOfView(
        {
          lat: currentNode.location.lat,
          lng: currentNode.location.lng,
          altitude: 1.5,
        },
        800 // animation duration
      )
    }
  }, [currentIndex, nodes])

  // Initial setup
  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.controls().autoRotate = false
      globeRef.current.controls().enableZoom = true
      globeRef.current.controls().enablePan = false
    }
  }, [])

  const getNodeIcon = (nodeType: string) => {
    switch (nodeType) {
      case 'birth': return '🌟'
      case 'death': return '✝'
      case 'battle': return '⚔'
      case 'major': return '★'
      case 'political': return '👑'
      case 'religious': return '⛪'
      default: return '●'
    }
  }

  return (
    <Globe
      ref={globeRef}
      // Dark globe style (FGO-like)
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-dark.jpg"
      backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
      showAtmosphere={true}
      atmosphereColor="#00d4ff"
      atmosphereAltitude={0.15}
      // Point markers for story nodes
      pointsData={markers}
      pointLat={(d) => (d as typeof markers[0]).lat}
      pointLng={(d) => (d as typeof markers[0]).lng}
      pointColor={(d) => {
        const marker = d as typeof markers[0]
        if (marker.isActive) return '#ffffff'
        if (marker.isVisited) return marker.color
        return 'rgba(100, 100, 120, 0.6)'
      }}
      pointAltitude={(d) => {
        const marker = d as typeof markers[0]
        return marker.isActive ? 0.08 : 0.03
      }}
      pointRadius={(d) => {
        const marker = d as typeof markers[0]
        return marker.isActive ? 1.2 : 0.6
      }}
      pointLabel={(d) => {
        const marker = d as typeof markers[0]
        const yearStr = marker.year !== null
          ? `${Math.abs(marker.year)} ${marker.year < 0 ? 'BCE' : 'CE'}`
          : ''
        return `
          <div style="
            background: rgba(10, 14, 23, 0.95);
            border: 1px solid ${marker.color};
            border-radius: 6px;
            padding: 10px 14px;
            font-size: 12px;
            color: #e2e8f0;
            max-width: 250px;
          ">
            <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
              <span style="font-size: 16px;">${getNodeIcon(marker.node_type)}</span>
              <span style="color: ${marker.color}; font-weight: 600;">${marker.title}</span>
            </div>
            ${yearStr ? `<div style="color: #00d4ff; font-size: 11px; margin-bottom: 4px;">${yearStr}</div>` : ''}
            ${marker.location ? `<div style="color: #64748b; font-size: 11px;">📍 ${marker.location.name}</div>` : ''}
          </div>
        `
      }}
      onPointClick={(point) => {
        const marker = point as typeof markers[0]
        onNodeClick(marker.originalIndex)
      }}
      // Path lines connecting nodes
      pathsData={paths}
      pathPoints="coords"
      pathColor={(d: object) => (d as typeof paths[0]).color}
      pathStroke={2}
      pathDashLength={0.3}
      pathDashGap={0.1}
      pathDashAnimateTime={3000}
      // Ring effect on current node
      ringsData={markers.filter(m => m.isActive)}
      ringColor={() => 'rgba(0, 212, 255, 0.6)'}
      ringMaxRadius={5}
      ringPropagationSpeed={2}
      ringRepeatPeriod={1000}
    />
  )
}
