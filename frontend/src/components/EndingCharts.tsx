import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts';
import type { ThemeCoverageScore } from '../types/api';

type Props = {
  score: ThemeCoverageScore;
  history: Array<{ step: number; narrative: string; choice?: string }>;
};

export function EndingCharts({ score, history }: Props) {
  const radarData = [
    { subject: 'Complaint Coverage', value: score.breakdown.complaint_coverage, fullMark: 100 },
    { subject: 'Preference Satisfaction', value: score.breakdown.preference_satisfaction, fullMark: 100 },
    { subject: 'Coherence', value: score.breakdown.coherence, fullMark: 100 },
  ];

  const barData = score.per_cluster.map((c) => ({
    name: c.cluster_label.length > 25 ? c.cluster_label.slice(0, 22) + '…' : c.cluster_label,
    addressed: c.addressed ? 100 : 0,
    notAddressed: c.addressed ? 0 : 100,
    fullName: c.cluster_label,
  }));

  const progressItems = [
    { label: 'Total', value: score.score_total, color: '#78824b' },
    { label: 'Complaint Coverage', value: score.breakdown.complaint_coverage, color: '#5a7a6a' },
    { label: 'Preference Satisfaction', value: score.breakdown.preference_satisfaction, color: '#b8a060' },
    { label: 'Coherence', value: score.breakdown.coherence, color: '#6a5a7a' },
  ];

  return (
    <div className="ending-charts">
      <section className="panel">
        <h2>Score Breakdown</h2>
        <div className="ending-charts-row">
          <div className="ending-radar-wrap">
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(228, 228, 222, 0.3)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: '#e4e4de', fontSize: 11 }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 100]}
                  tick={{ fill: '#e4e4de', fontSize: 10 }}
                />
                <Radar
                  name="Score"
                  dataKey="value"
                  stroke="#78824b"
                  fill="#78824b"
                  fillOpacity={0.4}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div className="ending-progress-rings">
            {progressItems.map((item) => (
              <div key={item.label} className="ending-progress-item">
                <div className="ending-progress-ring">
                  <svg viewBox="0 0 36 36" className="ending-progress-svg">
                    <path
                      className="ending-progress-bg"
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                    <path
                      className="ending-progress-fill"
                      style={{ stroke: item.color }}
                      strokeDasharray={`${item.value}, 100`}
                      d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                    />
                  </svg>
                  <span className="ending-progress-value">{item.value}</span>
                </div>
                <span className="ending-progress-label">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {barData.length > 0 ? (
        <section className="panel">
          <h2>Cluster Coverage</h2>
          <div className="ending-bar-wrap">
            <ResponsiveContainer width="100%" height={Math.max(200, barData.length * 36)}>
              <BarChart
                data={barData}
                layout="vertical"
                margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(228, 228, 222, 0.15)" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#e4e4de', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#e4e4de', fontSize: 10 }} width={75} />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid rgba(228,228,222,0.2)' }}
                  labelStyle={{ color: '#e4e4de' }}
                  formatter={(value: number | undefined) => [value != null ? `${value}%` : '', '']}
                  labelFormatter={(_, payload) => (payload?.[0] as { payload?: { fullName?: string } })?.payload?.fullName ?? ''}
                />
                <Bar dataKey="addressed" stackId="a" fill="#4a7a5a" name="Addressed" radius={[0, 4, 4, 0]} />
                <Bar dataKey="notAddressed" stackId="a" fill="#6a5a5a" name="Not addressed" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}

      {history.length > 0 ? (
        <section className="panel">
          <h2>Story Flow</h2>
          <div className="ending-story-flow-viz">
            {history.map((entry, idx) => (
              <div key={idx} className="ending-flow-step">
                <div className="ending-flow-marker">
                  <span className="ending-flow-step-num">{entry.step}</span>
                </div>
                <div className="ending-flow-content">
                  <p className="ending-flow-narrative">{entry.narrative}</p>
                  {entry.choice ? (
                    <p className="ending-flow-choice">
                      <span className="ending-flow-choice-label">Choice:</span> {entry.choice}
                    </p>
                  ) : null}
                </div>
                {idx < history.length - 1 ? <div className="ending-flow-connector" /> : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
