/**
 * AgentResponseRenderer - Renders agent responses based on format type
 */
import type { AgentResponseData, AgentStructuredData } from '../../types'
import './chat.css'

interface Props {
  response: AgentResponseData
}

// Comparison Table Component
function ComparisonTable({ data }: { data: AgentStructuredData }) {
  if (!data.items || data.items.length === 0) return null

  return (
    <div className="comparison-table">
      <div className="comparison-header">
        {data.items.map((item, i) => (
          <div key={i} className="comparison-column-header">
            <h3>{item.title}</h3>
            {item.date && <span className="comparison-date">{item.date}</span>}
          </div>
        ))}
      </div>
      <div className="comparison-body">
        {data.items.map((item, i) => (
          <div key={i} className="comparison-column">
            <ul>
              {item.key_points.map((point, j) => (
                <li key={j}>{point}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {data.comparison_axes && data.comparison_axes.length > 0 && (
        <div className="comparison-axes">
          <span>Comparison: </span>
          {data.comparison_axes.map((axis, i) => (
            <span key={i} className="axis-tag">{axis}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// Timeline List Component
function TimelineList({ data }: { data: AgentStructuredData }) {
  if (!data.events || data.events.length === 0) return null

  return (
    <div className="timeline-list">
      {data.events.map((event, i) => (
        <div key={i} className="timeline-item">
          <div className="timeline-marker">
            <div className="timeline-dot" />
            {i < data.events!.length - 1 && <div className="timeline-line" />}
          </div>
          <div className="timeline-content">
            <div className="timeline-date">{event.date}</div>
            <h4 className="timeline-title">{event.title}</h4>
            <p className="timeline-desc">{event.description}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// Causal Flow Component
function CausalFlow({ data }: { data: AgentStructuredData }) {
  if (!data.chain || data.chain.length === 0) return null

  return (
    <div className="causal-flow">
      {data.chain.map((item, i) => (
        <div key={i} className="causal-item">
          <div className="causal-cause">
            <span className="causal-label">Cause</span>
            <p>{item.cause}</p>
          </div>
          <div className="causal-arrow">
            <span>→</span>
          </div>
          <div className="causal-effect">
            <span className="causal-label">Effect</span>
            <p>{item.effect}</p>
          </div>
          {item.explanation && (
            <div className="causal-explanation">
              <p>{item.explanation}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// Map Markers Component (shows list, actual map integration would be separate)
function MapMarkersList({ data }: { data: AgentStructuredData }) {
  if (!data.markers || data.markers.length === 0) return null

  return (
    <div className="map-markers-list">
      {data.markers.map((marker, i) => (
        <div key={i} className="map-marker-item">
          <div className="marker-icon">📍</div>
          <div className="marker-content">
            <h4>{marker.title}</h4>
            <p className="marker-coords">
              LAT: {marker.lat.toFixed(4)} / LNG: {marker.lng.toFixed(4)}
            </p>
            <p className="marker-desc">{marker.description}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// Cards Component
function CardsList({ data }: { data: AgentStructuredData }) {
  if (!data.cards || data.cards.length === 0) return null

  return (
    <div className="cards-grid">
      {data.cards.map((card, i) => (
        <div key={i} className="info-card">
          <div className="card-header">
            <h4>{card.title}</h4>
            {card.subtitle && <span className="card-subtitle">{card.subtitle}</span>}
          </div>
          <p className="card-content">{card.content}</p>
          {card.tags && card.tags.length > 0 && (
            <div className="card-tags">
              {card.tags.map((tag, j) => (
                <span key={j} className="card-tag">{tag}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// Main Renderer
export function AgentResponseRenderer({ response }: Props) {
  const { answer, structured_data, sources, confidence } = response

  // Render structured data based on format
  const renderStructuredContent = () => {
    if (!structured_data || !structured_data.type) return null

    switch (structured_data.type) {
      case 'comparison':
        return <ComparisonTable data={structured_data} />
      case 'timeline':
        return <TimelineList data={structured_data} />
      case 'causation':
        return <CausalFlow data={structured_data} />
      case 'map':
        return <MapMarkersList data={structured_data} />
      case 'cards':
        return <CardsList data={structured_data} />
      default:
        return null
    }
  }

  return (
    <div className="agent-response">
      {/* Main Answer */}
      <div className="response-answer">
        <p>{answer}</p>
      </div>

      {/* Structured Content */}
      {renderStructuredContent()}

      {/* Confidence Indicator */}
      <div className="response-meta">
        <div className="confidence-bar">
          <span>Confidence</span>
          <div className="bar-container">
            <div
              className="bar-fill"
              style={{ width: `${Math.min(confidence * 100, 100)}%` }}
            />
          </div>
          <span>{(confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Sources - 더 자세한 정보 */}
      {sources && sources.length > 0 && (
        <div className="response-sources">
          <span className="sources-label">Sources:</span>
          <div className="sources-list-detailed">
            {sources.slice(0, 5).map((src, i) => (
              <div key={i} className="source-item-detailed">
                <span className="source-title">{src.title}</span>
                {src.date_start && (
                  <span className="source-date">
                    {src.date_start < 0 ? `${Math.abs(src.date_start)} BCE` : `${src.date_start} CE`}
                  </span>
                )}
                {src.similarity && (
                  <span className="source-relevance">
                    {(src.similarity * 100).toFixed(0)}% match
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Follow-up Suggestions - ChatPanel에서 렌더링하므로 여기선 제거 */}
    </div>
  )
}
