/**
 * VirtualEventList - Virtualized event list for performance
 *
 * Uses @tanstack/react-virtual for efficient rendering of large lists.
 * Only renders visible items + overscan buffer.
 */
import { useRef, useCallback } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useTranslation } from 'react-i18next'
import type { Event } from '../../types'
import './VirtualEventList.css'

interface Props {
  events: Event[]
  selectedEventId?: number | string | null
  onEventClick: (event: Event) => void
  onBookmarkToggle?: (eventId: number | string) => void
  bookmarkedIds?: Set<number | string>
}

const ITEM_HEIGHT = 88 // Estimated height of each event card
const OVERSCAN = 5 // Number of items to render outside viewport

export function VirtualEventList({
  events,
  selectedEventId,
  onEventClick,
  onBookmarkToggle,
  bookmarkedIds = new Set()
}: Props) {
  const { t } = useTranslation()
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ITEM_HEIGHT,
    overscan: OVERSCAN,
  })

  const formatYear = useCallback((year: number) => {
    const absYear = Math.abs(year)
    const era = year < 0 ? 'BCE' : 'CE'
    return { number: absYear, era }
  }, [])

  const items = virtualizer.getVirtualItems()

  return (
    <div
      ref={parentRef}
      className="virtual-event-list"
    >
      <div
        className="virtual-event-list-inner"
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          position: 'relative',
        }}
      >
        {items.map((virtualRow) => {
          const event = events[virtualRow.index]
          const year = formatYear(event.date_start)
          const cat = typeof event.category === 'string' ? event.category : 'general'
          const firstPerson = event.persons?.[0]
          const firstLocation = event.location || event.locations?.[0]
          const isSelected = selectedEventId === event.id
          const isBookmarked = bookmarkedIds.has(event.id)

          return (
            <div
              key={event.id}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              className={`virtual-event-card ${isSelected ? 'selected' : ''}`}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
              onClick={() => onEventClick(event)}
            >
              {/* Header: Year + Category + Bookmark */}
              <div className="event-card-header">
                <div className="event-card-year">
                  <span className="year-era">{year.era}</span>
                  <span className="year-number">{year.number}</span>
                </div>
                <span className={`event-card-category ${cat}`}>
                  {t(`categories.${cat}`, cat)}
                </span>
                {onBookmarkToggle && (
                  <button
                    className={`event-bookmark-btn ${isBookmarked ? 'active' : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      onBookmarkToggle(event.id)
                    }}
                    title={isBookmarked ? t('bookmark.remove', 'Remove bookmark') : t('bookmark.add', 'Add bookmark')}
                  >
                    {isBookmarked ? '★' : '☆'}
                  </button>
                )}
              </div>

              {/* Title */}
              <div className="event-card-title">{event.title}</div>

              {/* Meta: WHO + WHERE */}
              <div className="event-card-meta">
                {firstPerson && (
                  <span className="event-card-who" title={firstPerson.name}>
                    <span className="meta-icon">👤</span>
                    <span className="meta-text">{firstPerson.name}</span>
                    {event.persons && event.persons.length > 1 && (
                      <span className="meta-more">+{event.persons.length - 1}</span>
                    )}
                  </span>
                )}
                {firstLocation && (
                  <span className="event-card-where" title={firstLocation.name}>
                    <span className="meta-icon">📍</span>
                    <span className="meta-text">{firstLocation.name}</span>
                  </span>
                )}
              </div>

              {/* Selection Indicator */}
              <div className="event-card-indicator" />
            </div>
          )
        })}
      </div>

      {/* Empty State */}
      {events.length === 0 && (
        <div className="virtual-event-empty">
          {t('sidebar.noEvents', 'No events found')}
        </div>
      )}
    </div>
  )
}
