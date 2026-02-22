import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { LoadingProgress } from '../components/LoadingProgress';
import type { JobStatus, MovieAnalysisResponse } from '../types/api';

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png&text=Poster+Coming+Soon';

export function AnalysisPage() {
  const navigate = useNavigate();
  const { movieId } = useParams();
  const [analysis, setAnalysis] = useState<MovieAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [taglines, setTaglines] = useState<string[]>([]);

  const toggleCluster = useCallback((clusterId: string) => {
    setExpandedClusters((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) next.delete(clusterId);
      else next.add(clusterId);
      return next;
    });
  }, []);

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
    if (!analysis || !analysis.clusters.length) return;
    let active = true;
    api
      .clusterTaglines(analysis.clusters.map((c) => ({ summary: c.summary })))
      .then((res) => {
        if (active) setTaglines(res.taglines);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [analysis]);

  useEffect(() => {
    if (!activeJobId) return;
    const timer = window.setInterval(async () => {
      try {
        const status = await api.getPipelineJob(activeJobId);
        setJob(status);
        if (status.status === 'ready') {
          window.clearInterval(timer);
          setActiveJobId(null);
          if (movieId) {
            const refreshed = await api.getMovieAnalysis(movieId);
            setAnalysis(refreshed);
          }
        }
        if (status.status === 'failed') {
          window.clearInterval(timer);
          setError(status.error ?? 'Pipeline failed');
        }
      } catch (err) {
        window.clearInterval(timer);
        setError(err instanceof Error ? err.message : 'Could not poll pipeline status');
      }
    }, 1800);

    return () => window.clearInterval(timer);
  }, [activeJobId, movieId]);

  async function prepareMovie() {
    if (!movieId) return;
    setError(null);
    try {
      const result = await api.prepareMovie(movieId);
      if (result.status === 'ready') {
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
      {job ? <LoadingProgress job={job} /> : null}
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
                  analysis.clusters.map((cluster, idx) => {
                    const isOpen = expandedClusters.has(cluster.cluster_id);
                    const tagline = taglines[idx];
                    return (
                      <article className="cluster-item cluster-collapsible" key={cluster.cluster_id}>
                        <button
                          className="cluster-toggle"
                          onClick={() => toggleCluster(cluster.cluster_id)}
                          aria-expanded={isOpen}
                        >
                          <div className="cluster-header">
                            <h3 className="cluster-theme">
                              Theme {idx + 1}{tagline ? `: ${tagline}` : ''}
                            </h3>
                          </div>
                          <svg
                            className={`cluster-chevron${isOpen ? ' cluster-chevron--open' : ''}`}
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="6 9 12 15 18 9" />
                          </svg>
                        </button>
                        {isOpen && (
                          <div className="cluster-details">
                            <p>{cluster.summary}</p>
                            <small>{cluster.review_count} reviews represented</small>
                            {(examplesByCluster.get(cluster.cluster_id) ?? []).slice(0, 2).map((quote, index) => (
                              <p className="cluster-quote" key={`${cluster.cluster_id}-${index}`}>"{quote}"</p>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })
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
