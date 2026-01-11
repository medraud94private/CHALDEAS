/**
 * TimelineBar - Enhanced horizontal timeline visualization
 *
 * Features:
 * - Visual era markers
 * - Event density heat map
 * - Click-to-jump navigation
 * - Current year indicator
 */
import { useMemo, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import './TimelineBar.css'

interface Era {
  name: string
  start: number
  end: number
  color: string
}

interface Props {
  currentYear: number
  onYearChange: (year: number) => void
  events?: Array<{ date_start: number }>
  minYear?: number
  maxYear?: number
}

const ERAS: Era[] = [
  { name: 'prehistoric', start: -3000, end: -3000, color: '#6b7280' },
  { name: 'ancient', start: -3000, end: -500, color: '#a78bfa' },
  { name: 'classical', start: -500, end: 500, color: '#3b82f6' },
  { name: 'medieval', start: 500, end: 1500, color: '#22c55e' },
  { name: 'earlyModern', start: 1500, end: 1800, color: '#f59e0b' },
  { name: 'modern', start: 1800, end: 2025, color: '#ef4444' },
]

export function TimelineBar({
  currentYear,
  onYearChange,
  events = [],
  minYear = -3000,
  maxYear = 2025
}: Props) {
  const { t } = useTranslation()
  const barRef = useRef<HTMLDivElement>(null)

  // Calculate event density per segment
  const density = useMemo(() => {
    const segments = 100
    const segmentSize = (maxYear - minYear) / segments
    const counts = new Array(segments).fill(0)

    for (const event of events) {
      const segmentIndex = Math.floor((event.date_start - minYear) / segmentSize)
      if (segmentIndex >= 0 && segmentIndex < segments) {
        counts[segmentIndex]++
      }
    }

    const maxCount = Math.max(...counts, 1)
    return counts.map(c => c / maxCount)
  }, [events, minYear, maxYear])

  // Calculate position percentage
  const yearToPercent = useCallback((year: number) => {
    return ((year - minYear) / (maxYear - minYear)) * 100
  }, [minYear, maxYear])

  // Handle click on timeline
  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!barRef.current) return
    const rect = barRef.current.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    const year = Math.round(minYear + percent * (maxYear - minYear))
    onYearChange(Math.max(minYear, Math.min(maxYear, year)))
  }

  // Handle drag on timeline
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.buttons !== 1) return // Only on primary button held
    handleClick(e)
  }

  const currentPercent = yearToPercent(currentYear)

  // Format year for display
  const formatYear = (year: number) => {
    if (year < 0) return `${Math.abs(year)} BCE`
    return `${year} CE`
  }

  // Get era for current year
  const currentEra = ERAS.find(era => currentYear >= era.start && currentYear < era.end) || ERAS[ERAS.length - 1]

  return (
    <div className="timeline-bar-container">
      {/* Era Labels */}
      <div className="timeline-eras">
        {ERAS.map((era) => {
          const startPercent = yearToPercent(Math.max(era.start, minYear))
          const endPercent = yearToPercent(Math.min(era.end, maxYear))
          const width = endPercent - startPercent

          if (width <= 0) return null

          return (
            <div
              key={era.name}
              className={`timeline-era ${currentEra.name === era.name ? 'active' : ''}`}
              style={{
                left: `${startPercent}%`,
                width: `${width}%`,
                borderBottomColor: era.color
              }}
              onClick={() => onYearChange(Math.round((era.start + era.end) / 2))}
              title={t(`era.names.${era.name}`, era.name)}
            >
              <span className="era-label">{t(`era.names.${era.name}`, era.name)}</span>
            </div>
          )
        })}
      </div>

      {/* Main Timeline Bar */}
      <div
        className="timeline-bar"
        ref={barRef}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
      >
        {/* Density Heat Map */}
        <div className="timeline-density">
          {density.map((d, i) => (
            <div
              key={i}
              className="density-segment"
              style={{
                opacity: 0.1 + d * 0.7,
                backgroundColor: d > 0.5 ? '#00d4ff' : d > 0.2 ? '#0088aa' : '#004466'
              }}
            />
          ))}
        </div>

        {/* Era Background Colors */}
        <div className="timeline-era-bg">
          {ERAS.map((era) => {
            const startPercent = yearToPercent(Math.max(era.start, minYear))
            const endPercent = yearToPercent(Math.min(era.end, maxYear))
            const width = endPercent - startPercent

            if (width <= 0) return null

            return (
              <div
                key={era.name}
                className="era-bg-segment"
                style={{
                  left: `${startPercent}%`,
                  width: `${width}%`,
                  backgroundColor: era.color
                }}
              />
            )
          })}
        </div>

        {/* Year Markers */}
        <div className="timeline-markers">
          {[-2000, -1000, 0, 1000, 2000].map(year => {
            if (year < minYear || year > maxYear) return null
            return (
              <div
                key={year}
                className="year-marker"
                style={{ left: `${yearToPercent(year)}%` }}
                onClick={(e) => { e.stopPropagation(); onYearChange(year) }}
              >
                <span className="marker-line" />
                <span className="marker-year">{year === 0 ? '1 CE' : formatYear(year)}</span>
              </div>
            )
          })}
        </div>

        {/* Current Year Indicator */}
        <div
          className="timeline-indicator"
          style={{ left: `${currentPercent}%` }}
        >
          <div className="indicator-line" />
          <div className="indicator-head" style={{ borderColor: currentEra.color }} />
          <div className="indicator-year" style={{ color: currentEra.color }}>
            {formatYear(currentYear)}
          </div>
        </div>
      </div>

      {/* Quick Jump Buttons */}
      <div className="timeline-jumps">
        <button onClick={() => onYearChange(-2500)} title="Ancient Egypt">
          🏛️ -2500
        </button>
        <button onClick={() => onYearChange(-500)} title="Classical Greece">
          🏺 -500
        </button>
        <button onClick={() => onYearChange(0)} title="Roman Empire">
          ⚔️ 1 CE
        </button>
        <button onClick={() => onYearChange(1000)} title="Medieval">
          🏰 1000
        </button>
        <button onClick={() => onYearChange(1500)} title="Renaissance">
          🎨 1500
        </button>
        <button onClick={() => onYearChange(1900)} title="Modern Era">
          🌍 1900
        </button>
      </div>
    </div>
  )
}
