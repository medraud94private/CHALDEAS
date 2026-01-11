/**
 * SearchAutocomplete - Smart search with autocomplete suggestions
 *
 * Features:
 * - Debounced search input
 * - Categorized suggestions (Events, Persons, Locations)
 * - Keyboard navigation (up/down/enter/escape)
 * - Recent searches history
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import './SearchAutocomplete.css'

interface SearchResult {
  id: number
  type: 'event' | 'person' | 'location'
  title: string
  subtitle?: string
  year?: number | null
}

interface Props {
  onSelectEvent?: (eventId: number) => void
  onSelectPerson?: (personId: number) => void
  onSelectLocation?: (locationId: number) => void
  onSearch?: (query: string) => void
  placeholder?: string
}

const DEBOUNCE_MS = 300
const MAX_RECENT = 5

export function SearchAutocomplete({
  onSelectEvent,
  onSelectPerson,
  onSelectLocation,
  onSearch,
  placeholder
}: Props) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(-1)
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('chaldeas-recent-searches') || '[]')
    } catch {
      return []
    }
  })

  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query])

  // Fetch search suggestions
  const { data: suggestions, isLoading } = useQuery({
    queryKey: ['search-suggestions', debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery || debouncedQuery.length < 2) return { results: [] }
      const res = await api.get('/search', {
        params: { q: debouncedQuery, limit: 15 }
      })
      return res.data
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 30000, // Cache for 30 seconds
  })

  // Process results into categorized groups
  const groupedResults = useCallback(() => {
    if (!suggestions?.results) return { events: [], persons: [], locations: [] }

    const events: SearchResult[] = []
    const persons: SearchResult[] = []
    const locations: SearchResult[] = []

    for (const item of suggestions.results) {
      const result: SearchResult = {
        id: item.id,
        type: item.type,
        title: item.title || item.name,
        subtitle: item.description?.slice(0, 60),
        year: item.date_start || item.birth_year
      }

      switch (item.type) {
        case 'event':
          events.push(result)
          break
        case 'person':
          persons.push(result)
          break
        case 'location':
          locations.push(result)
          break
      }
    }

    return { events: events.slice(0, 5), persons: persons.slice(0, 5), locations: locations.slice(0, 5) }
  }, [suggestions])

  const results = groupedResults()
  const allResults = [...results.events, ...results.persons, ...results.locations]

  // Save to recent searches
  const saveRecentSearch = (searchTerm: string) => {
    const updated = [searchTerm, ...recentSearches.filter(s => s !== searchTerm)].slice(0, MAX_RECENT)
    setRecentSearches(updated)
    localStorage.setItem('chaldeas-recent-searches', JSON.stringify(updated))
  }

  // Handle selection
  const handleSelect = (result: SearchResult) => {
    saveRecentSearch(result.title)
    setQuery('')
    setIsOpen(false)

    switch (result.type) {
      case 'event':
        onSelectEvent?.(result.id)
        break
      case 'person':
        onSelectPerson?.(result.id)
        break
      case 'location':
        onSelectLocation?.(result.id)
        break
    }
  }

  // Handle direct search
  const handleSearch = () => {
    if (query.trim()) {
      saveRecentSearch(query.trim())
      onSearch?.(query.trim())
      setIsOpen(false)
    }
  }

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => Math.min(prev + 1, allResults.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => Math.max(prev - 1, -1))
        break
      case 'Enter':
        e.preventDefault()
        if (selectedIndex >= 0 && allResults[selectedIndex]) {
          handleSelect(allResults[selectedIndex])
        } else {
          handleSearch()
        }
        break
      case 'Escape':
        setIsOpen(false)
        inputRef.current?.blur()
        break
    }
  }

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const formatYear = (year: number | null | undefined) => {
    if (year === null || year === undefined) return ''
    if (year < 0) return `${Math.abs(year)} BCE`
    return `${year} CE`
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'event': return '📜'
      case 'person': return '👤'
      case 'location': return '📍'
      default: return '•'
    }
  }

  const showDropdown = isOpen && (query.length >= 2 || recentSearches.length > 0)

  return (
    <div className="search-autocomplete" ref={containerRef}>
      <div className="search-input-wrapper">
        <span className="search-icon">🔍</span>
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder={placeholder || t('sidebar.searchPlaceholder', 'Search events, people, places...')}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setSelectedIndex(-1)
            setIsOpen(true)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button
            className="search-clear"
            onClick={() => {
              setQuery('')
              inputRef.current?.focus()
            }}
          >
            ✕
          </button>
        )}
        {isLoading && <span className="search-loading" />}
      </div>

      {showDropdown && (
        <div className="search-dropdown">
          {/* Recent Searches (when no query) */}
          {query.length < 2 && recentSearches.length > 0 && (
            <div className="search-section">
              <div className="search-section-header">
                <span>🕐</span>
                <span>{t('search.recent', 'Recent Searches')}</span>
              </div>
              {recentSearches.map((term, idx) => (
                <div
                  key={idx}
                  className="search-item recent"
                  onClick={() => {
                    setQuery(term)
                    setDebouncedQuery(term)
                  }}
                >
                  <span className="search-item-icon">↩</span>
                  <span className="search-item-title">{term}</span>
                </div>
              ))}
              <button
                className="search-clear-recent"
                onClick={() => {
                  setRecentSearches([])
                  localStorage.removeItem('chaldeas-recent-searches')
                }}
              >
                {t('search.clearRecent', 'Clear recent searches')}
              </button>
            </div>
          )}

          {/* Search Results */}
          {query.length >= 2 && (
            <>
              {/* Events */}
              {results.events.length > 0 && (
                <div className="search-section">
                  <div className="search-section-header">
                    <span>📜</span>
                    <span>{t('search.events', 'Events')}</span>
                    <span className="search-count">{results.events.length}</span>
                  </div>
                  {results.events.map((item, idx) => (
                    <div
                      key={`event-${item.id}`}
                      className={`search-item ${selectedIndex === idx ? 'selected' : ''}`}
                      onClick={() => handleSelect(item)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                    >
                      <span className="search-item-icon">{getTypeIcon(item.type)}</span>
                      <div className="search-item-content">
                        <span className="search-item-title">{item.title}</span>
                        {item.year && <span className="search-item-year">{formatYear(item.year)}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Persons */}
              {results.persons.length > 0 && (
                <div className="search-section">
                  <div className="search-section-header">
                    <span>👤</span>
                    <span>{t('search.persons', 'People')}</span>
                    <span className="search-count">{results.persons.length}</span>
                  </div>
                  {results.persons.map((item, idx) => {
                    const actualIdx = results.events.length + idx
                    return (
                      <div
                        key={`person-${item.id}`}
                        className={`search-item ${selectedIndex === actualIdx ? 'selected' : ''}`}
                        onClick={() => handleSelect(item)}
                        onMouseEnter={() => setSelectedIndex(actualIdx)}
                      >
                        <span className="search-item-icon">{getTypeIcon(item.type)}</span>
                        <div className="search-item-content">
                          <span className="search-item-title">{item.title}</span>
                          {item.year && <span className="search-item-year">{formatYear(item.year)}</span>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Locations */}
              {results.locations.length > 0 && (
                <div className="search-section">
                  <div className="search-section-header">
                    <span>📍</span>
                    <span>{t('search.locations', 'Places')}</span>
                    <span className="search-count">{results.locations.length}</span>
                  </div>
                  {results.locations.map((item, idx) => {
                    const actualIdx = results.events.length + results.persons.length + idx
                    return (
                      <div
                        key={`location-${item.id}`}
                        className={`search-item ${selectedIndex === actualIdx ? 'selected' : ''}`}
                        onClick={() => handleSelect(item)}
                        onMouseEnter={() => setSelectedIndex(actualIdx)}
                      >
                        <span className="search-item-icon">{getTypeIcon(item.type)}</span>
                        <div className="search-item-content">
                          <span className="search-item-title">{item.title}</span>
                          {item.subtitle && <span className="search-item-subtitle">{item.subtitle}</span>}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}

              {/* No Results */}
              {allResults.length === 0 && !isLoading && (
                <div className="search-no-results">
                  <span>{t('search.noResults', 'No results found for')}</span>
                  <span className="search-query">"{query}"</span>
                </div>
              )}

              {/* Search All Button */}
              {query.length >= 2 && (
                <button className="search-all-btn" onClick={handleSearch}>
                  {t('search.searchAll', 'Search all for')} "{query}"
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
