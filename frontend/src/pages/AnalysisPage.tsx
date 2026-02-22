import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { KnowledgeGraphPanel } from '../components/KnowledgeGraphPanel';
import { MovieScores } from '../components/MovieScores';
import { useToast } from '../contexts/ToastContext';
import type { JobStatus, MovieAnalysisResponse } from '../types/api';

const ANALYSIS_LOADING_ID = 'analysis-loading';

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png?text=Poster+Coming+Soon';

export function AnalysisPage() {
  const navigate = useNavigate();
  const { movieId } = useParams();
  const toast = useToast();
  const [analysis, setAnalysis] = useState<MovieAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [expandedBeats, setExpandedBeats] = useState<Set<number>>(new Set());
  const [refreshingPlot, setRefreshingPlot] = useState(false);
  const [showGraphPanel, setShowGraphPanel] = useState(false);

  const toggleCluster = useCallback((clusterId: string) => {
    setExpandedClusters((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) next.delete(clusterId);
      else next.add(clusterId);
      return next;
    });
  }, []);

  const toggleBeat = useCallback((beatOrder: number) => {
    setExpandedBeats((prev) => {
      const next = new Set(prev);
      if (next.has(beatOrder)) next.delete(beatOrder);
      else next.add(beatOrder);
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
    <div className="page-container">
      {loading ? (
        <div className="skeleton-analysis" aria-busy="true" aria-label="Loading analysis">
          <section className="analysis-hero panel">
            <div className="skeleton skeleton-hero-poster" />
            <div>
              <div className="skeleton skeleton-title" style={{ width: '70%', height: '1.8rem', marginBottom: '0.5rem' }} />
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <div className="skeleton skeleton-score" />
                <div className="skeleton skeleton-score" />
                <div className="skeleton skeleton-score" />
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.8rem', flexWrap: 'wrap' }}>
                {[1, 2, 3].map((i) => (
                  <div key={i} className="skeleton" style={{ width: 60, height: 24, borderRadius: 999 }} />
                ))}
              </div>
              <div style={{ marginTop: '0.8rem' }}>
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="skeleton skeleton-plot-line" />
                ))}
              </div>
            </div>
          </section>
          <section className="analysis-layout">
            <section className="panel">
              <div className="skeleton" style={{ width: 160, height: 24, marginBottom: '0.8rem' }} />
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="skeleton skeleton-cluster-item" />
              ))}
            </section>
            <section className="panel">
              <div className="skeleton" style={{ width: 100, height: 24, marginBottom: '0.8rem' }} />
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="skeleton-timeline-node">
                  <div className="skeleton skeleton-timeline-dot" />
                  <div className="skeleton skeleton-timeline-line" />
                </div>
              ))}
            </section>
          </section>
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !analysis ? (
        <section className="panel">
          <h2>Movie not ready yet</h2>
          <p>Run the backend pipeline first to fetch metadata, reviews, embeddings, clusters, and story context.</p>
          <div className="row-actions" style={{ marginTop: '0.8rem' }}>
            <button className="primary-btn" onClick={prepareMovie}>
              Prepare Movie
            </button>
            <button className="secondary-btn" onClick={() => navigate('/')}>
              Back to Home
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
              <div className="movie-meta">
                {analysis.movie.year && <span className="meta-tag">{analysis.movie.year}</span>}
                {analysis.movie.full_omdb?.Rated != null && <span className="meta-tag meta-tag--rated">{String(analysis.movie.full_omdb.Rated)}</span>}
                {analysis.movie.full_omdb?.Runtime != null && <span className="meta-tag">{String(analysis.movie.full_omdb.Runtime)}</span>}
              </div>
              <div className="genre-tags">
                {(analysis.movie.genre ?? 'Genre unavailable').split(',').map((g) => (
                  <span className="genre-pill" key={g.trim()}>{g.trim()}</span>
                ))}
              </div>
              <p>{analysis.expanded_plot ?? analysis.plot_summary ?? analysis.movie.plot ?? 'No plot available yet.'}</p>
              <MovieScores
                imdb_rating={analysis.movie.imdb_rating}
                rotten_tomatoes={analysis.movie.rotten_tomatoes}
                audience_score={analysis.movie.audience_score}
              />
              <div className="row-actions" style={{ marginTop: '0.75rem' }}>
                <button
                  className="secondary-btn"
                  onClick={() => setShowGraphPanel(true)}
                  type="button"
                >
                  View Knowledge Graph
                </button>
              </div>
            </div>
          </section>

          {showGraphPanel && movieId && analysis && (
            <KnowledgeGraphPanel
              movieId={movieId}
              movieTitle={analysis.movie.title}
              onClose={() => setShowGraphPanel(false)}
            />
          )}

          <section className="analysis-layout">
            <section>
              <h2>Complaint Clusters</h2>
              <div className="cluster-list">
                {analysis.clusters.length ? (
                  analysis.clusters.map((cluster, idx) => {
                    const isOpen = expandedClusters.has(cluster.cluster_id);
                    const tagline = cluster.tagline;
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
                <h2 style={{ margin: 0 }}>Plot Beats</h2>
                <button
                  className="secondary-btn"
                  disabled={refreshingPlot}
                  onClick={async () => {
                    if (!movieId) return;
                    setRefreshingPlot(true);
                    try {
                      await api.refreshPlotBeats(movieId);
                      toast.addToast({ message: 'Plot beats refreshed', type: 'success' });
                      const refreshed = await api.getMovieAnalysis(movieId);
                      setAnalysis(refreshed);
                    } catch (err) {
                      toast.addToast({
                        message: err instanceof Error ? err.message : 'Failed to refresh plot beats',
                        type: 'error',
                      });
                    } finally {
                      setRefreshingPlot(false);
                    }
                  }}
                  title="Re-scrape Wikipedia and regenerate plot beats"
                >
                  {refreshingPlot ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
              {analysis.plot_beats.length ? (
                <div className="timeline">
                  {analysis.plot_beats.map((beat, idx) => {
                    const isOpen = expandedBeats.has(beat.beat_order);
                    const isLast = idx === analysis.plot_beats.length - 1;
                    return (
                      <div className={`timeline-node${isLast ? ' timeline-node--last' : ''}`} key={`${beat.movie_id}-${beat.beat_order}`}>
                        <div className="timeline-marker">
                          <div className="timeline-dot" />
                          {!isLast && <div className="timeline-line" />}
                        </div>
                        <div className="timeline-content">
                          <button className="timeline-toggle" onClick={() => toggleBeat(beat.beat_order)} aria-expanded={isOpen}>
                            <span className="timeline-label">{beat.label}</span>
                            <svg
                              className={`timeline-chevron${isOpen ? ' timeline-chevron--open' : ''}`}
                              width="16" height="16" viewBox="0 0 24 24"
                              fill="none" stroke="currentColor" strokeWidth="2"
                              strokeLinecap="round" strokeLinejoin="round"
                            >
                              <polyline points="6 9 12 15 18 9" />
                            </svg>
                          </button>
                          {isOpen && <p className="timeline-text">{beat.beat_text}</p>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p>Plot beats are not generated yet.</p>
              )}
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
