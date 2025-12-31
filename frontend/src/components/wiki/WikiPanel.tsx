import type { Event } from '../../types'

interface WikiPanelProps {
  isOpen: boolean
  event: Event | null
  onClose: () => void
}

export function WikiPanel({ isOpen, event, onClose }: WikiPanelProps) {
  if (!event) return null

  return (
    <div className={`wiki-panel ${isOpen ? 'open' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <h2 className="text-lg font-bold text-white truncate pr-4">
          {event.title}
        </h2>
        <button
          onClick={onClose}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-white/10"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="p-4 overflow-y-auto h-[calc(100%-60px)]">
        {/* Date & Category */}
        <div className="flex items-center gap-3 mb-4">
          <span
            className="px-2 py-1 rounded text-sm"
            style={{ backgroundColor: typeof event.category === 'object' ? event.category?.color : '#3B82F6' }}
          >
            {typeof event.category === 'object' ? event.category?.name : (event.category || 'Event')}
          </span>
          <span className="text-gray-400">{event.date_display}</span>
        </div>

        {/* Location */}
        {event.location && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-1">
              Location
            </h3>
            <p className="text-white">{event.location.name}</p>
            {event.location.modern_name && (
              <p className="text-sm text-gray-400">
                (Modern: {event.location.modern_name})
              </p>
            )}
          </div>
        )}

        {/* Description */}
        {event.description && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-1">
              Description
            </h3>
            <p className="text-white leading-relaxed">{event.description}</p>
          </div>
        )}

        {/* Persons */}
        {event.persons && event.persons.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">
              Key Figures
            </h3>
            <div className="space-y-2">
              {event.persons.map((person) => (
                <div
                  key={person.id}
                  className="flex items-center gap-2 p-2 bg-white/5 rounded"
                >
                  <div className="w-8 h-8 bg-chaldea-accent rounded-full flex items-center justify-center text-sm">
                    {person.name.charAt(0)}
                  </div>
                  <div>
                    <div className="text-white text-sm">{person.name}</div>
                    {person.role && (
                      <div className="text-xs text-gray-400">{person.role}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sources - LAPLACE */}
        {event.sources && event.sources.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">
              Sources (LAPLACE)
            </h3>
            <div className="space-y-2">
              {event.sources.map((source) => (
                <div
                  key={source.id}
                  className="p-2 bg-white/5 rounded text-sm"
                >
                  <div className="text-white">{source.name}</div>
                  {source.author && (
                    <div className="text-xs text-gray-400">
                      by {source.author}
                    </div>
                  )}
                  {source.url && (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-chaldea-gold hover:underline"
                    >
                      View Source →
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Wikipedia link */}
        {event.wikipedia_url && (
          <a
            href={event.wikipedia_url}
            target="_blank"
            rel="noopener noreferrer"
            className="block mt-4 text-center py-2 bg-white/10 rounded hover:bg-white/20 text-sm"
          >
            Read more on Wikipedia →
          </a>
        )}
      </div>
    </div>
  )
}
