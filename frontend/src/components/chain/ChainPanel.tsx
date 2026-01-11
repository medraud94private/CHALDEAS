/**
 * ChainPanel - Historical Chain Explorer (FGO Style)
 *
 * Shows connection statistics and allows exploration of historical chains.
 */
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api/client';
import './ChainPanel.css';

interface ChainStats {
  total_connections: number;
  by_layer: Record<string, number>;
  by_type: Record<string, number>;
  by_verification: Record<string, number>;
  avg_strength: number;
}

interface Connection {
  id: number;
  event_a: { id: number; title: string; date_start: number | null };
  event_b: { id: number; title: string; date_start: number | null };
  direction: string;
  layer_type: string;
  connection_type: string | null;
  strength_score: number;
}

type ViewMode = 'overview' | 'strongest' | 'recent';

export default function ChainPanel() {
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [animateIn, setAnimateIn] = useState(false);

  // Animate on mount
  useEffect(() => {
    const timer = setTimeout(() => setAnimateIn(true), 50);
    return () => clearTimeout(timer);
  }, []);

  // Fetch stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['chain-stats'],
    queryFn: () => api.get('/chains/stats'),
    select: (res) => res.data as ChainStats,
  });

  // Fetch strongest connections (top by strength)
  const { data: strongestData, isLoading: strongestLoading } = useQuery({
    queryKey: ['chain-strongest'],
    queryFn: () => api.get('/chains/', { params: { limit: 20, min_strength: 10 } }),
    select: (res) => res.data,
    enabled: viewMode === 'strongest',
  });

  // Fetch recent/sample connections
  const { data: recentData, isLoading: recentLoading } = useQuery({
    queryKey: ['chain-recent'],
    queryFn: () => api.get('/chains/', { params: { limit: 20 } }),
    select: (res) => res.data,
    enabled: viewMode === 'recent',
  });

  const formatYear = (year: number | null) => {
    if (year === null) return '?';
    if (year < 0) return `${Math.abs(year)} BCE`;
    return `${year} CE`;
  };

  const getTypeColor = (type: string | null): string => {
    const colors: Record<string, string> = {
      causes: '#ef4444',
      leads_to: '#f97316',
      follows: '#3b82f6',
      part_of: '#a855f7',
      concurrent: '#22c55e',
      related: '#6b7280',
    };
    return colors[type || ''] || '#6b7280';
  };

  const getLayerColor = (layer: string): string => {
    const colors: Record<string, string> = {
      person: '#fbbf24',
      location: '#34d399',
      causal: '#f472b6',
      thematic: '#a78bfa',
    };
    return colors[layer] || '#6b7280';
  };

  const getDirectionSymbol = (dir: string) => {
    switch (dir) {
      case 'forward': return '→';
      case 'backward': return '←';
      case 'bidirectional': return '↔';
      default: return '—';
    }
  };

  const connections = viewMode === 'strongest' ? strongestData?.items : recentData?.items;
  const isLoadingConnections = viewMode === 'strongest' ? strongestLoading : recentLoading;

  return (
    <div className={`chain-panel-content ${animateIn ? 'animate-in' : ''}`}>
      {/* Header */}
      <div className="chain-panel-header">
        <div className="chain-panel-title">
          <span className="chain-icon">⧉</span>
          <span>Historical Chain</span>
        </div>
        <div className="chain-panel-subtitle">Event Connection Graph</div>
      </div>

      {/* View Mode Tabs */}
      <div className="chain-view-tabs">
        {(['overview', 'strongest', 'recent'] as ViewMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`chain-view-tab ${viewMode === mode ? 'active' : ''}`}
          >
            {mode === 'overview' && '📊'}
            {mode === 'strongest' && '⚡'}
            {mode === 'recent' && '📋'}
            <span>{mode.charAt(0).toUpperCase() + mode.slice(1)}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="chain-panel-body">
        {/* Overview Tab */}
        {viewMode === 'overview' && (
          <div className="chain-overview">
            {statsLoading ? (
              <div className="chain-loading">Loading statistics...</div>
            ) : stats ? (
              <>
                {/* Total Stats */}
                <div className="chain-stat-hero">
                  <div className="stat-hero-value">{stats.total_connections.toLocaleString()}</div>
                  <div className="stat-hero-label">Total Connections</div>
                  <div className="stat-hero-sub">
                    Avg Strength: <span className="highlight">{stats.avg_strength.toFixed(1)}</span>
                  </div>
                </div>

                {/* Layer Breakdown */}
                <div className="chain-stat-section">
                  <div className="stat-section-title">By Layer</div>
                  <div className="chain-layer-bars">
                    {Object.entries(stats.by_layer)
                      .sort((a, b) => b[1] - a[1])
                      .map(([layer, count]) => {
                        const percentage = (count / stats.total_connections) * 100;
                        return (
                          <div key={layer} className="layer-bar-item">
                            <div className="layer-bar-header">
                              <span className="layer-name" style={{ color: getLayerColor(layer) }}>
                                {layer}
                              </span>
                              <span className="layer-count">{count.toLocaleString()}</span>
                            </div>
                            <div className="layer-bar-track">
                              <div
                                className="layer-bar-fill"
                                style={{
                                  width: `${percentage}%`,
                                  backgroundColor: getLayerColor(layer),
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>

                {/* Type Breakdown */}
                <div className="chain-stat-section">
                  <div className="stat-section-title">By Connection Type</div>
                  <div className="chain-type-grid">
                    {Object.entries(stats.by_type)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 6)
                      .map(([type, count]) => (
                        <div key={type} className="type-grid-item">
                          <div
                            className="type-indicator"
                            style={{ backgroundColor: getTypeColor(type) }}
                          />
                          <div className="type-info">
                            <span className="type-name">{type}</span>
                            <span className="type-count">{count.toLocaleString()}</span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Verification Status */}
                <div className="chain-stat-section">
                  <div className="stat-section-title">Verification Status</div>
                  <div className="verification-summary">
                    {Object.entries(stats.by_verification).map(([status, count]) => (
                      <div key={status} className="verification-item">
                        <span className={`verification-dot ${status}`} />
                        <span className="verification-label">{status.replace('_', ' ')}</span>
                        <span className="verification-count">{count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="chain-error">Failed to load statistics</div>
            )}
          </div>
        )}

        {/* Connections List (Strongest / Recent) */}
        {(viewMode === 'strongest' || viewMode === 'recent') && (
          <div className="chain-connections-list">
            {isLoadingConnections ? (
              <div className="chain-loading">Loading connections...</div>
            ) : connections && connections.length > 0 ? (
              <>
                <div className="connections-header">
                  {viewMode === 'strongest'
                    ? 'Strongest Connections (strength ≥ 10)'
                    : 'Sample Connections'}
                </div>
                {connections.map((conn: Connection, index: number) => (
                  <div
                    key={conn.id}
                    className="connection-card"
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className="connection-card-header">
                      <span
                        className="connection-type-badge"
                        style={{ backgroundColor: getTypeColor(conn.connection_type) }}
                      >
                        {conn.connection_type || 'unknown'}
                      </span>
                      <span
                        className="connection-layer-badge"
                        style={{ borderColor: getLayerColor(conn.layer_type) }}
                      >
                        {conn.layer_type}
                      </span>
                      <span className="connection-strength">
                        ⚡ {conn.strength_score.toFixed(1)}
                      </span>
                    </div>

                    <div className="connection-events">
                      <div className="connection-event event-a">
                        <div className="event-title">{conn.event_a?.title || '?'}</div>
                        <div className="event-year">{formatYear(conn.event_a?.date_start)}</div>
                      </div>

                      <div className="connection-arrow">
                        {getDirectionSymbol(conn.direction)}
                      </div>

                      <div className="connection-event event-b">
                        <div className="event-title">{conn.event_b?.title || '?'}</div>
                        <div className="event-year">{formatYear(conn.event_b?.date_start)}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </>
            ) : (
              <div className="chain-empty">No connections found</div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="chain-panel-footer">
        <span>Historical Chain System v1.0</span>
        <span className="footer-dot" />
        <span>CHALDEAS</span>
      </div>
    </div>
  );
}
