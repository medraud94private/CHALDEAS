/**
 * FilterPanel - Advanced filtering options for events
 *
 * Features:
 * - Layer type filter (person/location/causal connections)
 * - Time range slider
 * - Connection strength filter
 */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import './FilterPanel.css'

export interface FilterState {
  layers: {
    person: boolean
    location: boolean
    causal: boolean
  }
  yearRange: {
    start: number
    end: number
  }
  minStrength: number
  hasConnections: boolean | null // null = any, true = only with connections, false = only without
}

interface Props {
  filters: FilterState
  onChange: (filters: FilterState) => void
  isOpen: boolean
  onToggle: () => void
}

const YEAR_MIN = -3000
const YEAR_MAX = 2025

export function FilterPanel({ filters, onChange, isOpen, onToggle }: Props) {
  const { t } = useTranslation()
  const [localYearStart, setLocalYearStart] = useState(filters.yearRange.start.toString())
  const [localYearEnd, setLocalYearEnd] = useState(filters.yearRange.end.toString())

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    onChange({ ...filters, [key]: value })
  }

  const toggleLayer = (layer: keyof FilterState['layers']) => {
    onChange({
      ...filters,
      layers: { ...filters.layers, [layer]: !filters.layers[layer] }
    })
  }

  const handleYearChange = (type: 'start' | 'end', value: string) => {
    if (type === 'start') {
      setLocalYearStart(value)
    } else {
      setLocalYearEnd(value)
    }
  }

  const applyYearRange = () => {
    const start = parseInt(localYearStart) || YEAR_MIN
    const end = parseInt(localYearEnd) || YEAR_MAX
    updateFilter('yearRange', {
      start: Math.max(YEAR_MIN, Math.min(start, end)),
      end: Math.min(YEAR_MAX, Math.max(start, end))
    })
  }

  const resetFilters = () => {
    onChange({
      layers: { person: true, location: true, causal: true },
      yearRange: { start: YEAR_MIN, end: YEAR_MAX },
      minStrength: 0,
      hasConnections: null
    })
    setLocalYearStart(YEAR_MIN.toString())
    setLocalYearEnd(YEAR_MAX.toString())
  }

  const activeFilterCount = [
    !filters.layers.person || !filters.layers.location || !filters.layers.causal,
    filters.yearRange.start !== YEAR_MIN || filters.yearRange.end !== YEAR_MAX,
    filters.minStrength > 0,
    filters.hasConnections !== null
  ].filter(Boolean).length

  return (
    <div className="filter-panel-wrapper">
      {/* Toggle Button */}
      <button className="filter-toggle-btn" onClick={onToggle}>
        <span className="filter-icon">⚙</span>
        <span>{t('filters.advanced', 'Advanced Filters')}</span>
        {activeFilterCount > 0 && (
          <span className="filter-badge">{activeFilterCount}</span>
        )}
        <span className={`filter-arrow ${isOpen ? 'open' : ''}`}>▼</span>
      </button>

      {/* Collapsible Panel */}
      <div className={`filter-panel ${isOpen ? 'open' : ''}`}>
        {/* Layer Type Filters */}
        <div className="filter-section">
          <div className="filter-section-header">
            <span className="filter-section-icon">⧉</span>
            <span>{t('filters.connectionLayers', 'Connection Layers')}</span>
          </div>
          <div className="layer-toggles">
            <button
              className={`layer-toggle ${filters.layers.person ? 'active' : ''}`}
              onClick={() => toggleLayer('person')}
            >
              <span className="layer-dot person" />
              <span>{t('filters.personLayer', 'Person')}</span>
            </button>
            <button
              className={`layer-toggle ${filters.layers.location ? 'active' : ''}`}
              onClick={() => toggleLayer('location')}
            >
              <span className="layer-dot location" />
              <span>{t('filters.locationLayer', 'Location')}</span>
            </button>
            <button
              className={`layer-toggle ${filters.layers.causal ? 'active' : ''}`}
              onClick={() => toggleLayer('causal')}
            >
              <span className="layer-dot causal" />
              <span>{t('filters.causalLayer', 'Causal')}</span>
            </button>
          </div>
        </div>

        {/* Year Range */}
        <div className="filter-section">
          <div className="filter-section-header">
            <span className="filter-section-icon">📅</span>
            <span>{t('filters.yearRange', 'Year Range')}</span>
          </div>
          <div className="year-range-inputs">
            <div className="year-input-group">
              <label>{t('filters.from', 'From')}</label>
              <input
                type="number"
                value={localYearStart}
                onChange={(e) => handleYearChange('start', e.target.value)}
                onBlur={applyYearRange}
                onKeyDown={(e) => e.key === 'Enter' && applyYearRange()}
                min={YEAR_MIN}
                max={YEAR_MAX}
              />
              <span className="year-hint">
                {parseInt(localYearStart) < 0 ? 'BCE' : 'CE'}
              </span>
            </div>
            <span className="year-separator">~</span>
            <div className="year-input-group">
              <label>{t('filters.to', 'To')}</label>
              <input
                type="number"
                value={localYearEnd}
                onChange={(e) => handleYearChange('end', e.target.value)}
                onBlur={applyYearRange}
                onKeyDown={(e) => e.key === 'Enter' && applyYearRange()}
                min={YEAR_MIN}
                max={YEAR_MAX}
              />
              <span className="year-hint">
                {parseInt(localYearEnd) < 0 ? 'BCE' : 'CE'}
              </span>
            </div>
          </div>
          <div className="year-presets">
            <button onClick={() => { setLocalYearStart('-3000'); setLocalYearEnd('-500'); applyYearRange() }}>
              {t('filters.ancient', 'Ancient')}
            </button>
            <button onClick={() => { setLocalYearStart('-500'); setLocalYearEnd('500'); applyYearRange() }}>
              {t('filters.classical', 'Classical')}
            </button>
            <button onClick={() => { setLocalYearStart('500'); setLocalYearEnd('1500'); applyYearRange() }}>
              {t('filters.medieval', 'Medieval')}
            </button>
            <button onClick={() => { setLocalYearStart('1500'); setLocalYearEnd('2025'); applyYearRange() }}>
              {t('filters.modern', 'Modern')}
            </button>
          </div>
        </div>

        {/* Connection Strength */}
        <div className="filter-section">
          <div className="filter-section-header">
            <span className="filter-section-icon">💪</span>
            <span>{t('filters.minStrength', 'Min Connection Strength')}</span>
          </div>
          <div className="strength-slider">
            <input
              type="range"
              min="0"
              max="10"
              step="1"
              value={filters.minStrength}
              onChange={(e) => updateFilter('minStrength', parseInt(e.target.value))}
            />
            <div className="strength-labels">
              <span className={filters.minStrength === 0 ? 'active' : ''}>All</span>
              <span className={filters.minStrength >= 3 && filters.minStrength < 7 ? 'active' : ''}>Medium</span>
              <span className={filters.minStrength >= 7 ? 'active' : ''}>Strong</span>
            </div>
            <div className="strength-value">{filters.minStrength}</div>
          </div>
        </div>

        {/* Has Connections Filter */}
        <div className="filter-section">
          <div className="filter-section-header">
            <span className="filter-section-icon">🔗</span>
            <span>{t('filters.connectionStatus', 'Connection Status')}</span>
          </div>
          <div className="connection-toggles">
            <button
              className={`connection-toggle ${filters.hasConnections === null ? 'active' : ''}`}
              onClick={() => updateFilter('hasConnections', null)}
            >
              {t('filters.anyConnection', 'Any')}
            </button>
            <button
              className={`connection-toggle ${filters.hasConnections === true ? 'active' : ''}`}
              onClick={() => updateFilter('hasConnections', true)}
            >
              {t('filters.hasConnections', 'Connected')}
            </button>
            <button
              className={`connection-toggle ${filters.hasConnections === false ? 'active' : ''}`}
              onClick={() => updateFilter('hasConnections', false)}
            >
              {t('filters.noConnections', 'Isolated')}
            </button>
          </div>
        </div>

        {/* Reset Button */}
        <button className="filter-reset-btn" onClick={resetFilters}>
          {t('filters.reset', 'Reset All Filters')}
        </button>
      </div>
    </div>
  )
}

export const defaultFilters: FilterState = {
  layers: { person: true, location: true, causal: true },
  yearRange: { start: YEAR_MIN, end: YEAR_MAX },
  minStrength: 0,
  hasConnections: null
}
