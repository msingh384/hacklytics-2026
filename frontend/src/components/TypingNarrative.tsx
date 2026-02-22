import { useCallback, useEffect, useRef, useState } from 'react';

type Props = {
  text: string;
  speedMs?: number;
  onDone?: () => void;
};

export function TypingNarrative({ text, speedMs = 18, onDone }: Props) {
  const [visible, setVisible] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const onDoneRef = useRef(onDone);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  onDoneRef.current = onDone;

  const skip = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setVisible(text);
    setIsComplete(true);
    onDoneRef.current?.();
  }, [text]);

  useEffect(() => {
    setVisible('');
    setIsComplete(false);
    let active = true;
    let cursor = 0;

    timerRef.current = setInterval(() => {
      if (!active) return;
      cursor += 1;
      setVisible(text.slice(0, cursor));
      if (cursor >= text.length) {
        if (timerRef.current) {
          clearInterval(timerRef.current);
          timerRef.current = null;
        }
        setIsComplete(true);
        onDoneRef.current?.();
      }
    }, speedMs);

    return () => {
      active = false;
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [text, speedMs]);

  return (
    <div className="typing-panel">
      <div className="typing-panel-content">
        <p>
          {visible}
          {!isComplete && (
            <span className="typing-cursor" aria-hidden>
              |
            </span>
          )}
        </p>
        {!isComplete && (
          <button
            type="button"
            className="typing-skip-btn"
            onClick={skip}
          >
            Skip
          </button>
        )}
      </div>
    </div>
  );
}
