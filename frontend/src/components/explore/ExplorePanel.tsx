/**
 * ExplorePanel - Browse pre-curation NER entities
 *
 * Shows the raw extracted entities before they go through Historical Chain curation.
 * Allows filtering, searching, and browsing by entity type.
 */
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import './ExplorePanel.css'

interface ExploreStats {
  total_persons: number
  total_locations: number
  total_events: number
  total_polities: number
  total_periods: number
  persons_by_era: Record<string, number>
  persons_by_certainty: Record<string, number>
  locations_by_type: Record<string, number>
}

interface EntityItem {
  id: number
  name: string
  name_ko?: string
  // Person fields
  role?: string
  era?: string
  birth_year?: number
  death_year?: number
  mention_count?: number
  certainty?: string
  avg_confidence?: number
  // Location fields
  type?: string
  modern_name?: string
  country?: string
  latitude?: number
  longitude?: number
  // Event fields
  title?: string
  date_start?: number
  date_end?: number
  temporal_scale?: string
  // Polity fields
  polity_type?: string
  start_year?: number
  end_year?: number
  // Period fields
  year_start?: number
  year_end?: number
  scale?: string
  // Source fields
  author?: string
  archive_type?: string
  original_year?: number
}

interface PaginatedResponse {
  items: EntityItem[]
  total: number
  limit: number
  offset: number
}

type EntityType = 'persons' | 'locations' | 'events' | 'polities' | 'periods' | 'sources'

const ENTITY_TYPES: { key: EntityType; label: string; icon: string }[] = [
  { key: 'persons', label: 'Persons', icon: '👤' },
  { key: 'locations', label: 'Locations', icon: '📍' },
  { key: 'events', label: 'Events', icon: '📜' },
  { key: 'polities', label: 'Polities', icon: '🏛️' },
  { key: 'periods', label: 'Periods', icon: '⏳' },
  { key: 'sources', label: 'Sources', icon: '📚' },
]

interface ExplorePanelProps {
  isOpen: boolean
  onClose: () => void
}

export function ExplorePanel({ isOpen, onClose }: ExplorePanelProps) {
  const [entityType, setEntityType] = useState<EntityType>('persons')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(0)
  const [sortBy, setSortBy] = useState('mention_count')
  const limit = 50

  // Reset page when entity type or search changes
  useEffect(() => {
    setPage(0)
  }, [entityType, searchQuery])

  // Fetch stats
  const { data: stats } = useQuery<ExploreStats>({
    queryKey: ['explore-stats'],
    queryFn: async () => {
      const res = await api.get('/explore/stats')
      return res.data
    },
    enabled: isOpen,
  })

  // Fetch entities
  const { data: entitiesData, isLoading } = useQuery<PaginatedResponse>({
    queryKey: ['explore-entities', entityType, searchQuery, page, sortBy],
    queryFn: async () => {
      const params: Record<string, unknown> = {
        limit,
        offset: page * limit,
      }
      if (searchQuery) {
        params.q = searchQuery
      }
      if (entityType === 'persons') {
        params.sort_by = sortBy
        params.sort_order = 'desc'
      }
      const res = await api.get(`/explore/${entityType}`, { params })
      return res.data
    },
    enabled: isOpen,
  })

  if (!isOpen) return null

  const totalPages = entitiesData ? Math.ceil(entitiesData.total / limit) : 0

  return (
    <div className="explore-panel-overlay" onClick={onClose}>
      <div className="explore-panel" onClick={(e) => e.stopPropagation()}>
        <header className="explore-header">
          <div className="explore-title">
            <span className="explore-icon">🔍</span>
            <h2>Entity Explorer</h2>
            <span className="explore-subtitle">Pre-Curation Data Pool</span>
          </div>
          <button className="explore-close" onClick={onClose}>✕</button>
        </header>

        {/* Stats Summary */}
        {stats && (
          <div className="explore-stats">
            <div className="stat-item">
              <span className="stat-value">{stats.total_persons.toLocaleString()}</span>
              <span className="stat-label">Persons</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_locations.toLocaleString()}</span>
              <span className="stat-label">Locations</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_events.toLocaleString()}</span>
              <span className="stat-label">Events</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_polities.toLocaleString()}</span>
              <span className="stat-label">Polities</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_periods.toLocaleString()}</span>
              <span className="stat-label">Periods</span>
            </div>
          </div>
        )}

        {/* Entity Type Tabs */}
        <div className="explore-tabs">
          {ENTITY_TYPES.map((type) => (
            <button
              key={type.key}
              className={`explore-tab ${entityType === type.key ? 'active' : ''}`}
              onClick={() => setEntityType(type.key)}
            >
              <span className="tab-icon">{type.icon}</span>
              <span className="tab-label">{type.label}</span>
            </button>
          ))}
        </div>

        {/* Search & Filter */}
        <div className="explore-controls">
          <input
            type="text"
            className="explore-search"
            placeholder={`Search ${entityType}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {entityType === 'persons' && (
            <select
              className="explore-sort"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="mention_count">Most Mentioned</option>
              <option value="name">Name (A-Z)</option>
              <option value="birth_year">Birth Year</option>
              <option value="avg_confidence">Confidence</option>
            </select>
          )}
        </div>

        {/* Results */}
        <div className="explore-results">
          {isLoading ? (
            <div className="explore-loading">Loading...</div>
          ) : entitiesData?.items.length === 0 ? (
            <div className="explore-empty">No results found</div>
          ) : (
            <table className="explore-table">
              <thead>
                <tr>
                  {entityType === 'persons' && (
                    <>
                      <th>Name</th>
                      <th>Role</th>
                      <th>Era</th>
                      <th>Birth</th>
                      <th>Death</th>
                      <th>Mentions</th>
                      <th>Certainty</th>
                    </>
                  )}
                  {entityType === 'locations' && (
                    <>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Modern Name</th>
                      <th>Country</th>
                      <th>Coordinates</th>
                    </>
                  )}
                  {entityType === 'events' && (
                    <>
                      <th>Title</th>
                      <th>Date</th>
                      <th>Certainty</th>
                      <th>Scale</th>
                    </>
                  )}
                  {entityType === 'polities' && (
                    <>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Start</th>
                      <th>End</th>
                      <th>Certainty</th>
                    </>
                  )}
                  {entityType === 'periods' && (
                    <>
                      <th>Name</th>
                      <th>Start</th>
                      <th>End</th>
                      <th>Scale</th>
                    </>
                  )}
                  {entityType === 'sources' && (
                    <>
                      <th>Title</th>
                      <th>Author</th>
                      <th>Archive</th>
                      <th>Year</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {entitiesData?.items.map((item) => (
                  <tr key={item.id}>
                    {entityType === 'persons' && (
                      <>
                        <td className="name-cell">{item.name}</td>
                        <td>{item.role || '-'}</td>
                        <td>{item.era || '-'}</td>
                        <td>{formatYear(item.birth_year)}</td>
                        <td>{formatYear(item.death_year)}</td>
                        <td className="number-cell">{item.mention_count || 0}</td>
                        <td>
                          <span className={`certainty-badge ${item.certainty || 'unknown'}`}>
                            {item.certainty || '-'}
                          </span>
                        </td>
                      </>
                    )}
                    {entityType === 'locations' && (
                      <>
                        <td className="name-cell">{item.name}</td>
                        <td>{item.type || '-'}</td>
                        <td>{item.modern_name || '-'}</td>
                        <td>{item.country || '-'}</td>
                        <td>
                          {item.latitude && item.longitude
                            ? `${item.latitude.toFixed(2)}, ${item.longitude.toFixed(2)}`
                            : '-'}
                        </td>
                      </>
                    )}
                    {entityType === 'events' && (
                      <>
                        <td className="name-cell">{item.title || item.name}</td>
                        <td>{formatYear(item.date_start)}</td>
                        <td>
                          <span className={`certainty-badge ${item.certainty || 'unknown'}`}>
                            {item.certainty || '-'}
                          </span>
                        </td>
                        <td>{item.temporal_scale || '-'}</td>
                      </>
                    )}
                    {entityType === 'polities' && (
                      <>
                        <td className="name-cell">{item.name}</td>
                        <td>{item.polity_type || '-'}</td>
                        <td>{formatYear(item.start_year)}</td>
                        <td>{formatYear(item.end_year)}</td>
                        <td>
                          <span className={`certainty-badge ${item.certainty || 'unknown'}`}>
                            {item.certainty || '-'}
                          </span>
                        </td>
                      </>
                    )}
                    {entityType === 'periods' && (
                      <>
                        <td className="name-cell">{item.name}</td>
                        <td>{formatYear(item.year_start)}</td>
                        <td>{formatYear(item.year_end)}</td>
                        <td>{item.scale || '-'}</td>
                      </>
                    )}
                    {entityType === 'sources' && (
                      <>
                        <td className="name-cell">{item.title || item.name}</td>
                        <td>{item.author || '-'}</td>
                        <td>
                          <span className={`archive-badge ${item.archive_type || 'unknown'}`}>
                            {item.archive_type || '-'}
                          </span>
                        </td>
                        <td>{item.original_year || '-'}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {entitiesData && totalPages > 1 && (
          <div className="explore-pagination">
            <button
              className="pagination-btn"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              ← Previous
            </button>
            <span className="pagination-info">
              Page {page + 1} of {totalPages} ({entitiesData.total.toLocaleString()} total)
            </span>
            <button
              className="pagination-btn"
              disabled={page >= totalPages - 1}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function formatYear(year: number | null | undefined): string {
  if (year === null || year === undefined) return '-'
  const absYear = Math.abs(year)
  return year < 0 ? `${absYear} BCE` : `${absYear} CE`
}

export default ExplorePanel
