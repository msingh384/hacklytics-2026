import { useEffect, useRef, useState } from 'react';

type Props = {
  text: string;
  speedMs?: number;
  onDone?: () => void;
};

export function TypingNarrative({ text, speedMs = 18, onDone }: Props) {
  const [visible, setVisible] = useState('');
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    setVisible('');
    let active = true;
    let cursor = 0;

    const timer = setInterval(() => {
      if (!active) return;
      cursor += 1;
      setVisible(text.slice(0, cursor));
      if (cursor >= text.length) {
        clearInterval(timer);
        onDoneRef.current?.();
      }
    }, speedMs);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [text, speedMs]);

  return (
    <div className="typing-panel">
      <p>
        {visible}
        <span className="typing-cursor" aria-hidden>
          |
        </span>
      </p>
    </div>
  );
}
