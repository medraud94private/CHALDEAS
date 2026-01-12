import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Timeline display modes
export type TimelineDisplayMode = 'compact' | 'standard' | 'expanded'

interface TimelineState {
  // Current year being observed
  currentYear: number

  // Year range
  yearRange: {
    min: number // -3000 (3000 BCE)
    max: number // 2024
  }

  // Playback
  isPlaying: boolean
  playbackSpeed: number // years per second

  // Display settings (persisted)
  displayMode: TimelineDisplayMode

  // Actions
  setCurrentYear: (year: number | ((prev: number) => number)) => void
  setYearRange: (min: number, max: number) => void
  play: () => void
  pause: () => void
  setPlaybackSpeed: (speed: number) => void
  jumpToEra: (year: number) => void
  setDisplayMode: (mode: TimelineDisplayMode) => void
}

export const useTimelineStore = create<TimelineState>()(
  persist(
    (set) => ({
      currentYear: -500, // Start at 500 BCE (Classical Greece)

      yearRange: {
        min: -3000,
        max: 2024,
      },

      isPlaying: false,
      playbackSpeed: 10,
      displayMode: 'standard' as TimelineDisplayMode,

      setCurrentYear: (year) => set((state) => ({
        currentYear: typeof year === 'function' ? year(state.currentYear) : year
      })),

      setYearRange: (min, max) => set({ yearRange: { min, max } }),

      play: () => set({ isPlaying: true }),

      pause: () => set({ isPlaying: false }),

      setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),

      jumpToEra: (year) => set({ currentYear: year, isPlaying: false }),

      setDisplayMode: (mode) => set({ displayMode: mode }),
    }),
    {
      name: 'chaldeas-timeline',
      partialize: (state) => ({
        displayMode: state.displayMode,
        playbackSpeed: state.playbackSpeed
      }),
    }
  )
)

// Era definitions for quick navigation
export const ERAS = [
  { name: 'Ancient Egypt', year: -2500, label: '2500 BCE' },
  { name: 'Classical Greece', year: -500, label: '500 BCE' },
  { name: 'Roman Empire', year: 100, label: '100 CE' },
  { name: 'Medieval', year: 1000, label: '1000 CE' },
  { name: 'Renaissance', year: 1500, label: '1500 CE' },
  { name: 'Modern', year: 1900, label: '1900 CE' },
] as const
