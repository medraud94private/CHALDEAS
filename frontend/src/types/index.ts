// Core types for CHALDEAS frontend

export interface Category {
  id: number
  name: string
  name_ko?: string
  slug: string
  color: string
  icon?: string
  children?: Category[]
}

export interface Location {
  id: number
  name: string
  name_ko?: string
  name_original?: string
  latitude: number
  longitude: number
  type: 'city' | 'region' | 'landmark' | 'battle_site'
  modern_name?: string
  country?: string
  region?: string
  description?: string
  description_ko?: string
}

export interface Event {
  id: number
  title: string
  title_ko?: string
  slug: string
  description?: string
  description_ko?: string
  date_start: number // Negative for BCE
  date_end?: number
  date_display: string // "490 BCE"
  date_precision: 'exact' | 'year' | 'decade' | 'century'
  importance: 1 | 2 | 3 | 4 | 5
  category?: Category
  location?: Location // Primary location
  locations?: LocationRole[]
  persons?: PersonRole[]
  sources?: SourceReference[]
  image_url?: string
  wikipedia_url?: string
}

export interface LocationRole extends Location {
  role: 'location' | 'origin' | 'destination'
}

export interface Person {
  id: number
  name: string
  name_ko?: string
  name_original?: string
  slug: string
  birth_year?: number
  death_year?: number
  lifespan_display: string
  biography?: string
  biography_ko?: string
  category?: Category
  birthplace?: Location
  deathplace?: Location
  image_url?: string
  wikipedia_url?: string
}

export interface PersonRole extends Person {
  role: string
}

export interface Source {
  id: number
  name: string
  type: 'primary' | 'secondary' | 'digital_archive'
  url?: string
  author?: string
  publication_year?: number
  description?: string
  reliability: 1 | 2 | 3 | 4 | 5
  archive_type?: 'perseus' | 'ctext' | 'gutenberg' | 'latin_library' | 'augustana'
}

export interface SourceReference extends Source {
  page_reference?: string
  quote?: string
}

// API Response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
}

export interface SearchResults {
  query: string
  results: {
    events: Event[]
    persons: Person[]
    locations: Location[]
  }
}

export interface ChatResponse {
  answer: string
  sources: Array<{
    source: Source
    relevance: number
    excerpt?: string
  }>
  confidence: number
  related_events: Event[]
  suggested_queries: string[]
}
