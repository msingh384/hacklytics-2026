import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { HeroCarousel } from '../components/HeroCarousel';
import { MoviePosterCard } from '../components/MoviePosterCard';
import { useSearch } from '../contexts/SearchContext';
import { useToast } from '../contexts/ToastContext';
import type { MovieCandidate } from '../types/api';

const SEARCH_DEBOUNCE_MS = 320;

type ActiveJob = { jobId: string; movieId: string; title: string };

export function HomePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { query: searchQuery } = useSearch();
  const [movies, setMovies] = useState<MovieCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<MovieCandidate[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const activeJobsRef = useRef<ActiveJob[]>([]);
  activeJobsRef.current = activeJobs;

  const runSearch = useCallback(async (term: string) => {
    if (!term.trim()) {
      setSearchResults(null);
      setSearchError(null);
      return;
    }
    setSearchError(null);
    try {
      const data = await api.searchMovies(term.trim());
      setSearchResults(data);
      if (!data.length) {
        setSearchError('No movies found. Try another title.');
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Search failed');
      setSearchResults([]);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      runSearch(searchQuery);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchQuery, runSearch]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    api
      .featuredMovies()
      .then((data) => {
        if (!active) return;
        setMovies(data);
      })
      .catch((err: unknown) => {
        if (!active) return;
        const msg = err instanceof Error ? err.message : 'Failed to load featured movies';
        const isNetworkError = /failed to fetch|network error|load failed/i.test(msg);
        setError(
          isNetworkError
            ? "Could not reach the backend. Ensure it's running (./start.sh) and wait ~10s after startup."
            : msg
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (activeJobs.length === 0) return;
    const timer = window.setInterval(async () => {
      const jobs = [...activeJobsRef.current];
      for (const job of jobs) {
        try {
          const status = await api.getPipelineJob(job.jobId);
          toast.updateToast(`loading-${job.movieId}`, {
            stage: status.stage,
            progress: status.progress,
          });
          if (status.status === 'ready') {
            toast.removeToast(`loading-${job.movieId}`);
            toast.addToast({ message: `Analysis ready: ${job.title}`, type: 'success' });
            setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
            const updateHasAnalysis = (m: MovieCandidate) =>
              m.movie_id === job.movieId ? { ...m, has_analysis: true } : m;
            setMovies((prev) => prev.map(updateHasAnalysis));
            setSearchResults((prev) => (prev ? prev.map(updateHasAnalysis) : null));
          } else if (status.status === 'failed') {
            toast.removeToast(`loading-${job.movieId}`);
            toast.addToast({
              message: `Failed: ${job.title}`,
              type: 'error',
            });
            setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
          }
        } catch {
          toast.removeToast(`loading-${job.movieId}`);
          setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
        }
      }
    }, 1800);

    return () => window.clearInterval(timer);
  }, [activeJobs.length, toast]);

  async function analyzeMovie(movie: MovieCandidate) {
    setError(null);
    try {
      const response = await api.startPipeline(movie.title, movie.movie_id);
      if (response.status === 'ready' && response.movie_id) {
        toast.addToast({ message: `Analysis ready: ${movie.title}`, type: 'success' });
        setMovies((prev) =>
          prev.map((m) =>
            m.movie_id === movie.movie_id ? { ...m, has_analysis: true } : m
          )
        );
        navigate(`/movie/${response.movie_id}`);
        return;
      }
      if (response.status === 'queued' && response.job_id) {
        const job: ActiveJob = {
          jobId: response.job_id,
          movieId: movie.movie_id,
          title: movie.title,
        };
        setActiveJobs((prev) => [...prev, job]);
        toast.addToast({
          id: `loading-${movie.movie_id}`,
          message: `Preparing analysis: ${movie.title}`,
          type: 'loading',
        });
        return;
      }
      if (response.status === 'needs_selection' && response.candidates?.length) {
        setSearchResults(response.candidates);
        return;
      }
      setError(response.message ?? 'Could not start analysis');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start analysis');
    }
  }

  const groupByGenre = useCallback((list: MovieCandidate[]) => {
    const map = new Map<string, MovieCandidate[]>();
    for (const movie of list) {
      const rawGenre = movie.genre ?? 'Other';
      const genres = rawGenre.split(',').map((g) => g.trim()).filter(Boolean) || ['Other'];
      for (const genre of genres) {
        const key = genre || 'Other';
        const bucket = map.get(key) ?? [];
        bucket.push(movie);
        map.set(key, bucket);
      }
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, []);

  const grouped = useMemo(() => groupByGenre(movies), [movies, groupByGenre]);
  const groupedSearch = useMemo(
    () => (searchResults ? groupByGenre(searchResults) : []),
    [searchResults, groupByGenre]
  );

  const isFiltering = searchQuery.trim().length > 0;

  return (
    <div className="home-layout">
      {loading && !isFiltering ? (
        <div className="skeleton-hero-carousel" aria-hidden>
          <div className="skeleton-hero-carousel__inner">
            <div className="skeleton skeleton-hero-poster" />
            <div className="skeleton-hero-carousel__info">
              <div className="skeleton skeleton-hero-title" />
              <div className="skeleton-hero-carousel__meta">
                <div className="skeleton skeleton-hero-year" />
                <div className="skeleton skeleton-hero-genre" />
              </div>
              <div className="skeleton-hero-carousel__ratings">
                <div className="skeleton skeleton-hero-rating" />
                <div className="skeleton skeleton-hero-rating" />
                <div className="skeleton skeleton-hero-rating" />
              </div>
              <div className="skeleton-hero-carousel__synopsis">
                <div className="skeleton skeleton-plot-line" />
                <div className="skeleton skeleton-plot-line" />
                <div className="skeleton skeleton-plot-line" />
                <div className="skeleton skeleton-plot-line skeleton-plot-line--short" />
              </div>
              <div className="skeleton skeleton-hero-cta" />
            </div>
          </div>
        </div>
      ) : (
        <HeroCarousel movies={movies} onAnalyze={analyzeMovie} />
      )}
      <div className="page-container home-content">
        {loading && !isFiltering ? (
          <>
            <div className="skeleton skeleton-section-title" aria-hidden />
            <div className="skeleton skeleton-section-subtitle" aria-hidden />
            <div className="skeleton-genre-block">
              <h2 className="skeleton" aria-hidden />
              <div className="poster-grid">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="poster-card skeleton-poster-card" aria-hidden>
                    <div className="skeleton skeleton-poster" />
                    <div className="poster-overlay">
                      <div className="skeleton skeleton-title" style={{ marginBottom: '0.3rem' }} />
                      <div className="skeleton skeleton-text skeleton-text--sm" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <>
            <h1 className="section-title">Rewrite the endings audiences wanted</h1>
            <p className="section-subtitle">
              Browse all available movies by genre, then launch data-grounded rewrites from real review complaints.
            </p>
            {error ? <p className="error">{error}</p> : null}
            {searchError ? <p className="error">{searchError}</p> : null}

            {isFiltering && groupedSearch.length > 0
              ? groupedSearch.map(([genre, items]) => (
                  <section key={genre} className="genre-block">
                    <h2>{genre}</h2>
                    <div className="poster-grid">
                      {items.map((movie) => (
                        <MoviePosterCard
                          key={movie.movie_id}
                          movie={movie}
                          onSelect={() => analyzeMovie(movie)}
                          onPosterClick={(m) => {
                            if (m.has_analysis) {
                              navigate(`/movie/${m.movie_id}`);
                            } else {
                              toast.addToast({
                                message: 'Analysis required first.',
                                type: 'info',
                              });
                            }
                          }}
                          actionLabel="Analyze"
                        />
                      ))}
                    </div>
                  </section>
                ))
              : null}

            {isFiltering && searchResults?.length === 0 && !searchError ? (
              <div className="empty-state">
                <p>No movies found for &ldquo;{searchQuery}&rdquo;. Try another search.</p>
              </div>
            ) : null}

            {!loading && !error && !isFiltering && !movies.length ? (
              <div className="empty-state">
                <p>No movies are cached yet. Use the search bar in the header to add one through the pipeline.</p>
              </div>
            ) : null}

            {!isFiltering &&
              grouped.map(([genre, items]) => (
                <section key={genre} className="genre-block">
                  <h2>{genre}</h2>
                  <div className="poster-grid">
                    {items.map((movie) => (
                      <MoviePosterCard
                        key={movie.movie_id}
                        movie={movie}
                        onSelect={() => analyzeMovie(movie)}
                        onPosterClick={(m) => {
                          if (m.has_analysis) {
                            navigate(`/movie/${m.movie_id}`);
                          } else {
                            toast.addToast({
                              message: 'Analysis required first.',
                              type: 'info',
                            });
                          }
                        }}
                        actionLabel="Analyze"
                      />
                    ))}
                  </div>
                </section>
              ))}
          </>
        )}
      </div>
    </div>
  );
}
