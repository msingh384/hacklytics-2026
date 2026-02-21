import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { LoadingProgress } from '../components/LoadingProgress';
import { MoviePosterCard } from '../components/MoviePosterCard';
import type { JobStatus, MovieCandidate } from '../types/api';

export function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MovieCandidate[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  useEffect(() => {
    if (!activeJobId) return;
    const timer = window.setInterval(async () => {
      try {
        const status = await api.getPipelineJob(activeJobId);
        setJob(status);
        if (status.status === 'ready' && status.movie_id) {
          window.clearInterval(timer);
          navigate(`/movie/${status.movie_id}`);
        }
        if (status.status === 'failed') {
          window.clearInterval(timer);
          setError(status.error ?? 'Movie pipeline failed');
        }
      } catch (err) {
        window.clearInterval(timer);
        setError(err instanceof Error ? err.message : 'Failed to check pipeline status');
      }
    }, 1800);

    return () => window.clearInterval(timer);
  }, [activeJobId, navigate]);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);

    try {
      const data = await api.searchMovies(query.trim());
      setResults(data);
      if (!data.length) {
        setError('No movies found. Try another title or browse Home.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  }

  async function prepareMovie(movie: MovieCandidate) {
    setError(null);
    setJob(null);
    try {
      const response = await api.startPipeline(movie.title, movie.movie_id);
      if (response.status === 'ready' && response.movie_id) {
        navigate(`/movie/${response.movie_id}`);
        return;
      }
      if (response.status === 'queued' && response.job_id) {
        setActiveJobId(response.job_id);
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
      <p className="section-subtitle">Type a movie title to trigger OMDB + reviews + embeddings + clusters pipeline.</p>

      <form className="search-row" onSubmit={handleSearch}>
        <input
          placeholder="Search by movie title..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button className="primary-btn" type="submit" disabled={searching}>
          {searching ? 'Searching...' : 'Search'}
        </button>
      </form>

      {job ? <LoadingProgress job={job} /> : null}
      {error ? <p className="error">{error}</p> : null}

      {results.length ? (
        <div className="poster-grid">
          {results.map((movie) => (
            <MoviePosterCard
              key={movie.movie_id}
              movie={movie}
              onSelect={() => prepareMovie(movie)}
              actionLabel="Prepare"
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
