import { useMemo } from 'react';
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
  const arcs = useMemo(() => {
    return characters.map((char) => {
      const analysis = char.analysis || '';
      const role = (char.role || 'supporting').toLowerCase();
      const color = ROLE_COLORS[role] ?? ROLE_COLORS.default;
      // Simple arc visualization: extract key phrases from analysis
      const hasArc = /arc|journey|transform|evolve|change|growth|culminat/i.test(analysis);
      const arcStrength = hasArc ? 0.8 : 0.4;
      return {
        id: char.character_id,
        name: char.name,
        role: char.role,
        analysis,
        color,
        arcStrength,
      };
    });
  }, [characters]);

  if (arcs.length === 0) return null;

  return (
    <section className="panel character-arc-chart" style={{ marginTop: '1rem' }}>
      <h2>Character Journey</h2>
      <p className="section-hint" style={{ fontSize: '0.85rem', opacity: 0.8, marginBottom: '0.8rem' }}>
        Character arcs and roles inferred from analysis
      </p>
      <div className="character-arc-grid">
        {arcs.map((arc) => (
          <article key={arc.id} className="character-arc-card">
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
          </article>
        ))}
      </div>
    </section>
  );
}
