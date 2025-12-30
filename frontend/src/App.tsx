import { useState } from 'react'
import { GlobeContainer } from './components/globe/GlobeContainer'
import { TimelineSlider } from './components/timeline/TimelineSlider'
import { WikiPanel } from './components/wiki/WikiPanel'
import { SearchBar } from './components/search/SearchBar'
import { useTimelineStore } from './store/timelineStore'
import { useGlobeStore } from './store/globeStore'
import type { Event } from './types'

function App() {
  const { currentYear } = useTimelineStore()
  const { selectedEvent, setSelectedEvent } = useGlobeStore()
  const [isPanelOpen, setIsPanelOpen] = useState(false)

  const handleEventClick = (event: Event) => {
    setSelectedEvent(event)
    setIsPanelOpen(true)
  }

  const handleClosePanel = () => {
    setIsPanelOpen(false)
    setSelectedEvent(null)
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-chaldea-primary flex flex-col">
      {/* Header */}
      <header className="h-16 bg-chaldea-secondary/80 backdrop-blur-sm border-b border-white/10 flex items-center px-6 z-10">
        <h1 className="text-xl font-bold text-white tracking-wider">
          CHALDEAS
        </h1>
        <span className="ml-3 text-sm text-gray-400">
          Historical Knowledge System
        </span>
        <div className="flex-1 max-w-xl mx-8">
          <SearchBar />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 relative">
        {/* Globe */}
        <GlobeContainer onEventClick={handleEventClick} />

        {/* Timeline at bottom */}
        <div className="absolute bottom-0 left-0 right-0 z-10">
          <TimelineSlider />
        </div>

        {/* Current Year Display */}
        <div className="absolute top-4 left-4 z-10 bg-chaldea-secondary/80 backdrop-blur-sm rounded-lg px-4 py-2">
          <div className="text-sm text-gray-400">Observing</div>
          <div className="text-2xl font-bold text-white">
            {Math.abs(currentYear)} {currentYear < 0 ? 'BCE' : 'CE'}
          </div>
        </div>

        {/* Wiki Panel (Slide-in) */}
        <WikiPanel
          isOpen={isPanelOpen}
          event={selectedEvent}
          onClose={handleClosePanel}
        />
      </main>
    </div>
  )
}

export default App
