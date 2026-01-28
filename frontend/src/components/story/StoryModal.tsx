/**
 * StoryModal - Fullscreen Person Story Experience
 *
 * FGO-inspired story mode with map nodes and narrative progression.
 * Shows a person's life journey through connected events on a map.
 */
import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { StoryGlobe } from './StoryGlobe'
import './story.css'

// Types
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

interface StoryPerson {
  id: number
  name: string
  name_ko?: string
  birth_year?: number
  death_year?: number
  role?: string
}

interface MapView {
  center_lat: number
  center_lng: number
  zoom: number
}

interface PersonStoryData {
  person: StoryPerson
  nodes: StoryNode[]
  total_nodes: number
  map_view: MapView
}

interface Props {
  isOpen: boolean
  personId: number
  onClose: () => void
  onEventClick?: (eventId: number) => void
}

export function StoryModal({ isOpen, personId, onClose, onEventClick }: Props) {
  const [currentNodeIndex, setCurrentNodeIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  // Fetch story data
  const { data: storyData, isLoading, error } = useQuery<PersonStoryData>({
    queryKey: ['person-story', personId],
    queryFn: async () => {
      const res = await api.get(`/story/person/${personId}`)
      return res.data
    },
    enabled: isOpen && !!personId,
  })

  // Auto-play logic
  useEffect(() => {
    if (!isPlaying || !storyData) return

    const timer = setInterval(() => {
      setCurrentNodeIndex((prev) => {
        if (prev >= storyData.nodes.length - 1) {
          setIsPlaying(false)
          return prev
        }
        return prev + 1
      })
    }, 3000) // 3 seconds per node

    return () => clearInterval(timer)
  }, [isPlaying, storyData])

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'ArrowRight' || e.key === ' ') {
      e.preventDefault()
      if (storyData && currentNodeIndex < storyData.nodes.length - 1) {
        setCurrentNodeIndex((prev) => prev + 1)
      }
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault()
      if (currentNodeIndex > 0) {
        setCurrentNodeIndex((prev) => prev - 1)
      }
    }
  }, [onClose, storyData, currentNodeIndex])

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, handleKeyDown])

  // Reset when closed/opened
  useEffect(() => {
    if (isOpen) {
      setCurrentNodeIndex(0)
      setIsPlaying(false)
    }
  }, [isOpen, personId])

  if (!isOpen) return null

  const currentNode = storyData?.nodes[currentNodeIndex]

  const formatYear = (year: number | null | undefined) => {
    if (year === null || year === undefined) return '?'
    if (year < 0) return `${Math.abs(year)} BCE`
    return `${year} CE`
  }

  const getNodeIcon = (nodeType: string) => {
    switch (nodeType) {
      case 'birth': return '🌟'
      case 'death': return '✝'
      case 'battle': return '⚔'
      case 'major': return '★'
      case 'political': return '👑'
      default: return '●'
    }
  }

  const handleNodeClick = (index: number) => {
    setCurrentNodeIndex(index)
    setIsPlaying(false)
  }

  return (
    <div className="story-overlay" onClick={onClose}>
      <div className="story-modal" onClick={(e) => e.stopPropagation()}>
        {/* Close Button */}
        <button className="story-close" onClick={onClose}>✕</button>

        {isLoading && (
          <div className="story-loading">
            <div className="loading-spinner"></div>
            <p>Loading story...</p>
          </div>
        )}

        {error && (
          <div className="story-error">
            <p>Failed to load story data.</p>
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        {storyData && storyData.nodes.length === 0 && (
          <div className="story-empty">
            <p>No story data available for this person.</p>
            <p className="story-empty-hint">Event connections may not have been generated yet.</p>
          </div>
        )}

        {storyData && storyData.nodes.length > 0 && (
          <>
            {/* Header */}
            <div className="story-header">
              <div className="story-person-info">
                <h1 className="story-title">{storyData.person.name}</h1>
                {storyData.person.name_ko && (
                  <div className="story-title-ko">{storyData.person.name_ko}</div>
                )}
                <div className="story-lifespan">
                  {formatYear(storyData.person.birth_year)} — {formatYear(storyData.person.death_year)}
                </div>
              </div>
              <div className="story-progress">
                {currentNodeIndex + 1} / {storyData.total_nodes}
              </div>
            </div>

            {/* Main Content: Map + Side Panel */}
            <div className="story-content">
              {/* Map Area with 3D Globe */}
              <div className="story-map">
                <StoryGlobe
                  nodes={storyData.nodes}
                  currentIndex={currentNodeIndex}
                  onNodeClick={handleNodeClick}
                />
                {/* Current location badge */}
                {currentNode?.location && (
                  <div className="story-location-badge">
                    <span className="location-icon">📍</span>
                    {currentNode.location.name}
                    {currentNode.location.name_ko && ` (${currentNode.location.name_ko})`}
                  </div>
                )}
              </div>

              {/* Side Panel: Current Node Info */}
              <div className="story-side-panel">
                {currentNode && (
                  <div className="story-node-detail">
                    <div className="node-type-badge" data-type={currentNode.node_type}>
                      {getNodeIcon(currentNode.node_type)} {currentNode.node_type.toUpperCase()}
                    </div>

                    <div className="node-year">
                      {formatYear(currentNode.year)}
                      {currentNode.year_end && currentNode.year_end !== currentNode.year && (
                        <span> — {formatYear(currentNode.year_end)}</span>
                      )}
                    </div>

                    <h2 className="node-title">{currentNode.title}</h2>
                    {currentNode.title_ko && (
                      <div className="node-title-ko">{currentNode.title_ko}</div>
                    )}

                    {currentNode.description && (
                      <p className="node-description">{currentNode.description}</p>
                    )}

                    {onEventClick && (
                      <button
                        className="node-detail-btn"
                        onClick={() => onEventClick(currentNode.event_id)}
                      >
                        View Event Details →
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Controls */}
            <div className="story-controls">
              <button
                className="story-btn"
                onClick={() => setCurrentNodeIndex(0)}
                disabled={currentNodeIndex === 0}
              >
                ⏮ First
              </button>
              <button
                className="story-btn"
                onClick={() => setCurrentNodeIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentNodeIndex === 0}
              >
                ◀ Prev
              </button>

              <button
                className={`story-btn play-btn ${isPlaying ? 'playing' : ''}`}
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? '⏸ Pause' : '▶ Play'}
              </button>

              <button
                className="story-btn"
                onClick={() => setCurrentNodeIndex((prev) => Math.min(storyData.nodes.length - 1, prev + 1))}
                disabled={currentNodeIndex === storyData.nodes.length - 1}
              >
                Next ▶
              </button>
              <button
                className="story-btn"
                onClick={() => setCurrentNodeIndex(storyData.nodes.length - 1)}
                disabled={currentNodeIndex === storyData.nodes.length - 1}
              >
                Last ⏭
              </button>
            </div>

            {/* Timeline dots */}
            <div className="story-timeline-dots">
              {storyData.nodes.map((node, idx) => (
                <button
                  key={node.event_id}
                  className={`timeline-dot ${idx === currentNodeIndex ? 'active' : ''} ${idx < currentNodeIndex ? 'visited' : ''}`}
                  onClick={() => handleNodeClick(idx)}
                  title={`${formatYear(node.year)}: ${node.title}`}
                >
                  {getNodeIcon(node.node_type)}
                </button>
              ))}
            </div>
          </>
        )}

        {/* Footer */}
        <div className="story-footer">
          <span className="footer-hint">← → Arrow keys to navigate | Space to advance | Esc to close</span>
        </div>
      </div>
    </div>
  )
}
