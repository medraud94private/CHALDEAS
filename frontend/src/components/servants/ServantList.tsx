import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

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

interface ServantStats {
  total_servants: number;
  mapped_to_history: number;
  fgo_original: number;
  servants_with_books: number;
  total_book_mentions: number;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100';

export default function ServantList() {
  const [servants, setServants] = useState<Servant[]>([]);
  const [stats, setStats] = useState<ServantStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [hasBooks, setHasBooks] = useState<boolean | null>(true);
  const [selectedOrigin, setSelectedOrigin] = useState<string>('');

  useEffect(() => {
    fetchStats();
    fetchServants();
  }, [hasBooks, selectedOrigin]);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/servants/stats`);
      if (res.ok) {
        const data = await res.json();
        setStats(data);
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
      if (selectedOrigin) params.set('origin', selectedOrigin);
      if (search) params.set('search', search);

      const res = await fetch(`${API_URL}/api/v1/servants/?${params}`);
      if (res.ok) {
        const data = await res.json();
        setServants(data);
      }
    } catch (error) {
      console.error('Failed to fetch servants:', error);
    } finally {
      setLoading(false);
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

  return (
    <div className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">FGO Servants & Historical Sources</h1>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-blue-400">{stats.total_servants}</div>
            <div className="text-sm text-slate-400">Total Servants</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-400">{stats.mapped_to_history}</div>
            <div className="text-sm text-slate-400">Historical</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-purple-400">{stats.fgo_original}</div>
            <div className="text-sm text-slate-400">FGO Original</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-yellow-400">{stats.servants_with_books}</div>
            <div className="text-sm text-slate-400">With Books</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-orange-400">{stats.total_book_mentions.toLocaleString()}</div>
            <div className="text-sm text-slate-400">Book Mentions</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search servants..."
            className="px-3 py-2 bg-slate-800 rounded-lg border border-slate-700 focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
          >
            Search
          </button>
        </form>

        <select
          value={hasBooks === null ? '' : hasBooks ? 'yes' : 'no'}
          onChange={(e) => {
            if (e.target.value === '') setHasBooks(null);
            else setHasBooks(e.target.value === 'yes');
          }}
          className="px-3 py-2 bg-slate-800 rounded-lg border border-slate-700"
        >
          <option value="">All Servants</option>
          <option value="yes">With Book Mentions</option>
          <option value="no">No Book Mentions</option>
        </select>

        <select
          value={selectedOrigin}
          onChange={(e) => setSelectedOrigin(e.target.value)}
          className="px-3 py-2 bg-slate-800 rounded-lg border border-slate-700"
        >
          <option value="">All Origins</option>
          <option value="Historical">Historical</option>
          <option value="Divine">Divine/Mythological</option>
          <option value="Royalty">Royalty</option>
          <option value="Mythological">Mythological</option>
        </select>
      </div>

      {/* Servant List */}
      {loading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="grid gap-3">
          {servants.map((servant) => (
            <Link
              key={servant.fgo_name}
              to={`/servants/${encodeURIComponent(servant.fgo_name)}`}
              className="block bg-slate-800 hover:bg-slate-700 rounded-lg p-4 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{servant.fgo_name}</span>
                    {servant.rarity && (
                      <span className="text-yellow-400 text-sm">{rarityStars(servant.rarity)}</span>
                    )}
                    {servant.is_fgo_original && (
                      <span className="text-xs bg-purple-600 px-2 py-0.5 rounded">FGO Original</span>
                    )}
                  </div>
                  {servant.person_name && (
                    <div className="text-sm text-slate-400">
                      Historical: {servant.person_name}
                    </div>
                  )}
                  {servant.fgo_class && (
                    <div className="text-xs text-slate-500">{servant.fgo_class} • {servant.origin}</div>
                  )}
                </div>
                <div className="text-right">
                  {servant.mention_count > 0 ? (
                    <div>
                      <div className="text-lg font-bold text-green-400">{servant.mention_count.toLocaleString()}</div>
                      <div className="text-xs text-slate-400">book mentions</div>
                    </div>
                  ) : (
                    <div className="text-slate-500 text-sm">No book data</div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
