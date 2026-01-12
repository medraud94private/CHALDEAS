import { useState, useMemo, lazy, Suspense } from 'react'
import { useTranslation } from 'react-i18next'
import { ChatPanel } from './components/chat'
import { EventDetailPanel } from './components/detail'
import { ShowcaseMenu } from './components/showcase'
import type { ShowcaseContent } from './components/showcase'
import { FilterPanel, defaultFilters } from './components/filters'
import type { FilterState } from './components/filters'
import { SearchAutocomplete } from './components/search'
import { UnifiedTimeline } from './components/timeline'
import { VirtualEventList } from './components/sidebar'
import { LanguageSelector } from './components/common'
import { useTimelineStore } from './store/timelineStore'
import { useGlobeStore } from './store/globeStore'
import { useBookmarkStore } from './store/bookmarkStore'
import { useQuery } from '@tanstack/react-query'
import { api } from './api/client'
import type { Event } from './types'

// Lazy load heavy components (Three.js/Globe, panels)
const GlobeContainer = lazy(() => import('./components/globe/GlobeContainer').then(m => ({ default: m.GlobeContainer })))
const PersonDetailView = lazy(() => import('./components/detail/PersonDetailView').then(m => ({ default: m.PersonDetailView })))
const LocationDetailView = lazy(() => import('./components/detail/LocationDetailView').then(m => ({ default: m.LocationDetailView })))
const ShowcaseModal = lazy(() => import('./components/showcase').then(m => ({ default: m.ShowcaseModal })))
const ExplorePanel = lazy(() => import('./components/explore/ExplorePanel').then(m => ({ default: m.ExplorePanel })))
const ChainPanel = lazy(() => import('./components/chain/ChainPanel'))

// Loading fallback components
const GlobeLoader = () => (
  <div className="globe-loading">
    <div className="globe-loading-spinner" />
    <span>Initializing CHALDEAS Globe...</span>
  </div>
)

const PanelLoader = () => (
  <div className="panel-loading">
    <div className="panel-loading-spinner" />
  </div>
)

const CATEGORY_KEYS = [
  'all', 'battle', 'war', 'politics', 'religion', 'philosophy',
  'science', 'culture', 'civilization', 'discovery'
] as const

const GLOBE_STYLE_KEYS = ['default', 'holo', 'night'] as const

function App() {
  const { t } = useTranslation()
  const { currentYear, setCurrentYear } = useTimelineStore()
  const { selectedEvent, setSelectedEvent } = useGlobeStore()
  const { bookmarkedIds, toggleBookmark } = useBookmarkStore()
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [globeStyle, setGlobeStyle] = useState('default')
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [initialChatQuery, setInitialChatQuery] = useState<string | null>(null)
  const [showAllEras, setShowAllEras] = useState(false) // Toggle for sidebar: nearby era by default
  const [showcaseContent, setShowcaseContent] = useState<ShowcaseContent | null>(null)
  const [isShowcaseOpen, setIsShowcaseOpen] = useState(false)
  const [isExploreOpen, setIsExploreOpen] = useState(false)
  const [isChainOpen, setIsChainOpen] = useState(false)
  const [personDetailId, setPersonDetailId] = useState<number | null>(null)
  const [locationDetailId, setLocationDetailId] = useState<number | null>(null)
  const [advancedFilters, setAdvancedFilters] = useState<FilterState>(defaultFilters)
  const [isFilterPanelOpen, setIsFilterPanelOpen] = useState(false)

  // Handlers for entity detail views
  const handlePersonClick = (personId: number) => {
    setLocationDetailId(null) // Close location view if open
    setPersonDetailId(personId)
  }

  const handleLocationClick = (locationId: number) => {
    setPersonDetailId(null) // Close person view if open
    setLocationDetailId(locationId)
  }

  const handleCloseEntityView = () => {
    setPersonDetailId(null)
    setLocationDetailId(null)
  }

  const handleEventClick = (event: Event) => {
    setSelectedEvent(event)
    // Timeline follows to event's year
    setCurrentYear(event.date_start)
  }

  const handleClosePanel = () => {
    setSelectedEvent(null)
  }

  // Fetch chain stats for sidebar
  const { data: chainStats } = useQuery({
    queryKey: ['chain-stats'],
    queryFn: () => api.get('/chains/stats'),
    select: (res) => res.data,
    staleTime: 60000, // Cache for 1 minute
  })

  // Fetch events for sidebar - filtered by current era
  const TIME_RANGE = 50 // ±50 years for nearby era filter
  const WIDE_RANGE = 500 // ±500 years for "All Eras" mode (still centered on current year)
  const { data: allEventsData } = useQuery({
    queryKey: ['sidebar-events', currentYear, showAllEras],
    queryFn: () => api.get('/events', {
      params: showAllEras
        // "All Eras" mode: wider range centered on current year (moves with timeline)
        ? { year_start: currentYear - WIDE_RANGE, year_end: currentYear + WIDE_RANGE, limit: 1000 }
        : { year_start: currentYear - TIME_RANGE, year_end: currentYear + TIME_RANGE, limit: 1000 }
    }),
    select: (res) => res.data.items,
  })

  // Filter events for sidebar list (category, search, and advanced filters)
  const filteredEvents = useMemo(() => {
    return (allEventsData || [])
      .filter((e: Event) => {
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
        // Advanced: Year range filter (if custom range set beyond API filter)
        if (advancedFilters.yearRange.start > -3000 || advancedFilters.yearRange.end < 2025) {
          if (e.date_start < advancedFilters.yearRange.start ||
              e.date_start > advancedFilters.yearRange.end) {
            return false
          }
        }
        return true
      })
      .sort((a: Event, b: Event) => a.date_start - b.date_start)
      .slice(0, 500)
  }, [allEventsData, selectedCategory, searchQuery, advancedFilters.yearRange])

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

        {/* Archive Menu - FGO & Pan-Human History */}
        <div className="archive-menu-section">
          <ShowcaseMenu
            onSelectContent={(content) => {
              setShowcaseContent(content)
              setIsShowcaseOpen(true)
            }}
          />
        </div>

        <div className="search-container">
          <SearchAutocomplete
            placeholder={t('sidebar.searchPlaceholder')}
            onSelectEvent={async (eventId) => {
              try {
                const res = await api.get(`/events/${eventId}`)
                if (res.data) handleEventClick(res.data)
              } catch (err) {
                console.error('Failed to fetch event:', err)
              }
            }}
            onSelectPerson={handlePersonClick}
            onSelectLocation={handleLocationClick}
            onSearch={setSearchQuery}
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

        {/* Advanced Filters */}
        <FilterPanel
          filters={advancedFilters}
          onChange={setAdvancedFilters}
          isOpen={isFilterPanelOpen}
          onToggle={() => setIsFilterPanelOpen(!isFilterPanelOpen)}
        />

        <VirtualEventList
          events={filteredEvents}
          selectedEventId={selectedEvent?.id}
          onEventClick={handleEventClick}
          onBookmarkToggle={toggleBookmark}
          bookmarkedIds={bookmarkedIds}
        />

        {/* Historical Chain Stats Section */}
        {chainStats && (
          <div
            className="chain-stats-section"
            onClick={() => setIsChainOpen(true)}
            title="Click to explore Historical Chain"
          >
            <div className="chain-stats-header">
              <span className="chain-stats-icon">⧉</span>
              <span className="chain-stats-title">{t('sidebar.chainStats', 'Historical Chain')}</span>
            </div>
            <div className="chain-stats-grid">
              <div className="chain-stat-item">
                <span className="chain-stat-value">{chainStats.total_connections?.toLocaleString()}</span>
                <span className="chain-stat-label">{t('sidebar.connections', 'Connections')}</span>
              </div>
              <div className="chain-stat-item">
                <span className="chain-stat-value">{chainStats.by_layer?.person?.toLocaleString() || 0}</span>
                <span className="chain-stat-label">{t('sidebar.personLinks', 'Person')}</span>
              </div>
              <div className="chain-stat-item">
                <span className="chain-stat-value">{chainStats.by_layer?.location?.toLocaleString() || 0}</span>
                <span className="chain-stat-label">{t('sidebar.locationLinks', 'Location')}</span>
              </div>
              <div className="chain-stat-item">
                <span className="chain-stat-value">{chainStats.by_layer?.causal?.toLocaleString() || 0}</span>
                <span className="chain-stat-label">{t('sidebar.causalLinks', 'Causal')}</span>
              </div>
            </div>
          </div>
        )}

        <div className="sidebar-footer">
          <span>{t('sidebar.records')}: {filteredEvents.length} / {allEventsData?.length || 0}</span>
          <span>{t('sidebar.latency')}: 3ms</span>
        </div>
      </aside>

      {/* Center - Globe */}
      <section className="globe-section">
        <div className="globe-overlay-top">
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

        <Suspense fallback={<GlobeLoader />}>
          <GlobeContainer onEventClick={handleEventClick} globeStyle={globeStyle} />
        </Suspense>

        <div className="globe-overlay-bottom" style={{ bottom: '100px' }}>
          <div className="system-spec">{t('app.systemSpec')}</div>
        </div>

        {/* Unified Timeline - switchable modes (compact/standard/expanded) */}
        <div className="unified-timeline-wrapper">
          <UnifiedTimeline events={allEventsData || []} />
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
        onPersonClick={handlePersonClick}
        onLocationClick={handleLocationClick}
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

      {/* Explore Toggle Button */}
      <button
        className="explore-toggle-btn"
        onClick={() => setIsExploreOpen(true)}
        title="Explore Entity Pool (Pre-Curation)"
      >
        ⋮⋮⋮
      </button>

      {/* Entity Explorer Panel */}
      <Suspense fallback={<PanelLoader />}>
        <ExplorePanel
          isOpen={isExploreOpen}
          onClose={() => setIsExploreOpen(false)}
        />
      </Suspense>

      {/* Historical Chain Panel */}
      {isChainOpen && (
        <div className="chain-panel-overlay">
          <div className="chain-panel-container">
            <button
              className="chain-panel-close"
              onClick={() => setIsChainOpen(false)}
            >
              ✕
            </button>
            <Suspense fallback={<PanelLoader />}>
              <ChainPanel />
            </Suspense>
          </div>
        </div>
      )}

      {/* Showcase Modal */}
      <Suspense fallback={<PanelLoader />}>
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
      </Suspense>

      {/* Person Detail View */}
      {personDetailId && (
        <Suspense fallback={<PanelLoader />}>
          <PersonDetailView
            personId={personDetailId}
            onClose={handleCloseEntityView}
            onEventClick={handleEventClick}
            onPersonClick={handlePersonClick}
          />
        </Suspense>
      )}

      {/* Location Detail View */}
      {locationDetailId && (
        <Suspense fallback={<PanelLoader />}>
          <LocationDetailView
            locationId={locationDetailId}
            onClose={handleCloseEntityView}
            onEventClick={handleEventClick}
            onLocationClick={handleLocationClick}
          />
        </Suspense>
      )}
    </div>
  )
}

export default App
