import { useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useSessionId } from '../hooks/useSessionId';
import type { MovieDetails, ThemeCoverageScore } from '../types/api';

type EndingState = {
  ending: string;
  score: ThemeCoverageScore;
  storySessionId: string;
  history?: Array<{ step: number; narrative: string; choice?: string }>;
  movie?: MovieDetails;
  whatIf?: string;
};

export function EndingPage() {
  const { movieId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const sessionId = useSessionId();

  const state = location.state as EndingState | null;
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const scoreItems = useMemo(() => {
    if (!state) return [];
    return [
      { label: 'Total', value: state.score.score_total },
      { label: 'Complaint Coverage', value: state.score.breakdown.complaint_coverage },
      { label: 'Preference Satisfaction', value: state.score.breakdown.preference_satisfaction },
      { label: 'Coherence', value: state.score.breakdown.coherence },
    ];
  }, [state]);

  if (!movieId || !state) {
    return (
      <section className="panel">
        <h1>Ending data not found</h1>
        <p>Run a rewrite first so this page has the generated ending context.</p>
      </section>
    );
  }

  async function saveEnding() {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save ending');
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="ending-layout">
      <h1 className="section-title">Final Alternate Ending</h1>
      <p className="section-subtitle">{state.movie?.title ?? movieId}</p>

      <section className="panel">
        <p>{state.ending}</p>
      </section>

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
          {state.score.per_cluster.map((cluster) => (
            <article className="review-item" key={`${cluster.cluster_label}-${cluster.review_reference}`}>
              <h3>{cluster.cluster_label}</h3>
              <p>{cluster.addressed ? 'Addressed' : 'Not addressed yet'}</p>
              <p>{cluster.evidence_excerpt}</p>
              <small>Ref: {cluster.review_reference}</small>
            </article>
          ))}
        </div>
      </section>

      <div className="row-actions">
        <button className="primary-btn" disabled={saving} onClick={saveEnding}>
          {saving ? 'Saving...' : savedId ? 'Saved' : 'Save Ending'}
        </button>
        <button className="secondary-btn" onClick={() => alert('Coming soon')}>
          Share (Coming soon)
        </button>
        <button className="secondary-btn" onClick={() => navigate('/explore')}>
          Explore Leaderboard
        </button>
      </div>

      {savedId ? <p>Saved generation: {savedId}</p> : null}
      {error ? <p className="error">{error}</p> : null}
    </section>
  );
}
