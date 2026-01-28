import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';

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

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100';

export default function ServantDetailPage() {
  const { fgoName } = useParams<{ fgoName: string }>();
  const [servant, setServant] = useState<ServantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBook, setExpandedBook] = useState<number | null>(null);

  useEffect(() => {
    if (fgoName) {
      fetchServant(fgoName);
    }
  }, [fgoName]);

  const fetchServant = async (name: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/servants/${encodeURIComponent(name)}`);
      if (res.ok) {
        const data = await res.json();
        setServant(data);
      } else {
        setError('Servant not found');
      }
    } catch (err) {
      setError('Failed to load servant data');
    } finally {
      setLoading(false);
    }
  };

  const formatYear = (year?: number) => {
    if (!year) return null;
    if (year < 0) return `${Math.abs(year)} BCE`;
    return `${year} CE`;
  };

  const rarityStars = (rarity?: number) => {
    if (!rarity) return '';
    return '★'.repeat(rarity);
  };

  if (loading) {
    return <div className="text-center py-8">Loading...</div>;
  }

  if (error || !servant) {
    return (
      <div className="max-w-4xl mx-auto p-4">
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
          {error || 'Servant not found'}
        </div>
        <Link to="/servants" className="text-blue-400 hover:underline mt-4 inline-block">
          ← Back to Servant List
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-4">
      <Link to="/servants" className="text-blue-400 hover:underline mb-4 inline-block">
        ← Back to Servant List
      </Link>

      {/* Header */}
      <div className="bg-slate-800 rounded-lg p-6 mb-6">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold mb-2">{servant.fgo_name}</h1>
            {servant.rarity && (
              <div className="text-yellow-400 text-xl mb-2">{rarityStars(servant.rarity)}</div>
            )}
            {servant.fgo_class && (
              <div className="text-slate-400">
                {servant.fgo_class} • {servant.origin}
              </div>
            )}
          </div>
          {servant.is_fgo_original && (
            <span className="bg-purple-600 px-3 py-1 rounded-full text-sm">FGO Original</span>
          )}
        </div>
      </div>

      {/* Historical Connection */}
      {servant.person_name && (
        <div className="bg-slate-800 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Historical Connection</h2>
          <div className="space-y-2">
            <div>
              <span className="text-slate-400">Historical Figure:</span>{' '}
              <span className="font-medium">{servant.person_name}</span>
              {servant.person_name_ko && (
                <span className="text-slate-400 ml-2">({servant.person_name_ko})</span>
              )}
            </div>
            {(servant.birth_year || servant.death_year) && (
              <div>
                <span className="text-slate-400">Lived:</span>{' '}
                {formatYear(servant.birth_year)} - {formatYear(servant.death_year)}
              </div>
            )}
            {servant.wikidata_id && (
              <div>
                <a
                  href={`https://www.wikidata.org/wiki/${servant.wikidata_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:underline"
                >
                  View on Wikidata →
                </a>
              </div>
            )}
            {servant.biography && (
              <div className="mt-4">
                <span className="text-slate-400">Description:</span>
                <p className="mt-1">{servant.biography}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Book Mentions */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">
          Book Mentions
          {servant.mention_count > 0 && (
            <span className="ml-2 text-green-400">({servant.mention_count.toLocaleString()} total)</span>
          )}
        </h2>

        {servant.book_mentions.length > 0 ? (
          <div className="space-y-4">
            {servant.book_mentions.map((book) => (
              <div
                key={book.source_id}
                className="border border-slate-700 rounded-lg overflow-hidden"
              >
                <button
                  onClick={() => setExpandedBook(expandedBook === book.source_id ? null : book.source_id)}
                  className="w-full p-4 text-left hover:bg-slate-700/50 transition-colors"
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium">{book.source_title}</div>
                      {book.source_author && (
                        <div className="text-sm text-slate-400">by {book.source_author}</div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-green-400 font-bold">{book.mention_count}</div>
                      <div className="text-xs text-slate-400">mentions</div>
                    </div>
                  </div>
                </button>

                {expandedBook === book.source_id && book.sample_contexts.length > 0 && (
                  <div className="border-t border-slate-700 p-4 bg-slate-900/50">
                    <div className="text-sm text-slate-400 mb-2">Sample contexts:</div>
                    {book.sample_contexts.map((context, i) => (
                      <div
                        key={i}
                        className="p-3 bg-slate-800 rounded mb-2 text-sm italic"
                      >
                        "...{context}..."
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-slate-400 py-4 text-center">
            {servant.is_fgo_original
              ? 'This is an FGO original character with no historical counterpart.'
              : 'No book mentions found for this servant yet.'}
          </div>
        )}
      </div>
    </div>
  );
}
