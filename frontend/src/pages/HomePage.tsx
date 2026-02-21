import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { MoviePosterCard } from '../components/MoviePosterCard';
import type { MovieCandidate } from '../types/api';

export function HomePage() {
  const navigate = useNavigate();
  const [movies, setMovies] = useState<MovieCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
                onSelect={() => navigate(`/movie/${movie.movie_id}`)}
                actionLabel="Analyze"
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
