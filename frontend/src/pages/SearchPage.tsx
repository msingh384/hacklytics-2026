import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MoviePosterCard } from '../components/MoviePosterCard';
import { useToast } from '../contexts/ToastContext';
import type { MovieCandidate } from '../types/api';

const SEARCH_DEBOUNCE_MS = 320;

type ActiveJob = { jobId: string; movieId: string; title: string };

export function SearchPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MovieCandidate[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const activeJobsRef = useRef<ActiveJob[]>([]);
  activeJobsRef.current = activeJobs;

  const runSearch = useCallback(async (term: string) => {
    if (!term.trim()) {
      setResults([]);
      setError(null);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const data = await api.searchMovies(term.trim());
      setResults(data);
      if (!data.length) {
        setError('No movies found. Try another title or browse Home.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setResults([]);
    } finally {
      setSearching(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => {
      runSearch(query);
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [query, runSearch]);

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
            const wasOnly = activeJobsRef.current.length === 1;
            setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
            setResults((prev) =>
              prev.map((m) => (m.movie_id === job.movieId ? { ...m, has_analysis: true } : m))
            );
            if (wasOnly) navigate(`/movie/${job.movieId}`);
          } else if (status.status === 'failed') {
            toast.removeToast(`loading-${job.movieId}`);
            toast.addToast({ message: `Failed: ${job.title}`, type: 'error' });
            setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
          }
        } catch {
          toast.removeToast(`loading-${job.movieId}`);
          setActiveJobs((prev) => prev.filter((j) => j.jobId !== job.jobId));
        }
      }
    }, 1800);

    return () => window.clearInterval(timer);
  }, [activeJobs.length, navigate, toast]);

  async function analyzeMovie(movie: MovieCandidate) {
    setError(null);
    try {
      const response = await api.startPipeline(movie.title, movie.movie_id);
      if (response.status === 'ready' && response.movie_id) {
        toast.addToast({ message: `Analysis ready: ${movie.title}`, type: 'success' });
        setResults((prev) =>
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
      if (response.status === 'needs_selection' && response.candidates.length) {
        setResults(response.candidates);
        return;
      }
      setError(response.message ?? 'Could not start pipeline');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not prepare movie');
    }
  }

  return (
    <div>
      <h1 className="section-title">Search Movies</h1>
      <p className="section-subtitle">Type a movie title.</p>

      <div className="search-row">
        <input
          type="search"
          placeholder="Type a movie title"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Movie title"
        />
        {searching ? <span className="search-status">Searching…</span> : null}
      </div>

      {error ? <p className="error">{error}</p> : null}

      {results.length ? (
        <div className="poster-grid">
          {results.map((movie) => (
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
      ) : null}
    </div>
  );
}
