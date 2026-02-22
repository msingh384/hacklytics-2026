export type MovieCandidate = {
  movie_id: string;
  title: string;
  year?: string | null;
  genre?: string | null;
  poster?: string | null;
  imdb_rating?: number | null;
  rotten_tomatoes?: string | null;
  audience_score?: string | null;
  has_analysis?: boolean | null;
};

export type PipelineStartResponse = {
  status: 'needs_selection' | 'queued' | 'ready' | 'failed';
  job_id?: string | null;
  movie_id?: string | null;
  message?: string | null;
  candidates: MovieCandidate[];
};

export type JobStatus = {
  job_id: string;
  status: 'queued' | 'running' | 'ready' | 'failed';
  stage: string;
  progress: number;
  movie_id?: string | null;
  message?: string | null;
  error?: string | null;
  updated_at: string;
};

export type PlotBeat = {
  movie_id: string;
  beat_order: number;
  label: string;
  beat_text: string;
};

export type ComplaintCluster = {
  movie_id: string;
  cluster_id: string;
  label: string;
  summary: string;
  review_count: number;
};

export type ClusterExample = {
  movie_id: string;
  cluster_id: string;
  example_id: string;
  review_text: string;
  source: 'user' | 'critic';
  review_reference?: string | null;
};

export type WhatIfSuggestion = {
  movie_id: string;
  suggestion_id: string;
  text: string;
  linked_cluster_ids: string[];
};

export type ReviewRecord = {
  movie_id: string;
  movie_title?: string | null;
  movie_review: string;
  rating?: number | null;
  source: 'user' | 'critic';
};

export type MovieDetails = {
  movie_id: string;
  title: string;
  year?: string | null;
  genre?: string | null;
  poster?: string | null;
  imdb_rating?: number | null;
  rotten_tomatoes?: string | null;
  audience_score?: string | null;
  plot?: string | null;
  full_omdb?: Record<string, unknown>;
};

export type MovieAnalysisResponse = {
  movie: MovieDetails;
  plot_summary?: string | null;
  expanded_plot?: string | null;
  plot_beats: PlotBeat[];
  clusters: ComplaintCluster[];
  cluster_examples: ClusterExample[];
  what_if_suggestions: WhatIfSuggestion[];
  review_samples: ReviewRecord[];
};

export type StoryOption = {
  option_id: string;
  label: string;
  text: string;
};

export type StoryStartResponse = {
  story_session_id: string;
  movie_id: string;
  what_if: string;
  narrative: string;
  options: StoryOption[];
  step_number: number;
  total_steps: number;
};

export type StoryStepResponse = {
  story_session_id: string;
  step_number: number;
  narrative: string;
  options: StoryOption[];
  ending?: string | null;
  is_complete: boolean;
};

export type ThemeCoverageScore = {
  score_total: number;
  breakdown: {
    complaint_coverage: number;
    preference_satisfaction: number;
    coherence: number;
  };
  per_cluster: Array<{
    cluster_label: string;
    addressed: boolean;
    evidence_excerpt: string;
    review_reference: string;
  }>;
};

export type GenerationResponse = {
  generation_id: string;
  movie_id: string;
  session_id: string;
  ending_text: string;
  votes: number;
  score_total: number;
  created_at: string;
};

export type LeaderboardItem = {
  generation_id: string;
  movie_id: string;
  movie_title: string;
  ending_text: string;
  votes: number;
  score_total: number;
  created_at: string;
};
