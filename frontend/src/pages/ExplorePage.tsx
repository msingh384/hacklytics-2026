import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useSessionId } from '../hooks/useSessionId';
import type { LeaderboardItem } from '../types/api';

export function ExplorePage() {
  const navigate = useNavigate();
  const sessionId = useSessionId();
  const [items, setItems] = useState<LeaderboardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.leaderboard();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load leaderboard');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function vote(generationId: string, value: number) {
    try {
      const result = await api.voteGeneration(generationId, sessionId, value);
      setItems((prev) =>
        prev
          .map((item) => (item.generation_id === generationId ? { ...item, votes: result.votes } : item))
          .sort((a, b) => b.votes - a.votes),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Vote failed');
    }
  }

  return (
    <div className="page-container">
      <h1 className="section-title">Explore Leaderboard</h1>
      <p className="section-subtitle">Top community endings sorted by votes.</p>

      {loading ? <p>Loading leaderboard...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !items.length ? (
        <div className="empty-state">
          <p>No endings saved yet. Create one from the Rewrite flow.</p>
        </div>
      ) : null}

      <section className="leaderboard-list">
        {items.map((item) => (
          <article
            className="leaderboard-item leaderboard-item--clickable"
            key={item.generation_id}
            onClick={() => navigate(`/ending/${item.movie_id}/${item.generation_id}`)}
          >
            <h2>{item.movie_title}</h2>
            <p>{item.ending_text}</p>
            <p>Votes: {item.votes} | Score: {item.score_total}</p>
            <div className="row-actions" onClick={(e) => e.stopPropagation()}>
              <button className="primary-btn" onClick={() => vote(item.generation_id, 1)}>
                Upvote
              </button>
              <button className="secondary-btn" onClick={() => vote(item.generation_id, -1)}>
                Downvote
              </button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
