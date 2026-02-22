import type {
  GenerationResponse,
  JobStatus,
  LeaderboardItem,
  MovieAnalysisResponse,
  MovieCandidate,
  PipelineStartResponse,
  StoryStartResponse,
  StoryStepResponse,
  ThemeCoverageScore,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';

function messageFromErrorBody(text: string): string {
  const trimmed = text?.trim();
  if (!trimmed) return 'API request failed';
  try {
    const json = JSON.parse(trimmed) as { detail?: string };
    const detail = typeof json.detail === 'string' ? json.detail : trimmed;
    if (/invalid imdb id|incorrect imdb id/i.test(detail))
      return "Couldn't load movies. Use Search to add a movie, or check the backend is connected to the database.";
    return detail;
  } catch {
    return trimmed;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(messageFromErrorBody(errorText));
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  featuredMovies: () => request<MovieCandidate[]>('/movies/featured'),

  searchMovies: (query: string, year?: string) => {
    const params = new URLSearchParams({ q: query });
    if (year) params.set('year', year);
    return request<MovieCandidate[]>(`/movies/search?${params.toString()}`);
  },

  startPipeline: (query: string, selectedImdbId?: string | null) =>
    request<PipelineStartResponse>('/pipeline/search', {
      method: 'POST',
      body: JSON.stringify({ query, selected_imdb_id: selectedImdbId ?? null }),
    }),

  getPipelineJob: (jobId: string) => request<JobStatus>(`/pipeline/jobs/${jobId}`),

  prepareMovie: (movieId: string) =>
    request<PipelineStartResponse>(`/movies/${movieId}/prepare`, {
      method: 'POST',
    }),

  rerunPipeline: (movieId: string) =>
    request<PipelineStartResponse>(`/movies/${movieId}/rerun-pipeline`, {
      method: 'POST',
    }),

  getMovieAnalysis: (movieId: string) => request<MovieAnalysisResponse>(`/movies/${movieId}/analysis`),

  getBeatComplaintDensity: (movieId: string) =>
    request<import('../types/api').BeatComplaintDensity>(`/movies/${movieId}/beat-complaint-density`),

  refreshPlotBeats: (movieId: string) =>
    request<{ status: string; message: string }>(`/movies/${movieId}/refresh-plot`, {
      method: 'POST',
    }),

  getGraph: (movieId: string) =>
    request<import('../types/api').GraphResponse>(`/movies/${movieId}/graph`),

  getPlotBeatGraph: (movieId: string) =>
    request<import('../types/api').GraphResponse>(`/movies/${movieId}/graph/plot-beats`),

  startStory: (movieId: string, sessionId: string, whatIfId?: string, customWhatIf?: string) =>
    request<StoryStartResponse>('/story/start', {
      method: 'POST',
      body: JSON.stringify({
        movie_id: movieId,
        session_id: sessionId,
        what_if_id: whatIfId ?? null,
        custom_what_if: customWhatIf ?? null,
      }),
    }),

  storyStep: (storySessionId: string, sessionId: string, optionId: string) =>
    request<StoryStepResponse>('/story/step', {
      method: 'POST',
      body: JSON.stringify({
        story_session_id: storySessionId,
        session_id: sessionId,
        option_id: optionId,
      }),
    }),

  scoreEnding: (storySessionId: string, endingText: string) =>
    request<ThemeCoverageScore>('/story/coverage', {
      method: 'POST',
      body: JSON.stringify({
        story_session_id: storySessionId,
        ending_text: endingText,
      }),
    }),

  saveGeneration: (
    movieId: string,
    sessionId: string,
    storySessionId: string,
    endingText: string,
    storyPayload: Record<string, unknown>,
    scorePayload: ThemeCoverageScore,
  ) =>
    request<GenerationResponse>('/generations', {
      method: 'POST',
      body: JSON.stringify({
        movie_id: movieId,
        session_id: sessionId,
        story_session_id: storySessionId,
        ending_text: endingText,
        story_payload: storyPayload,
        score_payload: scorePayload,
      }),
    }),

  voteGeneration: (generationId: string, sessionId: string, value: number) =>
    request<{ generation_id: string; votes: number }>(`/generations/${generationId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, value }),
    }),

  getGeneration: (generationId: string) =>
    request<import('../types/api').GenerationDetail>(`/generations/${generationId}`),

  leaderboard: (sessionId?: string) => {
    const params = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return request<{ items: LeaderboardItem[] }>(`/explore/leaderboard${params}`);
  },

  generateTTS: async (text: string): Promise<string> => {
    const response = await fetch(`${API_BASE}/tts/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) return '';
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },
};
