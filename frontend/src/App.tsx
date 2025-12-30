import { useState, useEffect } from 'react'
import { GlobeContainer } from './components/globe/GlobeContainer'
import { useTimelineStore } from './store/timelineStore'
import { useGlobeStore } from './store/globeStore'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { Event } from './types'

const CATEGORIES = [
  'ALL', 'BATTLE', 'WAR', 'POLITICS', 'RELIGION', 'PHILOSOPHY',
  'SCIENCE', 'CULTURE', 'CIVILIZATION', 'DISCOVERY'
]

const GLOBE_STYLES = [
  { id: 'default', label: 'BLUE MARBLE' },
  { id: 'holo', label: 'HOLO' },
  { id: 'night', label: 'NIGHT' },
]

function App() {
  const { currentYear, setCurrentYear, isPlaying, play, pause } = useTimelineStore()
  const { selectedEvent, setSelectedEvent, events } = useGlobeStore()
  const [selectedCategory, setSelectedCategory] = useState('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [globeStyle, setGlobeStyle] = useState('default')

  // Format year display
  const formatYear = (year: number) => {
    const absYear = Math.abs(year)
    const era = year < 0 ? 'BC' : 'AD'
    return { number: absYear, era }
  }

  const handleEventClick = (event: Event) => {
    setSelectedEvent(event)
    // Timeline follows to event's year
    setCurrentYear(event.date_start)
  }

  const handleClosePanel = () => {
    setSelectedEvent(null)
  }

  // Fetch ALL events for sidebar (not time-filtered)
  const { data: allEventsData } = useQuery({
    queryKey: ['all-events'],
    queryFn: () => api.get('/events', { params: { limit: 1000 } }),
    select: (res) => res.data.items,
  })

  // Filter events for sidebar list (show all eras)
  const filteredEvents = (allEventsData || [])
    .filter((e: Event) => {
      if (selectedCategory !== 'ALL') {
        const cat = typeof e.category === 'string' ? e.category : e.category?.slug
        if (cat?.toLowerCase() !== selectedCategory.toLowerCase()) return false
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        if (!e.title.toLowerCase().includes(q)) return false
      }
      return true
    })
    .sort((a: Event, b: Event) => a.date_start - b.date_start)
    .slice(0, 100)

  const yearDisplay = formatYear(currentYear)

  // Timeline playback - 1 year per 10 seconds
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      useTimelineStore.setState((state) => ({
        currentYear: state.currentYear + 1
      }))
    }, 10000) // 10 seconds per year

    return () => clearInterval(interval)
  }, [isPlaying])

  return (
    <div className="app-container">
      {/* Left Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon">⊕</div>
            <div>
              <div className="logo-text">CHALDEAS</div>
              <div className="system-status">
                <span className="status-dot"></span>
                SYSTEM ONLINE
              </div>
            </div>
          </div>
        </div>

        <div className="search-container">
          <input
            type="text"
            className="search-input"
            placeholder="SEARCH ARCHIVES..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="category-filters">
          <div className="category-tags">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                className={`category-tag ${selectedCategory === cat ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className="event-list">
          {filteredEvents.map((event) => {
            const year = formatYear(event.date_start)
            const cat = typeof event.category === 'string' ? event.category : 'general'
            return (
              <div
                key={event.id}
                className={`event-item ${selectedEvent?.id === event.id ? 'selected' : ''}`}
                onClick={() => handleEventClick(event)}
              >
                <div className="event-date">
                  {year.era} {year.number}
                </div>
                <div className="event-title">{event.title}</div>
                <span className={`event-category-badge ${cat}`}>
                  {cat}
                </span>
              </div>
            )
          })}
        </div>

        <div className="sidebar-footer">
          <span>RECORDS: {filteredEvents.length} / {allEventsData?.length || 0}</span>
          <span>LATENCY: 3ms</span>
        </div>
      </aside>

      {/* Center - Globe */}
      <section className="globe-section">
        <div className="globe-overlay-top">
          <div className="globe-control">
            CAM_MODE: <span>ORBIT</span>
          </div>
          <div className="globe-style-selector">
            {GLOBE_STYLES.map((style) => (
              <button
                key={style.id}
                className={`globe-style-btn ${globeStyle === style.id ? 'active' : ''}`}
                onClick={() => setGlobeStyle(style.id)}
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>

        <GlobeContainer onEventClick={handleEventClick} globeStyle={globeStyle} />

        <div className="globe-overlay-bottom" style={{ bottom: '100px' }}>
          <div className="system-spec">CHALDEAS SYSTEM SPEC III</div>
        </div>

        {/* Timeline Controls */}
        <div className="timeline-container">
          <div className="timeline-controls">
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear - 100)}
            >
              -100
            </button>
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear - 10)}
            >
              -10
            </button>

            <div className="timeline-year-display">
              <div className="timeline-year-label">OBSERVING</div>
              <div className="timeline-year-value">
                {yearDisplay.number} {yearDisplay.era}
              </div>
            </div>

            <button
              className="timeline-btn play"
              onClick={() => (isPlaying ? pause() : play())}
            >
              {isPlaying ? '⏸' : '▶'}
            </button>

            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear + 10)}
            >
              +10
            </button>
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear + 100)}
            >
              +100
            </button>
          </div>
        </div>
      </section>

      {/* Right Panel - Event Detail */}
      <aside className={`detail-panel ${!selectedEvent ? 'hidden' : ''}`}>
        {selectedEvent && (
          <>
            <button className="close-btn" onClick={handleClosePanel}>
              ✕
            </button>

            <div className="detail-header">
              <div className="detail-meta">
                <span>📋</span>
                LOG ID: {selectedEvent.id}
              </div>
              <div className="detail-year">
                <div className="detail-year-number">
                  {Math.abs(selectedEvent.date_start)}
                </div>
                <div className="detail-year-era">
                  {selectedEvent.date_start < 0 ? 'BC' : 'AD'}
                </div>
              </div>
            </div>

            <div className="detail-title">
              <h2>{selectedEvent.title}</h2>
            </div>

            <div className="detail-content">
              <p className="detail-description">
                {selectedEvent.description || 'No detailed description available for this event.'}
              </p>
            </div>

            <div className="detail-footer">
              <div className="detail-coords">
                LAT: {selectedEvent.latitude?.toFixed(2) || 'N/A'} LON: {selectedEvent.longitude?.toFixed(2) || 'N/A'}
              </div>
              <div className="detail-status">
                <span>◉</span>
                CONFIRMED
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}

export default App
