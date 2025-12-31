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
  id: number | string
  title: string
  title_ko?: string
  slug?: string
  description?: string
  description_ko?: string
  date_start: number // Negative for BCE
  date_end?: number
  date_display?: string // "490 BCE"
  date_precision?: 'exact' | 'year' | 'decade' | 'century'
  importance: number
  category?: Category | string
  // Direct coordinates (from API)
  latitude?: number
  longitude?: number
  // Or nested location object
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

// Agent Response Types
export type ResponseFormat =
  | 'narrative'
  | 'comparison_table'
  | 'timeline_list'
  | 'flow_chart'
  | 'map_markers'
  | 'cards'

export type QueryIntent =
  | 'comparison'
  | 'timeline'
  | 'causation'
  | 'deep_dive'
  | 'overview'
  | 'map_query'
  | 'person_info'
  | 'connection'

export interface AgentAnalysis {
  original_query: string
  english_query: string
  intent: QueryIntent
  intent_confidence: 'high' | 'medium' | 'low'
  entities: {
    events: string[]
    persons: string[]
    locations: string[]
    time_periods: Array<{ from?: number; to?: number; label?: string }>
    categories: string[]
    keywords: string[]
  }
  response_format: ResponseFormat
  search_strategy: string
  requires_multiple_searches: boolean
}

export interface AgentSearchResult {
  query_used: string
  filters_applied: Record<string, unknown>
  results: Array<{
    content_type: string
    content_id: number
    content_text: string
    metadata: Record<string, unknown>
    similarity: number
  }>
  result_count: number
}

export interface ComparisonItem {
  title: string
  date?: string
  key_points: string[]
}

export interface TimelineEvent {
  date: string
  title: string
  description: string
}

export interface CausalChain {
  cause: string
  effect: string
  explanation: string
}

export interface MapMarker {
  title: string
  lat: number
  lng: number
  description: string
}

export interface CardItem {
  title: string
  subtitle?: string
  content: string
  tags?: string[]
}

export interface AgentStructuredData {
  type: 'comparison' | 'timeline' | 'causation' | 'map' | 'cards'
  items?: ComparisonItem[]
  comparison_axes?: string[]
  events?: TimelineEvent[]
  chain?: CausalChain[]
  markers?: MapMarker[]
  cards?: CardItem[]
}

export interface AgentResponseData {
  intent: string
  format: ResponseFormat
  answer: string
  structured_data: AgentStructuredData
  sources: Array<{
    id: number
    title: string
    similarity: number
    date_start?: number
  }>
  confidence: number
  suggested_followups: string[]
  navigation?: {
    target_year?: number
    locations?: Array<{ lat: number; lng: number; title: string }>
  }
}

export interface AgentResponse {
  analysis: AgentAnalysis
  search_results: AgentSearchResult[]
  response: AgentResponseData
}
