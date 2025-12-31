import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { GlobeContainer } from './components/globe/GlobeContainer'
import { ChatPanel } from './components/chat'
import { EventDetailPanel } from './components/detail'
import { ShowcaseModal, ShowcaseMenu } from './components/showcase'
import type { ShowcaseContent } from './components/showcase'
import { LanguageSelector } from './components/common'
import { useTimelineStore } from './store/timelineStore'
import { useGlobeStore } from './store/globeStore'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import { formatYearWithEra } from './utils/era'
import type { Event } from './types'

const CATEGORY_KEYS = [
  'all', 'battle', 'war', 'politics', 'religion', 'philosophy',
  'science', 'culture', 'civilization', 'discovery'
] as const

const GLOBE_STYLE_KEYS = ['default', 'holo', 'night'] as const

function App() {
  const { t } = useTranslation()
  const { currentYear, setCurrentYear, isPlaying, play, pause } = useTimelineStore()
  const { selectedEvent, setSelectedEvent } = useGlobeStore()
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [globeStyle, setGlobeStyle] = useState('default')
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [initialChatQuery, setInitialChatQuery] = useState<string | null>(null)
  const [showAllEras, setShowAllEras] = useState(true) // Toggle for sidebar: all eras vs nearby
  const [showcaseContent, setShowcaseContent] = useState<ShowcaseContent | null>(null)
  const [isShowcaseOpen, setIsShowcaseOpen] = useState(false)

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

  // Filter events for sidebar list
  const TIME_RANGE = 10 // ±10 years for nearby era filter
  const filteredEvents = (allEventsData || [])
    .filter((e: Event) => {
      // Era filter: nearby (±10 years) or all
      if (!showAllEras) {
        const start = e.date_start
        const end = e.date_end || start
        if (currentYear < start - TIME_RANGE || currentYear > end + TIME_RANGE) {
          return false
        }
      }
      // Category filter
      if (selectedCategory !== 'all') {
        const cat = typeof e.category === 'string' ? e.category : e.category?.slug
        if (cat?.toLowerCase() !== selectedCategory.toLowerCase()) return false
      }
      // Search filter
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        if (!e.title.toLowerCase().includes(q)) return false
      }
      return true
    })
    .sort((a: Event, b: Event) => a.date_start - b.date_start)
    .slice(0, 100)

  const yearDisplay = formatYear(currentYear)

  // Get era information for current year
  const eraInfo = useMemo(() => formatYearWithEra(currentYear), [currentYear])

  // Timeline playback - 1 year per 10 seconds
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      useTimelineStore.setState((state) => ({
        currentYear: state.currentYear + 1
      }))
    }, 5000) // 5 seconds per year

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
              <div className="logo-text">{t('app.name')}</div>
              <div className="system-status">
                <span className="status-dot"></span>
                {t('app.systemOnline')}
              </div>
            </div>
          </div>
          <LanguageSelector />
        </div>

        <div className="search-container">
          <input
            type="text"
            className="search-input"
            placeholder={t('sidebar.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div className="category-filters">
          <div className="category-tags">
            {CATEGORY_KEYS.map((cat) => (
              <button
                key={cat}
                className={`category-tag ${selectedCategory === cat ? 'active' : ''}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {t(`categories.${cat}`)}
              </button>
            ))}
          </div>
        </div>

        {/* Era Filter Toggle */}
        <div className="era-filter-toggle">
          <button
            className={`era-toggle-btn ${!showAllEras ? 'active' : ''}`}
            onClick={() => setShowAllEras(false)}
          >
            <span className="toggle-label">{t('sidebar.eraFilter.nearby')}</span>
            <span className="toggle-desc">{t('sidebar.eraFilter.nearbyDesc')}</span>
          </button>
          <button
            className={`era-toggle-btn ${showAllEras ? 'active' : ''}`}
            onClick={() => setShowAllEras(true)}
          >
            <span className="toggle-label">{t('sidebar.eraFilter.all')}</span>
            <span className="toggle-desc">{t('sidebar.eraFilter.allDesc')}</span>
          </button>
        </div>

        <div className="event-list">
          {filteredEvents.map((event: Event) => {
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
          <span>{t('sidebar.records')}: {filteredEvents.length} / {allEventsData?.length || 0}</span>
          <span>{t('sidebar.latency')}: 3ms</span>
        </div>
      </aside>

      {/* Center - Globe */}
      <section className="globe-section">
        <div className="globe-overlay-top">
          <ShowcaseMenu
            onSelectContent={(content) => {
              setShowcaseContent(content)
              setIsShowcaseOpen(true)
            }}
          />
          <div className="globe-control">
            {t('globe.camMode')}: <span>{t('globe.orbit')}</span>
          </div>
          <div className="globe-style-selector">
            {GLOBE_STYLE_KEYS.map((styleKey) => (
              <button
                key={styleKey}
                className={`globe-style-btn ${globeStyle === styleKey ? 'active' : ''}`}
                onClick={() => setGlobeStyle(styleKey)}
              >
                {t(`globe.styles.${styleKey}`)}
              </button>
            ))}
          </div>
        </div>

        <GlobeContainer onEventClick={handleEventClick} globeStyle={globeStyle} />

        <div className="globe-overlay-bottom" style={{ bottom: '100px' }}>
          <div className="system-spec">{t('app.systemSpec')}</div>
        </div>

        {/* Timeline Controls - FGO Style */}
        <div className="timeline-container">
          {/* Era Display */}
          <div className="era-display">
            <div className="era-badge" style={{ borderColor: eraInfo.eraColor, color: eraInfo.eraColor }}>
              <span className="era-name">{t(`era.names.${eraInfo.eraName}`)}</span>
            </div>
            <div className="era-context">{t(`era.contexts.${eraInfo.eraName}`, t('era.observing'))}</div>
          </div>

          <div className="timeline-controls">
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear - 100)}
            >
              ◀◀ 100
            </button>
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear - 10)}
            >
              ◀ 10
            </button>

            <div className="timeline-year-display">
              <div className="timeline-year-label">{t('timeline.observingYear')}</div>
              <div className="timeline-year-value">
                <span className="year-number">{yearDisplay.number}</span>
                <span className="year-era" style={{ color: eraInfo.eraColor }}>{yearDisplay.era}</span>
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
              10 ▶
            </button>
            <button
              className="timeline-btn"
              onClick={() => setCurrentYear(currentYear + 100)}
            >
              100 ▶▶
            </button>
          </div>
        </div>
      </section>

      {/* Right Panel - Event Detail (FGO Style) */}
      <EventDetailPanel
        event={selectedEvent}
        allEvents={allEventsData || []}
        onClose={handleClosePanel}
        onEventClick={handleEventClick}
        onAskSheba={(query) => {
          setInitialChatQuery(query)
          setIsChatOpen(true)
        }}
      />

      {/* SHEBA Chat Interface */}
      <ChatPanel
        isOpen={isChatOpen}
        onClose={() => {
          setIsChatOpen(false)
          setInitialChatQuery(null)
        }}
        initialQuery={initialChatQuery}
        onQueryProcessed={() => setInitialChatQuery(null)}
      />

      {/* Chat Toggle Button */}
      {!isChatOpen && (
        <button
          className="chat-toggle-btn"
          onClick={() => setIsChatOpen(true)}
          title="Open SHEBA Chat"
        >
          ◎
        </button>
      )}

      {/* Showcase Modal */}
      <ShowcaseModal
        isOpen={isShowcaseOpen}
        content={showcaseContent}
        onClose={() => {
          setIsShowcaseOpen(false)
          setShowcaseContent(null)
        }}
        onEventClick={(eventId) => {
          // Find and select the event, then close modal
          const event = allEventsData?.find((e: Event) => e.id === eventId)
          if (event) {
            handleEventClick(event)
            setIsShowcaseOpen(false)
          }
        }}
      />
    </div>
  )
}

export default App
