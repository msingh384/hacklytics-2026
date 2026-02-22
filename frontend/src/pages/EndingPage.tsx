import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
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

  const scoreItems = useMemo(() => {
    if (!score) return [];
    return [
      { label: 'Total', value: score.score_total },
      { label: 'Complaint Coverage', value: score.breakdown.complaint_coverage },
      { label: 'Preference Satisfaction', value: score.breakdown.preference_satisfaction },
      { label: 'Coherence', value: score.breakdown.coherence },
    ];
  }, [score]);

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

  return (
    <div className="page-container">
      <section className="ending-layout">
      <h1 className="section-title">Final Alternate Ending</h1>
      <p className="section-subtitle">{movieTitle ?? movieId}</p>

      <section className="panel">
        <p>{ending}</p>
      </section>

      {score ? (
        <>
          <section className="panel">
            <h2>Theme Coverage Score</h2>
            <div className="score-grid" style={{ marginTop: '0.6rem' }}>
              {scoreItems.map((item) => (
                <article className="score-card" key={item.label}>
                  <p>{item.label}</p>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Evidence Panel</h2>
            <div className="review-list" style={{ marginTop: '0.6rem' }}>
              {score.per_cluster.map((cluster) => (
                <article className="review-item" key={`${cluster.cluster_label}-${cluster.review_reference}`}>
                  <h3>{cluster.cluster_label}</h3>
                  <p>{cluster.addressed ? 'Addressed' : 'Not addressed yet'}</p>
                  <p>{cluster.evidence_excerpt}</p>
                  <small>Ref: {cluster.review_reference}</small>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}

      <div className="row-actions">
        {!isFromExplore ? (
          <button className="primary-btn" disabled={saving} onClick={saveEnding}>
            {saving ? 'Saving...' : savedId ? 'Saved' : 'Save Ending'}
          </button>
        ) : null}
        <button className="secondary-btn" onClick={() => alert('Coming soon')}>
          Share (Coming soon)
        </button>
        <button className="secondary-btn" onClick={() => navigate('/explore')}>
          Explore Leaderboard
        </button>
      </div>

      {savedId && !isFromExplore ? <p>Saved generation: {savedId}</p> : null}
      {error ? <p className="error">{error}</p> : null}
      </section>
    </div>
  );
}
