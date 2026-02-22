import type { JobStatus } from '../types/api';

type Props = {
  job: JobStatus;
};

export function LoadingProgress({ job }: Props) {
  return (
    <section className="loading-card" aria-live="polite">
      <p className="loading-title">Preparing your movie analysis...</p>
      <p className="loading-stage">{job.stage.replace(/_/g, ' ')}</p>
      <div className="progress-track">
        <span className="progress-fill" style={{ width: `${job.progress}%` }} />
      </div>
      <p className="loading-caption">{job.message ?? 'Working through data pipeline...'}</p>
    </section>
  );
}
