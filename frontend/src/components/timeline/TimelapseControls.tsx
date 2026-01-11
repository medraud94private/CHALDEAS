/**
 * TimelapseControls - Time travel animation controls
 *
 * Provides play/pause, speed control, and progress visualization
 * for automatic time progression through history.
 */
import { useEffect, useRef, useCallback } from 'react'
import { useTimelineStore, ERAS } from '../../store/timelineStore'
import { useTranslation } from 'react-i18next'
import './TimelapseControls.css'

// Speed presets (years per second)
const SPEED_PRESETS = [
  { label: '1x', value: 5 },
  { label: '2x', value: 10 },
  { label: '5x', value: 25 },
  { label: '10x', value: 50 },
  { label: '50x', value: 100 },
]

export function TimelapseControls() {
  const { t } = useTranslation()
  const {
    currentYear,
    yearRange,
    isPlaying,
    playbackSpeed,
    setCurrentYear,
    play,
    pause,
    setPlaybackSpeed,
    jumpToEra,
  } = useTimelineStore()

  const animationRef = useRef<number>()
  const lastTimeRef = useRef<number>(0)

  // Animation loop
  const animate = useCallback(
    (timestamp: number) => {
      if (!lastTimeRef.current) {
        lastTimeRef.current = timestamp
      }

      const deltaTime = timestamp - lastTimeRef.current
      lastTimeRef.current = timestamp

      // Calculate year change based on playback speed
      const yearDelta = (playbackSpeed * deltaTime) / 1000

      setCurrentYear((prev: number) => {
        const newYear = prev + yearDelta
        // Stop at the end of the range
        if (newYear >= yearRange.max) {
          pause()
          return yearRange.max
        }
        return Math.round(newYear)
      })

      animationRef.current = requestAnimationFrame(animate)
    },
    [playbackSpeed, yearRange.max, setCurrentYear, pause]
  )

  // Start/stop animation based on isPlaying
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

  // Toggle play/pause
  const handlePlayPause = () => {
    if (isPlaying) {
      pause()
    } else {
      // If at the end, restart from beginning
      if (currentYear >= yearRange.max - 10) {
        setCurrentYear(yearRange.min)
      }
      play()
    }
  }

  // Reset to beginning
  const handleReset = () => {
    pause()
    setCurrentYear(yearRange.min)
  }

  // Skip to end
  const handleSkipToEnd = () => {
    pause()
    setCurrentYear(yearRange.max)
  }

  // Calculate progress percentage
  const progress = ((currentYear - yearRange.min) / (yearRange.max - yearRange.min)) * 100

  // Format year for display
  const formatYear = (year: number) => {
    if (year < 0) {
      return `${Math.abs(year)} BCE`
    }
    return `${year} CE`
  }

  // Find current era
  const getCurrentEra = () => {
    for (let i = ERAS.length - 1; i >= 0; i--) {
      if (currentYear >= ERAS[i].year) {
        return ERAS[i].name
      }
    }
    return 'Ancient'
  }

  return (
    <div className="timelapse-controls">
      {/* Main Controls */}
      <div className="timelapse-main">
        {/* Skip to Start */}
        <button
          className="timelapse-btn timelapse-skip"
          onClick={handleReset}
          title={t('timelapse.reset', 'Go to beginning')}
        >
          ⏮
        </button>

        {/* Play/Pause */}
        <button
          className={`timelapse-btn timelapse-play ${isPlaying ? 'playing' : ''}`}
          onClick={handlePlayPause}
          title={isPlaying ? t('timelapse.pause', 'Pause') : t('timelapse.play', 'Play')}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>

        {/* Skip to End */}
        <button
          className="timelapse-btn timelapse-skip"
          onClick={handleSkipToEnd}
          title={t('timelapse.end', 'Go to end')}
        >
          ⏭
        </button>
      </div>

      {/* Progress Bar */}
      <div className="timelapse-progress-container">
        <div className="timelapse-progress-bar">
          <div
            className="timelapse-progress-fill"
            style={{ width: `${progress}%` }}
          />
          {/* Era markers */}
          {ERAS.map((era) => {
            const eraProgress =
              ((era.year - yearRange.min) / (yearRange.max - yearRange.min)) * 100
            if (eraProgress < 0 || eraProgress > 100) return null
            return (
              <button
                key={era.name}
                className="timelapse-era-marker"
                style={{ left: `${eraProgress}%` }}
                onClick={() => jumpToEra(era.year)}
                title={`${era.name} (${era.label})`}
              />
            )
          })}
          {/* Current position indicator */}
          <div
            className="timelapse-position"
            style={{ left: `${progress}%` }}
          />
        </div>
        <div className="timelapse-year-display">
          <span className="current-year">{formatYear(currentYear)}</span>
          <span className="current-era">{getCurrentEra()}</span>
        </div>
      </div>

      {/* Speed Controls */}
      <div className="timelapse-speed">
        <span className="speed-label">{t('timelapse.speed', 'Speed')}:</span>
        <div className="speed-presets">
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
      </div>
    </div>
  )
}
