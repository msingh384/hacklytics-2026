type ScoreProps = {
  imdb_rating?: number | string | null;
  rotten_tomatoes?: number | string | null;
  audience_score?: number | string | null;
};

type Props = ScoreProps & {
  variant?: 'full' | 'compact';
};

function formatScore(val: number | string | null | undefined): string {
  if (val == null || val === '') return '--';
  return String(val);
}

export function MovieScores({
  imdb_rating,
  rotten_tomatoes,
  audience_score,
  variant = 'full',
}: Props) {
  const imdb = formatScore(imdb_rating);
  const rt = formatScore(rotten_tomatoes);
  const meta = formatScore(audience_score);

  if (variant === 'compact') {
    return (
      <div className="movie-scores movie-scores--compact">
        <span className="movie-scores__item movie-scores__item--imdb">
          IMDb {imdb}
        </span>
        <span className="movie-scores__item movie-scores__item--rt">
          🍅 {rt}
        </span>
      </div>
    );
  }

  return (
    <div className="analysis-stats">
      <div className="score-card score-card--imdb">
        <span className="score-label">IMDb</span>
        <span className="score-value">{imdb}</span>
      </div>
      <div className="score-card score-card--rt">
        <span className="score-label">🍅</span>
        <span className="score-value">{rt}</span>
      </div>
      <div className="score-card score-card--audience">
        <span className="score-label">Meta</span>
        <span className="score-value">{meta}</span>
      </div>
    </div>
  );
}
