import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useToast } from '../contexts/ToastContext';
import type { JobStatus, MovieAnalysisResponse } from '../types/api';

const ANALYSIS_LOADING_ID = 'analysis-loading';

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png&text=Poster+Coming+Soon';

export function AnalysisPage() {
  const navigate = useNavigate();
  const { movieId } = useParams();
  const toast = useToast();
  const [analysis, setAnalysis] = useState<MovieAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const examplesByCluster = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const example of analysis?.cluster_examples ?? []) {
      const bucket = map.get(example.cluster_id) ?? [];
      bucket.push(example.review_text);
      map.set(example.cluster_id, bucket);
    }
    return map;
  }, [analysis]);

  useEffect(() => {
    if (!movieId) return;
    let active = true;
    setLoading(true);
    setError(null);

    api
      .getMovieAnalysis(movieId)
      .then((data) => {
        if (!active) return;
        setAnalysis(data);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load movie analysis');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [movieId]);

  useEffect(() => {
    if (!activeJobId) return;
    toast.addToast({
      id: ANALYSIS_LOADING_ID,
      message: 'Preparing analysis…',
      type: 'loading',
    });
    const timer = window.setInterval(async () => {
      try {
        const status = await api.getPipelineJob(activeJobId);
        setJob(status);
        toast.updateToast(ANALYSIS_LOADING_ID, {
          stage: status.stage,
          progress: status.progress,
        });
        if (status.status === 'ready') {
          window.clearInterval(timer);
          setActiveJobId(null);
          toast.removeToast(ANALYSIS_LOADING_ID);
          toast.addToast({ message: 'Analysis ready', type: 'success' });
          if (movieId) {
            const refreshed = await api.getMovieAnalysis(movieId);
            setAnalysis(refreshed);
          }
        }
        if (status.status === 'failed') {
          window.clearInterval(timer);
          setActiveJobId(null);
          toast.removeToast(ANALYSIS_LOADING_ID);
          setError(status.error ?? 'Pipeline failed');
        }
      } catch (err) {
        window.clearInterval(timer);
        setActiveJobId(null);
        toast.removeToast(ANALYSIS_LOADING_ID);
        setError(err instanceof Error ? err.message : 'Could not poll pipeline status');
      }
    }, 1800);

    return () => {
      window.clearInterval(timer);
      toast.removeToast(ANALYSIS_LOADING_ID);
    };
  }, [activeJobId, movieId, toast]);

  async function prepareMovie() {
    if (!movieId) return;
    setError(null);
    try {
      const result = await api.prepareMovie(movieId);
      if (result.status === 'ready') {
        toast.addToast({ message: 'Analysis ready', type: 'success' });
        const refreshed = await api.getMovieAnalysis(movieId);
        setAnalysis(refreshed);
        return;
      }
      if (result.status === 'queued' && result.job_id) {
        setActiveJobId(result.job_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not prepare movie');
    }
  }

  if (!movieId) return <p className="error">Movie ID missing.</p>;

  return (
    <div>
      {loading ? <p>Loading analysis...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !analysis ? (
        <section className="panel">
          <h2>Movie not ready yet</h2>
          <p>Run the backend pipeline first to fetch metadata, reviews, embeddings, clusters, and story context.</p>
          <div className="row-actions" style={{ marginTop: '0.8rem' }}>
            <button className="primary-btn" onClick={prepareMovie}>
              Prepare Movie
            </button>
            <button className="secondary-btn" onClick={() => navigate('/search')}>
              Go to Search
            </button>
          </div>
        </section>
      ) : null}

      {analysis ? (
        <>
          <section className="analysis-hero panel">
            <img src={analysis.movie.poster ?? PLACEHOLDER} alt={`${analysis.movie.title} poster`} />
            <div>
              <h1 className="section-title">{analysis.movie.title}</h1>
              <p className="section-subtitle">{analysis.movie.genre ?? 'Genre unavailable'}</p>
              <p>{analysis.expanded_plot ?? analysis.plot_summary ?? analysis.movie.plot ?? 'No plot available yet.'}</p>
              <div className="analysis-stats">
                <span className="stat-pill">IMDb {analysis.movie.imdb_rating ?? '--'}</span>
                <span className="stat-pill">RT {analysis.movie.rotten_tomatoes ?? '--'}</span>
                <span className="stat-pill">Audience {analysis.movie.audience_score ?? '--'}</span>
              </div>
            </div>
          </section>

          <section className="analysis-layout">
            <section>
              <h2>Complaint Clusters</h2>
              <div className="cluster-list">
                {analysis.clusters.length ? (
                  analysis.clusters.map((cluster) => (
                    <article className="cluster-item" key={cluster.cluster_id}>
                      <h3>{cluster.label}</h3>
                      <p>{cluster.summary}</p>
                      <small>{cluster.review_count} reviews represented</small>
                      {(examplesByCluster.get(cluster.cluster_id) ?? []).slice(0, 2).map((quote, index) => (
                        <p key={`${cluster.cluster_id}-${index}`}>"{quote}"</p>
                      ))}
                    </article>
                  ))
                ) : (
                  <p>No clusters generated yet.</p>
                )}
              </div>
            </section>

            <section>
              <h2>Plot Beats</h2>
              <div className="beat-list">
                {analysis.plot_beats.length ? (
                  analysis.plot_beats.map((beat) => (
                    <article className="beat-item" key={`${beat.movie_id}-${beat.beat_order}`}>
                      <h3>
                        {beat.beat_order}. {beat.label}
                      </h3>
                      <p>{beat.beat_text}</p>
                    </article>
                  ))
                ) : (
                  <p>Plot beats are not generated yet.</p>
                )}
              </div>
            </section>
          </section>

          <section className="panel" style={{ marginTop: '1rem' }}>
            <h2>What-if Suggestions</h2>
            <div className="whatif-list" style={{ marginTop: '0.6rem' }}>
              {analysis.what_if_suggestions.length ? (
                analysis.what_if_suggestions.map((item) => (
                  <article className="whatif-item" key={item.suggestion_id}>
                    <p>{item.text}</p>
                    <button
                      className="primary-btn"
                      onClick={() => navigate(`/rewrite/${movieId}?whatIf=${item.suggestion_id}`)}
                      style={{ marginTop: '0.5rem' }}
                    >
                      Start Rewrite
                    </button>
                  </article>
                ))
              ) : (
                <p>No what-if suggestions yet. Prepare the movie again once clusters are ready.</p>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
