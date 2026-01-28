import { useState, useEffect } from 'react';
import './ServantPanel.css';

interface Servant {
  fgo_name: string;
  fgo_class?: string;
  rarity?: number;
  origin?: string;
  person_id?: number;
  person_name?: string;
  wikidata_id?: string;
  mention_count: number;
  is_fgo_original: boolean;
}

interface BookMention {
  source_id: number;
  source_title: string;
  source_author?: string;
  mention_count: number;
  sample_contexts: string[];
}

interface ServantDetail {
  fgo_name: string;
  fgo_class?: string;
  rarity?: number;
  origin?: string;
  person_id?: number;
  person_name?: string;
  person_name_ko?: string;
  wikidata_id?: string;
  biography?: string;
  birth_year?: number;
  death_year?: number;
  is_fgo_original: boolean;
  mention_count: number;
  book_mentions: BookMention[];
}

interface ServantStats {
  total_servants: number;
  mapped_to_history: number;
  fgo_original: number;
  servants_with_books: number;
  total_book_mentions: number;
}

interface ServantPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onPersonClick?: (personId: number) => void;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100';

export function ServantPanel({ isOpen, onClose, onPersonClick }: ServantPanelProps) {
  const [servants, setServants] = useState<Servant[]>([]);
  const [stats, setStats] = useState<ServantStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [hasBooks, setHasBooks] = useState<boolean | null>(true);
  const [selectedServant, setSelectedServant] = useState<ServantDetail | null>(null);
  const [expandedBook, setExpandedBook] = useState<number | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchStats();
      fetchServants();
    } else {
      // 모달 닫힐 때 상태 초기화
      setSelectedServant(null);
      setExpandedBook(null);
    }
  }, [isOpen, hasBooks]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/servants/stats`);
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const fetchServants = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('limit', '100');
      if (hasBooks !== null) params.set('has_books', String(hasBooks));
      if (search) params.set('search', search);

      const res = await fetch(`${API_URL}/api/v1/servants/?${params}`);
      if (res.ok) {
        setServants(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch servants:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchServantDetail = async (fgoName: string) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/servants/${encodeURIComponent(fgoName)}`);
      if (res.ok) {
        setSelectedServant(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch servant detail:', error);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchServants();
  };

  const rarityStars = (rarity?: number) => {
    if (!rarity) return '';
    return '★'.repeat(rarity);
  };

  const formatYear = (year?: number) => {
    if (!year) return null;
    if (year < 0) return `${Math.abs(year)} BCE`;
    return `${year} CE`;
  };

  if (!isOpen) return null;

  return (
    <div className="servant-panel-overlay" onClick={onClose}>
      <div className="servant-panel" onClick={(e) => e.stopPropagation()}>
        <div className="servant-panel-header">
          <h2>FGO Servants & Historical Sources</h2>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {selectedServant ? (
          /* Detail View */
          <div className="servant-detail">
            <button
              className="back-btn"
              onClick={() => setSelectedServant(null)}
            >
              ← Back to List
            </button>

            <div className="servant-detail-header">
              <h3>{selectedServant.fgo_name}</h3>
              {selectedServant.rarity && (
                <span className="rarity">{rarityStars(selectedServant.rarity)}</span>
              )}
              {selectedServant.is_fgo_original && (
                <span className="fgo-original-badge">FGO Original</span>
              )}
            </div>

            {selectedServant.fgo_class && (
              <div className="servant-meta">
                {selectedServant.fgo_class} • {selectedServant.origin}
              </div>
            )}

            {selectedServant.person_name && (
              <div className="historical-section">
                <h4>Historical Connection</h4>
                <div className="historical-info">
                  <div className="person-name">
                    {selectedServant.person_name}
                    {selectedServant.person_name_ko && (
                      <span className="name-ko"> ({selectedServant.person_name_ko})</span>
                    )}
                  </div>
                  {(selectedServant.birth_year || selectedServant.death_year) && (
                    <div className="lifespan">
                      {formatYear(selectedServant.birth_year)} - {formatYear(selectedServant.death_year)}
                    </div>
                  )}
                  {selectedServant.biography && (
                    <p className="biography">{selectedServant.biography}</p>
                  )}
                  <div className="links">
                    {selectedServant.wikidata_id && (
                      <a
                        href={`https://www.wikidata.org/wiki/${selectedServant.wikidata_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        Wikidata →
                      </a>
                    )}
                    {selectedServant.person_id && onPersonClick && (
                      <button
                        className="view-person-btn"
                        onClick={() => {
                          onPersonClick(selectedServant.person_id!);
                          onClose();
                        }}
                      >
                        View in CHALDEAS →
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="book-mentions-section">
              <h4>
                Book Mentions
                {selectedServant.mention_count > 0 && (
                  <span className="count"> ({selectedServant.mention_count.toLocaleString()})</span>
                )}
              </h4>
              {selectedServant.book_mentions.length > 0 ? (
                <div className="book-list">
                  {selectedServant.book_mentions.map((book) => (
                    <div key={book.source_id} className="book-item">
                      <div
                        className="book-header"
                        onClick={() => setExpandedBook(
                          expandedBook === book.source_id ? null : book.source_id
                        )}
                      >
                        <div className="book-info">
                          <div className="book-title">{book.source_title}</div>
                          {book.source_author && (
                            <div className="book-author">by {book.source_author}</div>
                          )}
                        </div>
                        <div className="mention-count">{book.mention_count}</div>
                      </div>
                      {expandedBook === book.source_id && book.sample_contexts.length > 0 && (
                        <div className="book-contexts">
                          {book.sample_contexts.map((ctx, i) => (
                            <div key={i} className="context-quote">
                              "...{ctx}..."
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-books">
                  {selectedServant.is_fgo_original
                    ? 'This is an FGO original character.'
                    : 'No book mentions found yet.'}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* List View */
          <>
            {/* Stats */}
            {stats && (
              <div className="servant-stats">
                <div className="stat">
                  <span className="value">{stats.total_servants}</span>
                  <span className="label">Total</span>
                </div>
                <div className="stat">
                  <span className="value">{stats.servants_with_books}</span>
                  <span className="label">With Books</span>
                </div>
                <div className="stat">
                  <span className="value">{stats.total_book_mentions.toLocaleString()}</span>
                  <span className="label">Mentions</span>
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="servant-filters">
              <form onSubmit={handleSearch} className="search-form">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search servants..."
                />
                <button type="submit">Search</button>
              </form>
              <select
                value={hasBooks === null ? '' : hasBooks ? 'yes' : 'no'}
                onChange={(e) => {
                  if (e.target.value === '') setHasBooks(null);
                  else setHasBooks(e.target.value === 'yes');
                }}
              >
                <option value="">All</option>
                <option value="yes">With Books</option>
                <option value="no">No Books</option>
              </select>
            </div>

            {/* List */}
            <div className="servant-list">
              {loading ? (
                <div className="loading">Loading...</div>
              ) : (
                servants.map((servant) => (
                  <div
                    key={servant.fgo_name}
                    className="servant-item"
                    onClick={() => fetchServantDetail(servant.fgo_name)}
                  >
                    <div className="servant-info">
                      <div className="servant-name">
                        {servant.fgo_name}
                        {servant.rarity && (
                          <span className="rarity-small">{rarityStars(servant.rarity)}</span>
                        )}
                        {servant.is_fgo_original && (
                          <span className="fgo-badge">FGO</span>
                        )}
                      </div>
                      {servant.person_name && (
                        <div className="historical-name">{servant.person_name}</div>
                      )}
                    </div>
                    {servant.mention_count > 0 && (
                      <div className="mention-badge">
                        {servant.mention_count.toLocaleString()}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default ServantPanel;
