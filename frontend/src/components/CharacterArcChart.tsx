import { useCallback, useEffect, useMemo, useState } from 'react';
import type { MovieCharacter } from '../types/api';

type Props = {
  characters: MovieCharacter[];
};

const ROLE_COLORS: Record<string, string> = {
  protagonist: '#78824b',
  antagonist: '#a06060',
  'internal antagonist': '#8a6a6a',
  supporting: '#5a7a6a',
  target: '#6a7a8a',
  default: '#6a6a6a',
};

export function CharacterArcChart({ characters }: Props) {
  const [selectedCharacter, setSelectedCharacter] = useState<MovieCharacter | null>(null);

  const arcs = useMemo(() => {
    return characters.map((char) => {
      const analysis = char.analysis || '';
      const role = (char.role || 'supporting').toLowerCase();
      const color = ROLE_COLORS[role] ?? ROLE_COLORS.default;
      const hasArc = /arc|journey|transform|evolve|change|growth|culminat/i.test(analysis);
      const arcStrength = hasArc ? 0.8 : 0.4;
      return {
        ...char,
        color,
        arcStrength,
      };
    });
  }, [characters]);

  const closeModal = useCallback(() => setSelectedCharacter(null), []);

  useEffect(() => {
    if (!selectedCharacter) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeModal();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedCharacter, closeModal]);

  if (arcs.length === 0) return null;

  return (
    <>
      <section className="panel character-arc-chart" style={{ marginTop: '1rem' }}>
        <h2>Character Journey</h2>
        <p className="section-hint" style={{ fontSize: '0.85rem', opacity: 0.8, marginBottom: '0.8rem' }}>
          Click a character to view full analysis
        </p>
        <div className="character-arc-grid">
          {arcs.map((arc) => (
            <button
              type="button"
              key={arc.character_id}
              className="character-arc-card character-arc-card--clickable"
              onClick={() => setSelectedCharacter(arc)}
            >
              <div className="character-arc-header">
                <span className="character-arc-name">{arc.name}</span>
                <span
                  className="character-arc-role"
                  style={{ backgroundColor: arc.color, color: '#fff' }}
                >
                  {arc.role}
                </span>
              </div>
              <div className="character-arc-bar">
                <div
                  className="character-arc-fill"
                  style={{
                    width: `${arc.arcStrength * 100}%`,
                    backgroundColor: arc.color,
                  }}
                />
              </div>
              <p className="character-arc-arc-label">
                {arc.arcStrength > 0.6 ? 'Strong arc' : 'Supporting role'}
              </p>
            </button>
          ))}
        </div>
      </section>

      {selectedCharacter && (
        <div
          className="modal-backdrop"
          onClick={closeModal}
          onKeyDown={(e) => e.key === 'Escape' && closeModal()}
          role="presentation"
        >
          <div
            className="modal character-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="character-modal-title"
          >
            <div className="character-modal-header">
              <h2 id="character-modal-title">{selectedCharacter.name}</h2>
              <span
                className="character-modal-role"
                style={{
                  backgroundColor: ROLE_COLORS[(selectedCharacter.role || '').toLowerCase()] ?? ROLE_COLORS.default,
                  color: '#fff',
                }}
              >
                {selectedCharacter.role}
              </span>
            </div>
            <p className="character-modal-analysis">{selectedCharacter.analysis}</p>
            <button
              type="button"
              className="secondary-btn"
              onClick={closeModal}
              style={{ marginTop: '1rem' }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
