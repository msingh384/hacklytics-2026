import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { MovieCandidate } from '../types/api';

const PLACEHOLDER =
  'https://dummyimage.com/500x750/1b1b1b/e4e4de.png?text=Poster+Coming+Soon';

const CTA_LABEL = 'Explore Alternate Endings';
const ROTATE_INTERVAL_MS = 6000;

function shuffle<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function formatMeta(val: number | string | null | undefined): string {
  if (val == null || val === '') return '';
  const s = String(val);
  return s.includes('%') ? s : `${s}%`;
}

type Props = {
  movies: MovieCandidate[];
  onAnalyze?: (movie: MovieCandidate) => void;
};

export function HeroCarousel({ movies, onAnalyze }: Props) {
  const navigate = useNavigate();
  const [activeIndex, setActiveIndex] = useState(0);

  const carouselItems = useMemo(() => {
    const five = movies.slice(0, 5);
    return shuffle(five);
  }, [movies]);

  useEffect(() => {
    if (carouselItems.length < 2) return;
    const id = setInterval(() => {
      setActiveIndex((i) => (i + 1) % carouselItems.length);
    }, ROTATE_INTERVAL_MS);
    return () => clearInterval(id);
  }, [carouselItems.length]);

  const active = carouselItems[activeIndex];
  if (!active || carouselItems.length === 0) return null;

  const hasAnalysis = active.has_analysis === true;
  const poster = active.poster ?? PLACEHOLDER;
  const genre = (active.genre ?? 'Movie').split(',')[0].trim();
  const imdb = active.imdb_rating != null ? String(active.imdb_rating) : null;
  const rt = active.rotten_tomatoes != null ? formatMeta(active.rotten_tomatoes) : null;
  const meta = formatMeta(active.audience_score);

  function handleCta() {
    if (hasAnalysis) {
      navigate(`/movie/${active.movie_id}`);
    } else if (onAnalyze) {
      onAnalyze(active);
    }
  }

  function goPrev() {
    setActiveIndex((i) => (i - 1 + carouselItems.length) % carouselItems.length);
  }

  function goNext() {
    setActiveIndex((i) => (i + 1) % carouselItems.length);
  }

  return (
    <section className="hero-carousel" aria-label="Featured movies">
      <div
        className="hero-carousel__bg"
        style={{ backgroundImage: `url(${poster})` }}
        aria-hidden
      />

      <div className="hero-carousel__inner">
        <div className="hero-carousel__poster-wrap">
          <img
            src={poster}
            alt=""
            className="hero-carousel__poster"
          />
        </div>

        <div className="hero-carousel__info">
          <h1 className="hero-carousel__title">{active.title}</h1>
          <div className="hero-carousel__meta">
            <span className="hero-carousel__year">{active.year ?? 'Unknown year'}</span>
            <span className="hero-carousel__genre-pill">{genre}</span>
          </div>
          <div className="hero-carousel__ratings">
            {imdb && (
              <span className="hero-carousel__rating hero-carousel__rating--imdb">
                IMDb {imdb}
              </span>
            )}
            {rt && (
              <span className="hero-carousel__rating hero-carousel__rating--rt">
                🍅 {rt}
              </span>
            )}
            {meta && (
              <span className="hero-carousel__rating hero-carousel__rating--meta">
                META {meta}
              </span>
            )}
          </div>
          <p className="hero-carousel__synopsis">
            Explore alternate endings grounded in real audience complaints. Rewrite the story the way fans wanted.
          </p>
          <button
            type="button"
            className="hero-carousel__cta"
            onClick={handleCta}
          >
            {hasAnalysis ? CTA_LABEL : 'Analyze first'}
          </button>
        </div>
      </div>

      <button
        type="button"
        className="hero-carousel__arrow hero-carousel__arrow--prev"
        onClick={goPrev}
        aria-label="Previous slide"
      >
        &lt;
      </button>
      <button
        type="button"
        className="hero-carousel__arrow hero-carousel__arrow--next"
        onClick={goNext}
        aria-label="Next slide"
      >
        &gt;
      </button>

      <div className="hero-carousel__indicators" aria-hidden>
        {carouselItems.map((_, i) => (
          <button
            key={i}
            type="button"
            className={`hero-carousel__indicator ${i === activeIndex ? 'hero-carousel__indicator--active' : ''}`}
            onClick={() => setActiveIndex(i)}
            aria-label={`Go to slide ${i + 1}`}
          />
        ))}
      </div>
    </section>
  );
}
