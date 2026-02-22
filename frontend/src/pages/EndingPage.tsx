import { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { EndingScoreSection } from '../components/EndingScoreSection';
import { useSessionId } from '../hooks/useSessionId';
import type { GenerationDetail, MovieDetails, ThemeCoverageScore } from '../types/api';

type EndingState = {
  ending: string;
  score: ThemeCoverageScore;
  storySessionId: string;
  history?: Array<{ step: number; narrative: string; choice?: string }>;
  movie?: MovieDetails;
  whatIf?: string;
};

export function EndingPage() {
  const { movieId, generationId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const sessionId = useSessionId();

  const state = location.state as EndingState | null;
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(generationId ?? null);
  const [error, setError] = useState<string | null>(null);
  const [fetchedGeneration, setFetchedGeneration] = useState<GenerationDetail | null>(null);
  const [loadingGeneration, setLoadingGeneration] = useState(!!generationId);

  const isFromExplore = !!generationId;

  useEffect(() => {
    if (!generationId) return;
    let active = true;
    setLoadingGeneration(true);
    setError(null);
    api
      .getGeneration(generationId)
      .then((gen) => {
        if (active) setFetchedGeneration(gen);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load ending');
      })
      .finally(() => {
        if (active) setLoadingGeneration(false);
      });
    return () => {
      active = false;
    };
  }, [generationId]);

  const ending = isFromExplore ? fetchedGeneration?.ending_text : state?.ending;
  const score = isFromExplore ? fetchedGeneration?.score_payload : state?.score;
  const movieTitle = isFromExplore ? fetchedGeneration?.movie_title : state?.movie?.title;

  const storyPayload = isFromExplore ? (fetchedGeneration?.story_payload ?? {}) : { what_if: state?.whatIf, history: state?.history ?? [] };
  const whatIf = (typeof storyPayload.what_if === 'string' ? storyPayload.what_if : null) ?? state?.whatIf ?? null;
  const history = Array.isArray(storyPayload.history) ? storyPayload.history as Array<{ step: number; narrative: string; choice?: string }> : (state?.history ?? []);

  if (!movieId) {
    return (
      <div className="page-container">
        <section className="panel">
          <h1>Movie ID missing</h1>
        </section>
      </div>
    );
  }

  if (isFromExplore) {
    if (loadingGeneration) {
      return (
        <div className="page-container">
          <section className="panel">
            <p>Loading ending...</p>
          </section>
        </div>
      );
    }
    if (error || !fetchedGeneration) {
      return (
        <div className="page-container">
          <section className="panel">
            <h1>Ending not found</h1>
            <p>{error ?? 'This ending may have been removed.'}</p>
            <button className="secondary-btn" onClick={() => navigate('/explore')} style={{ marginTop: '0.8rem' }}>
              Back to Explore
            </button>
          </section>
        </div>
      );
    }
  } else if (!state) {
    return (
      <div className="page-container">
        <section className="panel">
          <h1>Ending data not found</h1>
          <p>Run a rewrite first so this page has the generated ending context.</p>
        </section>
      </div>
    );
  }

  async function saveEnding() {
    if (!state || !movieId) return;
    setSaving(true);
    setError(null);
    try {
      const generation = await api.saveGeneration(
        movieId,
        sessionId,
        state.storySessionId,
        state.ending,
        {
          what_if: state.whatIf,
          history: state.history ?? [],
        },
        state.score,
      );
      setSavedId(generation.generation_id);
      navigate(`/ending/${movieId}/${generation.generation_id}`, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save ending');
    } finally {
      setSaving(false);
    }
  }

  const hasStory = whatIf || history.length > 0 || ending;

  return (
    <div className="page-container">
      <article className="ending-page">
        {/* Hero */}
        <header className="ending-hero">
          <div className="ending-hero-text">
            <h1 className="ending-title">Alternate Ending</h1>
            <p className="ending-subtitle">{movieTitle ?? movieId}</p>
          </div>
          <div className="ending-hero-actions">
            {!isFromExplore && (
              <button className="primary-btn" disabled={saving} onClick={saveEnding}>
                {saving ? 'Saving…' : savedId ? 'Saved' : 'Save Ending'}
              </button>
            )}
            <button className="secondary-btn" onClick={() => navigate('/explore')}>
              Explore Leaderboard
            </button>
          </div>
        </header>

        {/* Single story block: what-if → steps → ending */}
        {hasStory && (
          <section className="ending-story">
            {whatIf && (
              <div className="ending-prompt">
                <span className="ending-prompt-label">What if</span>
                <p>{whatIf}</p>
              </div>
            )}

            <div className="ending-narrative-flow">
              {history.map((entry, idx) => (
                <div key={idx} className="ending-step">
                  <span className="ending-step-badge">Step {entry.step}</span>
                  <p className="ending-step-narrative">{entry.narrative}</p>
                  {entry.choice && (
                    <p className="ending-step-choice">&rarr; {entry.choice}</p>
                  )}
                </div>
              ))}
              {ending && (
                <div className="ending-final">
                  <h2 className="ending-final-heading">The Ending</h2>
                  <p className="ending-final-text">{ending}</p>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Single analytics section: score + clusters + evidence */}
        {score && (
          <EndingScoreSection score={score} />
        )}

        {/* Footer */}
        <footer className="ending-footer">
          {savedId && !isFromExplore && (
            <span className="ending-saved-id">Saved as {savedId.slice(0, 8)}…</span>
          )}
          {error && <span className="error">{error}</span>}
        </footer>
      </article>
    </div>
  );
}
