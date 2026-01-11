/**
 * Bookmark Store - Manages user's bookmarked events
 *
 * Persists bookmarks to localStorage for offline access.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type EventId = number | string

interface BookmarkState {
  bookmarkedIds: Set<EventId>
  addBookmark: (eventId: EventId) => void
  removeBookmark: (eventId: EventId) => void
  toggleBookmark: (eventId: EventId) => void
  isBookmarked: (eventId: EventId) => boolean
  clearBookmarks: () => void
}

export const useBookmarkStore = create<BookmarkState>()(
  persist(
    (set, get) => ({
      bookmarkedIds: new Set<EventId>(),

      addBookmark: (eventId: EventId) => {
        set((state) => ({
          bookmarkedIds: new Set([...state.bookmarkedIds, eventId])
        }))
      },

      removeBookmark: (eventId: EventId) => {
        set((state) => {
          const newSet = new Set(state.bookmarkedIds)
          newSet.delete(eventId)
          return { bookmarkedIds: newSet }
        })
      },

      toggleBookmark: (eventId: EventId) => {
        const { bookmarkedIds, addBookmark, removeBookmark } = get()
        if (bookmarkedIds.has(eventId)) {
          removeBookmark(eventId)
        } else {
          addBookmark(eventId)
        }
      },

      isBookmarked: (eventId: EventId) => {
        return get().bookmarkedIds.has(eventId)
      },

      clearBookmarks: () => {
        set({ bookmarkedIds: new Set() })
      },
    }),
    {
      name: 'chaldeas-bookmarks',
      // Custom serialization for Set
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name)
          if (!str) return null
          const data = JSON.parse(str)
          return {
            ...data,
            state: {
              ...data.state,
              bookmarkedIds: new Set(data.state.bookmarkedIds || [])
            }
          }
        },
        setItem: (name, value) => {
          const data = {
            ...value,
            state: {
              ...value.state,
              bookmarkedIds: [...value.state.bookmarkedIds]
            }
          }
          localStorage.setItem(name, JSON.stringify(data))
        },
        removeItem: (name) => localStorage.removeItem(name)
      }
    }
  )
)
