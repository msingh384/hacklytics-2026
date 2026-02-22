import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { CharacterArcChart } from '../components/CharacterArcChart';
import { KnowledgeGraphPanel } from '../components/KnowledgeGraphPanel';
import { MovieScores } from '../components/MovieScores';
import { PlotBeatGraphPanel } from '../components/PlotBeatGraphPanel';
import { useToast } from '../contexts/ToastContext';
import type { JobStatus, MovieAnalysisResponse } from '../types/api';

const ANALYSIS_LOADING_ID = 'analysis-loading';

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png?text=Poster+Coming+Soon';

export function AnalysisPage() {
  const navigate = useNavigate();
  const { movieId } = useParams();
  const { addToast, removeToast, updateToast } = useToast();
  const [analysis, setAnalysis] = useState<MovieAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(new Set());
  const [expandedBeats, setExpandedBeats] = useState<Set<number>>(new Set());
  const [expandedCharacters, setExpandedCharacters] = useState<Set<string>>(new Set());
  const [plotExpanded, setPlotExpanded] = useState(false);
  const [refreshingPlot, setRefreshingPlot] = useState(false);
  const [rerunningPipeline, setRerunningPipeline] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [customWhatIfInput, setCustomWhatIfInput] = useState('');
  const [showGraphPanel, setShowGraphPanel] = useState(false);
  const [showPlotBeatGraphPanel, setShowPlotBeatGraphPanel] = useState(false);
  const [beatDensity, setBeatDensity] = useState<Record<string, number> | null>(null);

  const PLOT_PREVIEW_LENGTH = 350;

  const toggleCharacter = useCallback((characterId: string) => {
    setExpandedCharacters((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });
  }, []);

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
    if (!showCreateModal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowCreateModal(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showCreateModal]);

  useEffect(() => {
    if (!movieId) return;
    let active = true;
    setLoading(true);
    setError(null);
    setPlotExpanded(false);
    setShowCreateModal(false);
    setCustomWhatIfInput('');
    setShowGraphPanel(false);

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
    if (!movieId || !analysis?.plot_beats?.length) return;
    let cancelled = false;
    setBeatDensity(null);
    api
      .getBeatComplaintDensity(movieId)
      .then((d) => {
        if (!cancelled) setBeatDensity(d);
      })
      .catch(() => {
        if (!cancelled) setBeatDensity({});
      });
    return () => {
      cancelled = true;
    };
  }, [movieId, analysis]);

  useEffect(() => {
    if (!activeJobId || !movieId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    addToast({
      id: ANALYSIS_LOADING_ID,
      message: 'Preparing analysis…',
      type: 'loading',
    });

    async function poll(): Promise<boolean> {
      if (cancelled) return true;
      try {
        const status = await api.getPipelineJob(activeJobId!);
        if (cancelled) return true;
        setJob(status);
        updateToast(ANALYSIS_LOADING_ID, {
          stage: status.stage,
          progress: status.progress,
        });
        if (status.status === 'ready' && movieId) {
          removeToast(ANALYSIS_LOADING_ID);
          addToast({ message: 'Analysis ready', type: 'success' });
          const refreshed = await api.getMovieAnalysis(movieId);
          if (!cancelled) setAnalysis(refreshed);
          setActiveJobId(null);
          return true;
        }
        if (status.status === 'failed') {
          removeToast(ANALYSIS_LOADING_ID);
          setError(status.error ?? 'Pipeline failed');
          setActiveJobId(null);
          return true;
        }
      } catch (err) {
        if (!cancelled) {
          removeToast(ANALYSIS_LOADING_ID);
          setError(err instanceof Error ? err.message : 'Could not poll pipeline status');
          setActiveJobId(null);
        }
        return true;
      }
      return false;
    }

    void poll().then((done) => {
      if (done || cancelled) return;
      timer = window.setInterval(async () => {
        const finished = await poll();
        if (finished && timer) window.clearInterval(timer);
      }, 2500);
    });

    return () => {
      cancelled = true;
      if (timer) window.clearInterval(timer);
      removeToast(ANALYSIS_LOADING_ID);
    };
  }, [activeJobId, movieId, addToast, removeToast, updateToast]);

  async function prepareMovie() {
    if (!movieId) return;
    setError(null);
    try {
      const result = await api.prepareMovie(movieId);
      if (result.status === 'ready') {
        addToast({ message: 'Analysis ready', type: 'success' });
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

  async function rerunPipeline() {
    if (!movieId || activeJobId) return;
    setError(null);
    setRerunningPipeline(true);
    try {
      const result = await api.rerunPipeline(movieId);
      if (result.status === 'ready') {
        addToast({ message: 'Pipeline complete. Output saved.', type: 'success' });
        const refreshed = await api.getMovieAnalysis(movieId);
        setAnalysis(refreshed);
        return;
      }
      if (result.status === 'queued' && result.job_id) {
        setActiveJobId(result.job_id);
        addToast({
          id: ANALYSIS_LOADING_ID,
          message: 'Re-running pipeline…',
          type: 'loading',
        });
      } else {
        setError(result.message ?? 'Could not start pipeline');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not re-run pipeline');
    } finally {
      setRerunningPipeline(false);
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
          <div className="analysis-page-header">
            <button
              type="button"
              className="secondary-btn"
              onClick={() => navigate('/')}
              title="Back to home"
            >
              ← Back
            </button>
            <button
              type="button"
              className="secondary-btn"
              disabled={rerunningPipeline || activeJobId != null}
              onClick={rerunPipeline}
              title="Re-run the full pipeline (reviews, clustering, plot beats, what-ifs) and save output to backend/pipeline_outputs"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={rerunningPipeline || activeJobId ? 'spin' : ''}>
                <path d="M21 12a9 9 0 1 1-2.636-6.364" />
                <path d="M21 3v6h-6" />
              </svg>
              Re-run pipeline
            </button>
          </div>
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
              <div className="plot-collapsible">
                {(() => {
                  const plot = analysis.expanded_plot ?? analysis.plot_summary ?? analysis.movie.plot ?? 'No plot available yet.';
                  const isLong = plot.length > PLOT_PREVIEW_LENGTH;
                  const displayText = !plotExpanded && isLong ? `${plot.slice(0, PLOT_PREVIEW_LENGTH).trim()}…` : plot;
                  return (
                    <>
                      <p>{displayText}</p>
                      {isLong && (
                        <button
                          type="button"
                          className="plot-toggle"
                          onClick={() => setPlotExpanded((v) => !v)}
                        >
                          {plotExpanded ? 'Show less' : 'Read more'}
                        </button>
                      )}
                    </>
                  );
                })()}
              </div>
              <MovieScores
                imdb_rating={analysis.movie.imdb_rating}
                rotten_tomatoes={analysis.movie.rotten_tomatoes}
                audience_score={analysis.movie.audience_score}
              />
              <div className="hero-cta-row">
                <button
                  type="button"
                  className="primary-btn hero-cta-btn"
                  disabled={!analysis.what_if_suggestions?.length}
                  title={!analysis.what_if_suggestions?.length ? 'Prepare the movie first to get data-backed suggestions' : undefined}
                  onClick={() => {
                    const first = analysis.what_if_suggestions?.[0];
                    if (first) {
                      navigate(`/rewrite/${movieId}?whatIf=${encodeURIComponent(first.suggestion_id)}`, {
                        state: { whatIfText: first.text },
                      });
                    }
                  }}
                >
                  Explore Data-backed alternative
                </button>
                <button
                  type="button"
                  className="secondary-btn hero-cta-btn"
                  onClick={() => setShowCreateModal(true)}
                >
                  Create your own
                </button>
                <button
                  type="button"
                  className="secondary-btn hero-cta-btn"
                  onClick={() => setShowGraphPanel(true)}
                >
                  View Knowledge Graph
                </button>
                <button
                  type="button"
                  className="secondary-btn hero-cta-btn"
                  onClick={() => setShowPlotBeatGraphPanel(true)}
                >
                  Plot Beat Graph
                </button>
              </div>
            </div>
          </section>

          {showCreateModal ? (
            <div className="modal-backdrop" onClick={() => setShowCreateModal(false)} role="presentation">
              <div className="modal create-whatif-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="create-whatif-title">
                <h2 id="create-whatif-title">Create your own alternate ending</h2>
                <p className="modal-hint">What do you wish would have happened in the story?</p>
                <textarea
                  className="create-whatif-input"
                  placeholder="e.g. Cobb stays in the dream with Mal forever, or the top never stops spinning..."
                  value={customWhatIfInput}
                  onChange={(e) => setCustomWhatIfInput(e.target.value)}
                  rows={4}
                  autoFocus
                />
                <div className="modal-actions">
                  <button type="button" className="secondary-btn" onClick={() => setShowCreateModal(false)}>
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="primary-btn"
                    disabled={!customWhatIfInput.trim() || customWhatIfInput.trim().length < 10}
                    onClick={() => {
                      const text = customWhatIfInput.trim();
                      if (text.length >= 10) {
                        setShowCreateModal(false);
                        setCustomWhatIfInput('');
                        navigate(`/rewrite/${movieId}`, { state: { customWhatIf: text } });
                      }
                    }}
                  >
                    Start Rewrite
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          {showGraphPanel && movieId && analysis && (
            <KnowledgeGraphPanel
              movieId={movieId}
              movieTitle={analysis.movie.title}
              onClose={() => setShowGraphPanel(false)}
            />
          )}
          {showPlotBeatGraphPanel && movieId && analysis && (
            <PlotBeatGraphPanel
              movieId={movieId}
              movieTitle={analysis.movie.title}
              onClose={() => setShowPlotBeatGraphPanel(false)}
            />
          )}

          <section className="analysis-layout">
            <section>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
                <h2 style={{ margin: 0 }}>Complaint Clusters</h2>
                {(analysis.user_review_count != null || analysis.critic_review_count != null) && (
                  <span className="cluster-review-totals">
                    {analysis.user_review_count != null && (
                      <span title="User reviews (IMDb) used to form clusters">{analysis.user_review_count.toLocaleString()} user</span>
                    )}
                    {analysis.user_review_count != null && analysis.critic_review_count != null && ' · '}
                    {analysis.critic_review_count != null && (
                      <span title="Critic reviews used to form clusters">{analysis.critic_review_count.toLocaleString()} critic</span>
                    )}
                  </span>
                )}
              </div>
              <div className="cluster-list">
                {analysis.clusters.length ? (
                  analysis.clusters.map((cluster, idx) => {
                    const isOpen = expandedClusters.has(cluster.cluster_id);
                    return (
                      <article className="cluster-item cluster-collapsible" key={cluster.cluster_id}>
                        <button
                          className="cluster-toggle"
                          onClick={() => toggleCluster(cluster.cluster_id)}
                          aria-expanded={isOpen}
                        >
                          <div className="cluster-header">
                            <h3 className="cluster-theme">
                              Theme {idx + 1}: {cluster.label}
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem', gap: '0.5rem' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h2 style={{ margin: 0 }}>Plot Beats</h2>
                  {beatDensity && Object.keys(beatDensity).length > 0 && (
                    <p className="heat-legend" style={{ margin: '0.25rem 0 0', fontSize: '0.8rem', opacity: 0.7 }}>
                      Heat = complaint density (darker = more complaints aligned to this beat)
                    </p>
                  )}
                </div>
                <button
                  className="icon-btn"
                  disabled={refreshingPlot}
                  onClick={async () => {
                    if (!movieId) return;
                    setRefreshingPlot(true);
                    try {
                      await api.refreshPlotBeats(movieId);
                      addToast({ message: 'Plot beats refreshed', type: 'success' });
                      const refreshed = await api.getMovieAnalysis(movieId);
                      setAnalysis(refreshed);
                    } catch (err) {
                      addToast({
                        message: err instanceof Error ? err.message : 'Failed to refresh plot beats',
                        type: 'error',
                      });
                    } finally {
                      setRefreshingPlot(false);
                    }
                  }}
                  title="Re-scrape Wikipedia and regenerate plot beats"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={refreshingPlot ? 'spin' : ''}>
                    <path d="M21 12a9 9 0 1 1-2.636-6.364" />
                    <path d="M21 3v6h-6" />
                  </svg>
                </button>
              </div>
              {analysis.plot_beats.length ? (
                <div className="timeline">
                  {analysis.plot_beats.map((beat, idx) => {
                    const isOpen = expandedBeats.has(beat.beat_order);
                    const isLast = idx === analysis.plot_beats.length - 1;
                    const sortedKeys = beatDensity ? Object.keys(beatDensity).sort((a, b) => Number(a) - Number(b)) : [];
                    const density =
                      beatDensity?.[String(beat.beat_order)] ??
                      (sortedKeys[idx] != null && beatDensity ? beatDensity[sortedKeys[idx]] : null) ??
                      null;
                    const hasHeat = beatDensity && Object.keys(beatDensity).length > 0 && density != null;
                    const d = density ?? 0;
                    const r = Math.round(255 - 215 * d);
                    const g = Math.round(255 - 200 * d);
                    const b = Math.round(235 - 210 * d);
                    const heatColor = `rgb(${r}, ${g}, ${b})`;
                    const tooltipText = hasHeat ? `Complaint density: ${Math.round(d * 100)}% — darker = more complaints` : '';
                    return (
                      <div
                        className={`timeline-node${isLast ? ' timeline-node--last' : ''}${hasHeat ? ' timeline-node--heat' : ''}`}
                        key={`${beat.movie_id}-${beat.beat_order}`}
                        data-tooltip={tooltipText}
                      >
                        <div className="timeline-marker">
                          <div
                            className="timeline-dot"
                            style={hasHeat ? {
                              background: heatColor,
                              borderColor: `rgba(${r}, ${g}, ${b}, 0.9)`,
                              boxShadow: `0 0 12px rgba(${r}, ${g}, ${b}, 0.6)`,
                            } : undefined}
                          />
                          {!isLast && <div className="timeline-line" />}
                        </div>
                        <div
                          className="timeline-content"
                          style={hasHeat ? {
                            borderLeft: `4px solid ${heatColor}`,
                            paddingLeft: '0.6rem',
                            backgroundColor: `rgba(${r}, ${g}, ${b}, 0.12)`,
                            borderRadius: '6px',
                          } : undefined}
                        >
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

          {analysis.characters?.length ? (
            <>
              <CharacterArcChart characters={analysis.characters} />
              <section className="panel" style={{ marginTop: '1rem' }}>
                <h2>Characters</h2>
                <div className="timeline" style={{ marginTop: '0.6rem' }}>
                {analysis.characters.map((char) => {
                  const isOpen = expandedCharacters.has(char.character_id);
                  return (
                    <div className="timeline-node" key={char.character_id}>
                      <div className="timeline-marker">
                        <div className="timeline-dot" />
                      </div>
                      <div className="timeline-content">
                        <button
                          className="timeline-toggle"
                          onClick={() => toggleCharacter(char.character_id)}
                          aria-expanded={isOpen}
                        >
                          <span className="timeline-label">
                            {char.name} <em>({char.role})</em>
                          </span>
                          <svg
                            className={`timeline-chevron${isOpen ? ' timeline-chevron--open' : ''}`}
                            width="16"
                            height="16"
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
                        {isOpen && <p className="timeline-text">{char.analysis}</p>}
                      </div>
                    </div>
                  );
                })}
                </div>
              </section>
            </>
          ) : null}

          <section className="panel" style={{ marginTop: '1rem' }}>
            <h2>What-if Suggestions</h2>
            <div className="whatif-list" style={{ marginTop: '0.6rem' }}>
              {analysis.what_if_suggestions.length ? (
                analysis.what_if_suggestions.map((item) => (
                  <article className="whatif-item" key={item.suggestion_id}>
                    <p>{item.text}</p>
                    <button
                      className="primary-btn"
                      onClick={() =>
                        navigate(`/rewrite/${movieId}?whatIf=${item.suggestion_id}`, {
                          state: { whatIfText: item.text },
                        })
                      }
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
