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
  const [votingId, setVotingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.leaderboard(sessionId);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load leaderboard');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [sessionId]);

  async function vote(generationId: string, value: number) {
    if (votingId) return;
    const item = items.find((i) => i.generation_id === generationId);
    const nextValue = item?.user_vote === value ? 0 : value;
    setVotingId(generationId);
    try {
      const result = await api.voteGeneration(generationId, sessionId, nextValue);
      setItems((prev) =>
        prev
          .map((i) =>
            i.generation_id === generationId
              ? { ...i, votes: result.votes, user_vote: nextValue === 0 ? undefined : nextValue }
              : i,
          )
          .sort((a, b) => b.votes - a.votes),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Vote failed');
    } finally {
      setVotingId(null);
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
            <div
              className="vote-widget"
              onClick={(e) => e.stopPropagation()}
              role="group"
              aria-label="Vote"
            >
              <button
                type="button"
                className={`vote-btn vote-btn--up${item.user_vote === 1 ? ' vote-btn--active' : ''}`}
                onClick={() => vote(item.generation_id, 1)}
                disabled={votingId === item.generation_id}
                aria-label="Upvote"
                aria-pressed={item.user_vote === 1}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="18 15 12 9 6 15" />
                </svg>
              </button>
              <span className="vote-count">{item.votes}</span>
              <button
                type="button"
                className={`vote-btn vote-btn--down${item.user_vote === -1 ? ' vote-btn--active' : ''}`}
                onClick={() => vote(item.generation_id, -1)}
                disabled={votingId === item.generation_id}
                aria-label="Downvote"
                aria-pressed={item.user_vote === -1}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
            </div>
            <div className="leaderboard-content">
              <h2>{item.movie_title}</h2>
              <p>{item.ending_text}</p>
              <p className="leaderboard-meta">Score: {item.score_total}</p>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
