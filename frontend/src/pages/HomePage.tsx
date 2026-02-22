import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MoviePosterCard } from '../components/MoviePosterCard';
import { useToast } from '../contexts/ToastContext';
import type { MovieCandidate } from '../types/api';

type ActiveJob = { jobId: string; movieId: string; title: string };

export function HomePage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [movies, setMovies] = useState<MovieCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<ActiveJob[]>([]);
  const activeJobsRef = useRef<ActiveJob[]>([]);
  activeJobsRef.current = activeJobs;

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
        setError(err instanceof Error ? err.message : 'Failed to load featured movies');
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
            setMovies((prev) =>
              prev.map((m) => (m.movie_id === job.movieId ? { ...m, has_analysis: true } : m))
            );
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
      setError(response.message ?? 'Could not start analysis');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start analysis');
    }
  }

  const grouped = useMemo(() => {
    const map = new Map<string, MovieCandidate[]>();
    for (const movie of movies) {
      const rawGenre = movie.genre ?? 'Featured';
      const genre = rawGenre.split(',')[0].trim() || 'Featured';
      const bucket = map.get(genre) ?? [];
      bucket.push(movie);
      map.set(genre, bucket);
    }
    return Array.from(map.entries());
  }, [movies]);

  return (
    <div>
      <h1 className="section-title">Rewrite the endings audiences wanted</h1>
      <p className="section-subtitle">
        Browse all available movies by genre, then launch data-grounded rewrites from real review complaints.
      </p>

      {loading ? <p>Loading featured catalog...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !movies.length ? (
        <div className="empty-state">
          <p>No movies are cached yet. Use Search to add one through the pipeline.</p>
        </div>
      ) : null}

      {grouped.map(([genre, items]) => (
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
    </div>
  );
}
