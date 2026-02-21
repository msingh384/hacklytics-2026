import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { TypingNarrative } from '../components/TypingNarrative';
import { useSessionId } from '../hooks/useSessionId';
import type { MovieAnalysisResponse, StoryOption } from '../types/api';

export function RewritePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { movieId } = useParams();
  const sessionId = useSessionId();

  const [analysis, setAnalysis] = useState<MovieAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [storySessionId, setStorySessionId] = useState<string | null>(null);
  const [narrative, setNarrative] = useState('');
  const [options, setOptions] = useState<StoryOption[]>([]);
  const [stepNumber, setStepNumber] = useState(1);
  const [typingComplete, setTypingComplete] = useState(false);
  const [runningStep, setRunningStep] = useState(false);
  const [history, setHistory] = useState<Array<{ step: number; narrative: string; choice?: string }>>([]);

  const whatIfId = searchParams.get('whatIf');
  const pickedSuggestion = useMemo(() => {
    if (!analysis) return null;
    if (whatIfId) {
      return analysis.what_if_suggestions.find((item) => item.suggestion_id === whatIfId) ?? null;
    }
    return analysis.what_if_suggestions[0] ?? null;
  }, [analysis, whatIfId]);

  useEffect(() => {
    if (!movieId) return;
    let active = true;
    setLoading(true);
    setError(null);

    api
      .getMovieAnalysis(movieId)
      .then((data) => {
        if (!active) return;
        setAnalysis(data);
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load movie context');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [movieId]);

  useEffect(() => {
    if (!analysis || !movieId || storySessionId) return;
    if (!pickedSuggestion && !location.state) {
      setError('No what-if selected. Go back and choose one from analysis.');
      return;
    }

    const customWhatIf =
      typeof location.state === 'object' && location.state && 'customWhatIf' in location.state
        ? (location.state as { customWhatIf?: string }).customWhatIf
        : undefined;

    setRunningStep(true);
    api
      .startStory(movieId, sessionId, pickedSuggestion?.suggestion_id, customWhatIf)
      .then((story) => {
        setStorySessionId(story.story_session_id);
        setNarrative(story.narrative);
        setOptions(story.options);
        setStepNumber(story.step_number);
        setTypingComplete(false);
        setHistory([{ step: story.step_number, narrative: story.narrative }]);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Could not start rewrite story');
      })
      .finally(() => setRunningStep(false));
  }, [analysis, movieId, pickedSuggestion, sessionId, storySessionId, location.state]);

  async function chooseOption(option: StoryOption) {
    if (!storySessionId || !movieId || runningStep) return;
    setRunningStep(true);
    setTypingComplete(false);

    try {
      const response = await api.storyStep(storySessionId, sessionId, option.option_id);
      let updatedHistory: Array<{ step: number; narrative: string; choice?: string }> = [];
      setHistory((prev) => {
        const next = [...prev];
        if (next.length) {
          next[next.length - 1] = {
            ...next[next.length - 1],
            choice: option.text,
          };
        }
        next.push({ step: response.step_number, narrative: response.narrative });
        updatedHistory = next;
        return next;
      });

      setNarrative(response.narrative);
      setOptions(response.options);
      setStepNumber(response.step_number);

      if (response.is_complete && response.ending) {
        const score = await api.scoreEnding(storySessionId, response.ending);
        navigate(`/ending/${movieId}`, {
          state: {
            ending: response.ending,
            score,
            storySessionId,
            history: updatedHistory,
            movie: analysis?.movie,
            whatIf: pickedSuggestion?.text,
          },
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to continue story');
    } finally {
      setRunningStep(false);
    }
  }

  if (!movieId) {
    return <p className="error">Movie ID missing.</p>;
  }

  return (
    <div className="story-layout">
      <h1 className="section-title">Rewrite Flow</h1>
      {pickedSuggestion ? <p className="section-subtitle">{pickedSuggestion.text}</p> : null}
      {loading ? <p>Loading rewrite context...</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && storySessionId ? (
        <>
          <div className="story-progress">
            <span>Choice {Math.min(stepNumber, 3)} of 3</span>
            <span>{runningStep ? 'Generating next scene...' : 'Your story is live'}</span>
          </div>

          <TypingNarrative
            key={`${storySessionId}-${stepNumber}-${narrative}`}
            text={narrative}
            speedMs={20}
            onDone={() => setTypingComplete(true)}
          />

          {typingComplete && options.length ? (
            <div className="option-grid">
              {options.map((option) => (
                <button
                  className="option-btn"
                  key={option.option_id}
                  onClick={() => chooseOption(option)}
                  disabled={runningStep}
                >
                  <strong>{option.label}</strong>
                  <p>{option.text}</p>
                </button>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
