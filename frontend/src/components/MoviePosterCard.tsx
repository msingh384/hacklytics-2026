import type { MovieCandidate } from '../types/api';

type Props = {
  movie: MovieCandidate;
  onSelect?: (movie: MovieCandidate) => void;
  onPosterClick?: (movie: MovieCandidate) => void;
  actionLabel?: string;
};

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png&text=Poster+Coming+Soon';

export function MoviePosterCard({ movie, onSelect, onPosterClick, actionLabel = 'Open' }: Props) {
  const poster = movie.poster ?? PLACEHOLDER;
  const analyzed = movie.has_analysis === true;

  function handlePosterClick() {
    if (onPosterClick) {
      onPosterClick(movie);
    }
  }

  return (
    <article className="poster-card">
      <img src={poster} alt="" loading="lazy" />
      <button
        type="button"
        className="poster-click-target"
        onClick={handlePosterClick}
        aria-label={analyzed ? `Open ${movie.title} analysis` : movie.title}
      />
      <div className="poster-overlay" aria-hidden>
        <div className="poster-meta">
          <h3>{movie.title}</h3>
          <p>{movie.year ?? 'Unknown year'}</p>
        </div>
        <div className="poster-scores">
          <span>RT {movie.rotten_tomatoes ?? '--'}</span>
          <span>Audience {movie.audience_score ?? '--'}</span>
        </div>
      </div>
      {!analyzed && onSelect ? (
        <button
          type="button"
          className="action-btn"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(movie);
          }}
        >
          {actionLabel}
        </button>
      ) : null}
    </article>
  );
}
