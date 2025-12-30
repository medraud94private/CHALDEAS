import { useCallback, useMemo } from 'react'
import { useTimelineStore, ERAS } from '../../store/timelineStore'

export function TimelineSlider() {
  const { currentYear, yearRange, setCurrentYear, isPlaying, play, pause } =
    useTimelineStore()

  // Convert year to slider value (0-100)
  const yearToSlider = useCallback(
    (year: number) => {
      const range = yearRange.max - yearRange.min
      return ((year - yearRange.min) / range) * 100
    },
    [yearRange]
  )

  // Convert slider value to year
  const sliderToYear = useCallback(
    (value: number) => {
      const range = yearRange.max - yearRange.min
      return Math.round(yearRange.min + (value / 100) * range)
    },
    [yearRange]
  )

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value)
    setCurrentYear(sliderToYear(value))
  }

  const formatYear = (year: number) => {
    const absYear = Math.abs(year)
    const era = year < 0 ? 'BCE' : 'CE'
    return `${absYear} ${era}`
  }

  // Era markers for the slider
  const eraMarkers = useMemo(
    () =>
      ERAS.map((era) => ({
        ...era,
        position: yearToSlider(era.year),
      })),
    [yearToSlider]
  )

  return (
    <div className="timeline-slider">
      {/* Era quick jump buttons */}
      <div className="flex justify-center gap-2 mb-3">
        {ERAS.map((era) => (
          <button
            key={era.name}
            onClick={() => setCurrentYear(era.year)}
            className={`px-3 py-1 text-xs rounded-full transition-all ${
              Math.abs(currentYear - era.year) < 200
                ? 'bg-chaldea-gold text-white'
                : 'bg-white/10 text-gray-300 hover:bg-white/20'
            }`}
          >
            {era.name}
          </button>
        ))}
      </div>

      {/* Slider track with era markers */}
      <div className="relative h-12 mx-4">
        {/* Era markers */}
        {eraMarkers.map((era) => (
          <div
            key={era.name}
            className="absolute top-0 h-2 w-px bg-white/30"
            style={{ left: `${era.position}%` }}
          >
            <span className="absolute top-3 left-1/2 -translate-x-1/2 text-[10px] text-gray-400 whitespace-nowrap">
              {era.label}
            </span>
          </div>
        ))}

        {/* Main slider */}
        <input
          type="range"
          min={0}
          max={100}
          step={0.1}
          value={yearToSlider(currentYear)}
          onChange={handleSliderChange}
          className="absolute bottom-0 w-full h-2 appearance-none bg-white/20 rounded-full cursor-pointer
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-chaldea-gold
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:shadow-lg
            [&::-webkit-slider-thumb]:shadow-chaldea-gold/50"
        />
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 mt-4">
        <button
          onClick={() => setCurrentYear(currentYear - 100)}
          className="px-3 py-1 text-sm bg-white/10 rounded hover:bg-white/20"
        >
          -100
        </button>
        <button
          onClick={() => setCurrentYear(currentYear - 10)}
          className="px-3 py-1 text-sm bg-white/10 rounded hover:bg-white/20"
        >
          -10
        </button>

        <button
          onClick={() => (isPlaying ? pause() : play())}
          className="w-10 h-10 flex items-center justify-center bg-chaldea-gold rounded-full"
        >
          {isPlaying ? '⏸' : '▶'}
        </button>

        <button
          onClick={() => setCurrentYear(currentYear + 10)}
          className="px-3 py-1 text-sm bg-white/10 rounded hover:bg-white/20"
        >
          +10
        </button>
        <button
          onClick={() => setCurrentYear(currentYear + 100)}
          className="px-3 py-1 text-sm bg-white/10 rounded hover:bg-white/20"
        >
          +100
        </button>
      </div>
    </div>
  )
}
