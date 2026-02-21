import type { MovieCandidate } from '../types/api';

type Props = {
  movie: MovieCandidate;
  onSelect?: (movie: MovieCandidate) => void;
  actionLabel?: string;
};

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png&text=Poster+Coming+Soon';

export function MoviePosterCard({ movie, onSelect, actionLabel = 'Open' }: Props) {
  const poster = movie.poster ?? PLACEHOLDER;
  return (
    <article className="poster-card">
      <img src={poster} alt={`${movie.title} poster`} loading="lazy" />
      <div className="poster-overlay">
        <div className="poster-meta">
          <h3>{movie.title}</h3>
          <p>{movie.year ?? 'Unknown year'}</p>
        </div>
        <div className="poster-scores">
          <span>RT {movie.rotten_tomatoes ?? '--'}</span>
          <span>Audience {movie.audience_score ?? '--'}</span>
        </div>
      </div>
      {onSelect ? (
        <button className="action-btn" onClick={() => onSelect(movie)}>
          {actionLabel}
        </button>
      ) : null}
    </article>
  );
}
