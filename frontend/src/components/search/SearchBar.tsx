import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useGlobeStore } from '../../store/globeStore'
import type { Event, Person, Location } from '../../types'

export function SearchBar() {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const { setSelectedEvent, flyToLocation } = useGlobeStore()

  // Search query
  const { data: results, isLoading } = useQuery({
    queryKey: ['search', query],
    queryFn: () => api.get('/search', { params: { q: query, limit: 10 } }),
    select: (res) => res.data.results,
    enabled: query.length >= 2,
  })

  const handleEventClick = useCallback(
    (event: Event) => {
      setSelectedEvent(event)
      setIsOpen(false)
      setQuery('')
    },
    [setSelectedEvent]
  )

  const handleLocationClick = useCallback(
    (location: Location) => {
      flyToLocation(location.latitude, location.longitude)
      setIsOpen(false)
      setQuery('')
    },
    [flyToLocation]
  )

  return (
    <div className="search-bar relative">
      <input
        type="text"
        placeholder="Search events, persons, locations..."
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setIsOpen(true)
        }}
        onFocus={() => setIsOpen(true)}
      />

      {/* Results dropdown */}
      {isOpen && query.length >= 2 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-chaldea-secondary border border-white/20 rounded-lg shadow-xl max-h-96 overflow-y-auto z-50">
          {isLoading ? (
            <div className="p-4 text-center text-gray-400">Searching...</div>
          ) : results ? (
            <div>
              {/* Events */}
              {results.events?.length > 0 && (
                <div className="p-2">
                  <div className="text-xs text-gray-400 px-2 mb-1">Events</div>
                  {results.events.map((event: Event) => (
                    <button
                      key={event.id}
                      onClick={() => handleEventClick(event)}
                      className="w-full text-left px-3 py-2 hover:bg-white/10 rounded"
                    >
                      <div className="text-white text-sm">{event.title}</div>
                      <div className="text-xs text-gray-400">
                        {event.date_display}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Persons */}
              {results.persons?.length > 0 && (
                <div className="p-2 border-t border-white/10">
                  <div className="text-xs text-gray-400 px-2 mb-1">Persons</div>
                  {results.persons.map((person: Person) => (
                    <button
                      key={person.id}
                      className="w-full text-left px-3 py-2 hover:bg-white/10 rounded"
                    >
                      <div className="text-white text-sm">{person.name}</div>
                      <div className="text-xs text-gray-400">
                        {person.lifespan_display}
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Locations */}
              {results.locations?.length > 0 && (
                <div className="p-2 border-t border-white/10">
                  <div className="text-xs text-gray-400 px-2 mb-1">
                    Locations
                  </div>
                  {results.locations.map((location: Location) => (
                    <button
                      key={location.id}
                      onClick={() => handleLocationClick(location)}
                      className="w-full text-left px-3 py-2 hover:bg-white/10 rounded"
                    >
                      <div className="text-white text-sm">{location.name}</div>
                      {location.modern_name && (
                        <div className="text-xs text-gray-400">
                          {location.modern_name}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}

              {/* No results */}
              {!results.events?.length &&
                !results.persons?.length &&
                !results.locations?.length && (
                  <div className="p-4 text-center text-gray-400">
                    No results found
                  </div>
                )}
            </div>
          ) : null}
        </div>
      )}

      {/* Backdrop to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  )
}
