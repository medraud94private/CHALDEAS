/**
 * UnifiedTimeline - Unified timeline component with switchable display modes
 *
 * Modes:
 * - compact: Single line with essential controls
 * - standard: Two lines with density bar + controls (default)
 * - expanded: Full featured with all controls visible
 */
import { useMemo, useRef, useCallback, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useTimelineStore, ERAS, TimelineDisplayMode } from '../../store/timelineStore'
import './UnifiedTimeline.css'

// Era definitions with colors
const ERA_STYLES = [
  { name: 'ancient', start: -3000, end: -500, color: '#a78bfa' },
  { name: 'classical', start: -500, end: 500, color: '#3b82f6' },
  { name: 'medieval', start: 500, end: 1500, color: '#22c55e' },
  { name: 'earlyModern', start: 1500, end: 1800, color: '#f59e0b' },
  { name: 'modern', start: 1800, end: 2025, color: '#ef4444' },
]

// Speed presets
const SPEED_PRESETS = [
  { label: '1x', value: 5 },
  { label: '2x', value: 10 },
  { label: '5x', value: 25 },
  { label: '10x', value: 50 },
]

interface Props {
  events?: Array<{ date_start: number }>
}

export function UnifiedTimeline({ events = [] }: Props) {
  const { t } = useTranslation()
  const barRef = useRef<HTMLDivElement>(null)
  const animationRef = useRef<number>()
  const lastTimeRef = useRef<number>(0)

  const {
    currentYear,
    yearRange,
    isPlaying,
    playbackSpeed,
    displayMode,
    setCurrentYear,
    play,
    pause,
    setPlaybackSpeed,
    setDisplayMode,
    jumpToEra,
  } = useTimelineStore()

  const minYear = yearRange.min
  const maxYear = yearRange.max

  // Animation loop for playback
  const animate = useCallback(
    (timestamp: number) => {
      if (!lastTimeRef.current) {
        lastTimeRef.current = timestamp
      }

      const deltaTime = timestamp - lastTimeRef.current
      lastTimeRef.current = timestamp

      const yearDelta = (playbackSpeed * deltaTime) / 1000

      setCurrentYear((prev: number) => {
        const newYear = prev + yearDelta
        if (newYear >= maxYear) {
          pause()
          return maxYear
        }
        return Math.round(newYear)
      })

      animationRef.current = requestAnimationFrame(animate)
    },
    [playbackSpeed, maxYear, setCurrentYear, pause]
  )

  useEffect(() => {
    if (isPlaying) {
      lastTimeRef.current = 0
      animationRef.current = requestAnimationFrame(animate)
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [isPlaying, animate])

  // Calculate event density
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

  // Year to percentage
  const yearToPercent = useCallback((year: number) => {
    return ((year - minYear) / (maxYear - minYear)) * 100
  }, [minYear, maxYear])

  // Handle bar click/drag
  const handleBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!barRef.current) return
    const rect = barRef.current.getBoundingClientRect()
    const percent = (e.clientX - rect.left) / rect.width
    const year = Math.round(minYear + percent * (maxYear - minYear))
    setCurrentYear(Math.max(minYear, Math.min(maxYear, year)))
  }

  const handleBarDrag = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.buttons !== 1) return
    handleBarClick(e)
  }

  // Toggle play/pause
  const handlePlayPause = () => {
    if (isPlaying) {
      pause()
    } else {
      if (currentYear >= maxYear - 10) {
        setCurrentYear(minYear)
      }
      play()
    }
  }

  // Format year
  const formatYear = (year: number) => {
    if (year < 0) return `${Math.abs(year)} BCE`
    return `${year} CE`
  }

  // Current era
  const currentEra = useMemo(() => {
    return ERA_STYLES.find(era => currentYear >= era.start && currentYear < era.end) || ERA_STYLES[ERA_STYLES.length - 1]
  }, [currentYear])

  // Progress percentage
  const progress = ((currentYear - minYear) / (maxYear - minYear)) * 100

  // Cycle display mode
  const cycleDisplayMode = () => {
    const modes: TimelineDisplayMode[] = ['compact', 'standard', 'expanded']
    const currentIndex = modes.indexOf(displayMode)
    const nextIndex = (currentIndex + 1) % modes.length
    setDisplayMode(modes[nextIndex])
  }

  return (
    <div className={`unified-timeline mode-${displayMode}`}>
      {/* Mode Toggle Button */}
      <button
        className="timeline-mode-toggle"
        onClick={cycleDisplayMode}
        title={t('timeline.switchMode', 'Switch timeline mode')}
      >
        <span className="mode-icon">
          {displayMode === 'compact' ? '━' : displayMode === 'standard' ? '☰' : '▤'}
        </span>
      </button>

      {/* Era Labels - all modes except compact */}
      {displayMode !== 'compact' && (
        <div className="timeline-eras">
          {ERA_STYLES.map((era) => {
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
                onClick={() => jumpToEra(Math.round((era.start + era.end) / 2))}
              >
                <span className="era-label">{t(`era.names.${era.name}`, era.name)}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Main Timeline Bar */}
      <div className="timeline-main-row">
        {/* Skip to start - expanded only */}
        {displayMode === 'expanded' && (
          <button
            className="timeline-btn timeline-skip"
            onClick={() => { pause(); setCurrentYear(minYear) }}
            title={t('timeline.reset', 'Go to beginning')}
          >
            ⏮
          </button>
        )}

        {/* Play/Pause */}
        <button
          className={`timeline-btn timeline-play ${isPlaying ? 'playing' : ''}`}
          onClick={handlePlayPause}
          title={isPlaying ? t('timeline.pause') : t('timeline.play')}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>

        {/* Skip to end - expanded only */}
        {displayMode === 'expanded' && (
          <button
            className="timeline-btn timeline-skip"
            onClick={() => { pause(); setCurrentYear(maxYear) }}
            title={t('timeline.end', 'Go to end')}
          >
            ⏭
          </button>
        )}

        {/* Progress Bar */}
        <div
          className="timeline-bar"
          ref={barRef}
          onClick={handleBarClick}
          onMouseMove={handleBarDrag}
        >
          {/* Density Heat Map */}
          <div className="timeline-density">
            {density.map((d, i) => (
              <div
                key={i}
                className="density-segment"
                style={{
                  opacity: 0.1 + d * 0.6,
                  backgroundColor: d > 0.5 ? 'var(--chaldea-cyan)' : d > 0.2 ? '#0088aa' : '#004466'
                }}
              />
            ))}
          </div>

          {/* Era Background Colors */}
          <div className="timeline-era-bg">
            {ERA_STYLES.map((era) => {
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

          {/* Progress Fill */}
          <div
            className="timeline-progress-fill"
            style={{ width: `${progress}%` }}
          />

          {/* Year Markers - standard and expanded */}
          {displayMode !== 'compact' && (
            <div className="timeline-markers">
              {[-2000, -1000, 0, 1000, 2000].map(year => {
                if (year < minYear || year > maxYear) return null
                return (
                  <div
                    key={year}
                    className="year-marker"
                    style={{ left: `${yearToPercent(year)}%` }}
                    onClick={(e) => { e.stopPropagation(); setCurrentYear(year) }}
                  >
                    <span className="marker-line" />
                    <span className="marker-year">{year === 0 ? '1 CE' : formatYear(year)}</span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Current Position Indicator */}
          <div
            className="timeline-indicator"
            style={{ left: `${progress}%` }}
          >
            <div className="indicator-head" style={{ borderColor: currentEra.color }} />
            <div className="indicator-line" style={{ backgroundColor: currentEra.color }} />
          </div>
        </div>

        {/* Year Display */}
        <div className="timeline-year-display">
          <span className="year-number" style={{ color: currentEra.color }}>
            {Math.abs(currentYear)}
          </span>
          <span className="year-era">
            {currentYear < 0 ? 'BCE' : 'CE'}
          </span>
        </div>

        {/* Speed Controls - standard and expanded */}
        {displayMode !== 'compact' && (
          <div className="timeline-speed">
            {SPEED_PRESETS.map((preset) => (
              <button
                key={preset.value}
                className={`speed-btn ${playbackSpeed === preset.value ? 'active' : ''}`}
                onClick={() => setPlaybackSpeed(preset.value)}
              >
                {preset.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Quick Jump Buttons - expanded only */}
      {displayMode === 'expanded' && (
        <div className="timeline-jumps">
          {ERAS.map((era) => (
            <button
              key={era.year}
              onClick={() => jumpToEra(era.year)}
              className={Math.abs(currentYear - era.year) < 200 ? 'active' : ''}
            >
              {era.label}
            </button>
          ))}
        </div>
      )}

      {/* Step Controls - expanded only */}
      {displayMode === 'expanded' && (
        <div className="timeline-step-controls">
          <button onClick={() => setCurrentYear(currentYear - 100)}>-100</button>
          <button onClick={() => setCurrentYear(currentYear - 10)}>-10</button>
          <span className="step-year">{formatYear(currentYear)}</span>
          <button onClick={() => setCurrentYear(currentYear + 10)}>+10</button>
          <button onClick={() => setCurrentYear(currentYear + 100)}>+100</button>
        </div>
      )}
    </div>
  )
}
