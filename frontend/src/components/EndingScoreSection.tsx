import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { ThemeCoverageScore } from '../types/api';

type Props = {
  score: ThemeCoverageScore;
};

const RING_COLORS = ['#78824b', '#5a7a6a', '#b8a060', '#6a5a7a'] as const;

export function EndingScoreSection({ score }: Props) {
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);

  const ringItems = [
    { label: 'Total', value: score.score_total },
    { label: 'Complaint Coverage', value: score.breakdown.complaint_coverage },
    { label: 'Preference Satisfaction', value: score.breakdown.preference_satisfaction },
    { label: 'Coherence', value: score.breakdown.coherence },
  ];

  const barData = score.per_cluster.map((c) => ({
    name: c.cluster_label.length > 28 ? c.cluster_label.slice(0, 25) + '…' : c.cluster_label,
    addressed: c.addressed ? 100 : 0,
    notAddressed: c.addressed ? 0 : 100,
    fullName: c.cluster_label,
  }));

  return (
    <section className="ending-score-section">
      <h2 className="ending-score-heading">Theme Coverage</h2>
      <p className="ending-score-desc">How well this ending addressed audience feedback</p>

      {/* Score rings */}
      <div className="ending-score-rings">
        {ringItems.map((item, i) => (
          <div key={item.label} className="ending-ring-item">
            <div className="ending-ring">
              <svg viewBox="0 0 36 36" className="ending-ring-svg">
                <path
                  className="ending-ring-bg"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
                <path
                  className="ending-ring-fill"
                  style={{ stroke: RING_COLORS[i % 4] }}
                  strokeDasharray={`${item.value}, 100`}
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                />
              </svg>
              <span className="ending-ring-value">{item.value}</span>
            </div>
            <span className="ending-ring-label">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Cluster coverage + evidence */}
      {barData.length > 0 && (
        <div className="ending-clusters">
          <h3 className="ending-clusters-heading">By theme</h3>
          <div className="ending-clusters-chart">
            <ResponsiveContainer width="100%" height={Math.max(160, barData.length * 32)}>
              <BarChart
                data={barData}
                layout="vertical"
                margin={{ top: 4, right: 12, left: 4, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="2 2" stroke="rgba(228, 228, 222, 0.1)" />
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis type="category" dataKey="name" tick={{ fill: '#e4e4de', fontSize: 11 }} width={120} />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid rgba(228,228,222,0.2)', fontSize: 12 }}
                  formatter={() => []}
                  labelFormatter={(_, payload) => {
                    const p = payload?.[0]?.payload;
                    if (!p) return '';
                    return p.addressed ? 'Addressed' : 'Not addressed';
                  }}
                />
                <Bar dataKey="addressed" stackId="a" fill="#4a7a5a" radius={[0, 4, 4, 0]} />
                <Bar dataKey="notAddressed" stackId="a" fill="#5a4a4a" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ul className="ending-evidence-list">
            {score.per_cluster.map((c) => {
              const isExpanded = expandedCluster === c.cluster_label;
              return (
                <li key={`${c.cluster_label}-${c.review_reference}`} className="ending-evidence-item">
                  <button
                    type="button"
                    className={`ending-evidence-toggle${c.addressed ? ' ending-evidence-toggle--addressed' : ''}`}
                    onClick={() => setExpandedCluster(isExpanded ? null : c.cluster_label)}
                    aria-expanded={isExpanded}
                  >
                    <span className="ending-evidence-badge">{c.addressed ? 'Addressed' : 'Not addressed'}</span>
                    <span className="ending-evidence-label">{c.cluster_label}</span>
                  </button>
                  {isExpanded && (
                    <div className="ending-evidence-detail">
                      <p>{c.evidence_excerpt}</p>
                      <small>Ref: {c.review_reference}</small>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
