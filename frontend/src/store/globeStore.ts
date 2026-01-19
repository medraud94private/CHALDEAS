import { create } from 'zustand'
import type { Event, Location, Category } from '../types'

// Camera mode types
export type CameraMode = 'orbit' | 'fly'

interface CameraPosition {
  lat: number
  lng: number
  altitude: number
}

// Fly mode state for WASD navigation
interface FlyState {
  heading: number  // degrees, 0 = north
  pitch: number    // degrees, 0 = level
  speed: number    // movement speed multiplier
}

interface HighlightedLocation {
  title: string
  lat: number
  lng: number
  year?: number
}

interface GlobeState {
  // Data
  events: Event[]
  locations: Location[]
  categories: Category[]

  // UI State
  selectedEvent: Event | null
  hoveredEvent: Event | null
  cameraPosition: CameraPosition
  autoRotate: boolean
  highlightedLocations: HighlightedLocation[]
  cameraMode: CameraMode
  flyState: FlyState

  // Filters
  selectedCategories: number[]
  minImportance: number

  // Actions
  setEvents: (events: Event[]) => void
  setLocations: (locations: Location[]) => void
  setCategories: (categories: Category[]) => void
  setSelectedEvent: (event: Event | null) => void
  setHoveredEvent: (event: Event | null) => void
  setCameraPosition: (position: Partial<CameraPosition>) => void
  setAutoRotate: (rotate: boolean) => void
  toggleCategory: (categoryId: number) => void
  setMinImportance: (importance: number) => void
  flyToLocation: (lat: number, lng: number) => void
  setHighlightedLocations: (locs: HighlightedLocation[]) => void
  clearHighlightedLocations: () => void
  setCameraMode: (mode: CameraMode) => void
  updateFlyState: (state: Partial<FlyState>) => void
}

export const useGlobeStore = create<GlobeState>((set, get) => ({
  // Initial state
  events: [],
  locations: [],
  categories: [],
  selectedEvent: null,
  hoveredEvent: null,
  cameraPosition: { lat: 30, lng: 20, altitude: 2.5 },
  autoRotate: true,
  highlightedLocations: [],
  cameraMode: 'orbit',
  flyState: { heading: 0, pitch: 0, speed: 1.0 },
  selectedCategories: [],
  minImportance: 1,

  // Actions
  setEvents: (events) => set({ events }),

  setLocations: (locations) => set({ locations }),

  setCategories: (categories) => set({ categories }),

  setSelectedEvent: (event) => {
    set({ selectedEvent: event, autoRotate: false })
    if (event?.location) {
      get().flyToLocation(event.location.latitude, event.location.longitude)
    }
  },

  setHoveredEvent: (event) => set({ hoveredEvent: event }),

  setCameraPosition: (position) =>
    set((state) => ({
      cameraPosition: { ...state.cameraPosition, ...position },
    })),

  setAutoRotate: (rotate) => set({ autoRotate: rotate }),

  toggleCategory: (categoryId) =>
    set((state) => {
      const categories = state.selectedCategories.includes(categoryId)
        ? state.selectedCategories.filter((id) => id !== categoryId)
        : [...state.selectedCategories, categoryId]
      return { selectedCategories: categories }
    }),

  setMinImportance: (importance) => set({ minImportance: importance }),

  flyToLocation: (lat, lng) =>
    set({
      cameraPosition: { lat, lng, altitude: 1.5 },
    }),

  setHighlightedLocations: (locs) => {
    set({ highlightedLocations: locs })
    // Auto fly to first highlighted location
    if (locs.length > 0) {
      set({
        cameraPosition: { lat: locs[0].lat, lng: locs[0].lng, altitude: 1.5 },
        autoRotate: false,
      })
    }
  },

  clearHighlightedLocations: () => set({ highlightedLocations: [] }),

  setCameraMode: (mode) => {
    set({ cameraMode: mode })
    // Disable auto-rotate in fly mode
    if (mode === 'fly') {
      set({ autoRotate: false })
    }
  },

  updateFlyState: (state) =>
    set((prev) => ({
      flyState: { ...prev.flyState, ...state },
    })),
}))
