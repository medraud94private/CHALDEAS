import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    if (import.meta.env.DEV) {
      console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error(
        `[API Error] ${error.response.status}: ${error.response.data?.detail || error.message}`
      )
    } else {
      console.error('[API Error] Network error:', error.message)
    }
    return Promise.reject(error)
  }
)

// API functions
export const eventsApi = {
  list: (params?: Record<string, unknown>) => api.get('/events', { params }),
  get: (id: number) => api.get(`/events/${id}`),
  getBySlug: (slug: string) => api.get(`/events/slug/${slug}`),
}

export const personsApi = {
  list: (params?: Record<string, unknown>) => api.get('/persons', { params }),
  get: (id: number) => api.get(`/persons/${id}`),
  getEvents: (id: number) => api.get(`/persons/${id}/events`),
}

export const locationsApi = {
  list: (params?: Record<string, unknown>) => api.get('/locations', { params }),
  get: (id: number) => api.get(`/locations/${id}`),
  getEvents: (id: number, params?: Record<string, unknown>) =>
    api.get(`/locations/${id}/events`, { params }),
}

export const searchApi = {
  search: (q: string, params?: Record<string, unknown>) =>
    api.get('/search', { params: { q, ...params } }),
  observeDateLocation: (params: {
    year: number
    latitude?: number
    longitude?: number
    radius_km?: number
  }) => api.get('/search/date-location', { params }),
}

export const chatApi = {
  query: (query: string, context?: Record<string, unknown>) =>
    api.post('/chat', { query, context }),
  observe: (query: string) => api.post('/chat/observe', { query }),
  // Agent-based intelligent query (api_key optional - falls back to BM25 if not provided)
  agent: (query: string, apiKey?: string, language: string = 'en') =>
    api.post('/chat/agent', { query, api_key: apiKey || undefined, language }),
}

// Showcase/Archive API
export const showcaseApi = {
  // FGO content
  getSingularities: () => api.get('/showcases/fgo/singularities'),
  getLostbelts: () => api.get('/showcases/fgo/lostbelts'),
  getServants: () => api.get('/showcases/fgo/servants'),
  // Pan-Human History
  getHistory: () => api.get('/showcases/history'),
  getLiterature: () => api.get('/showcases/literature'),
  getMusic: () => api.get('/showcases/music'),
  // Generic
  getAll: (params?: { type?: string; limit?: number }) =>
    api.get('/showcases', { params }),
  getById: (id: string) => api.get(`/showcases/${id}`),
  getStats: () => api.get('/showcases/stats/summary'),
}
