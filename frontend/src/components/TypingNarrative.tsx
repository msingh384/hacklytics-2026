import { useEffect, useState } from 'react';

type Props = {
  text: string;
  speedMs?: number;
  onDone?: () => void;
};

export function TypingNarrative({ text, speedMs = 18, onDone }: Props) {
  const [visible, setVisible] = useState('');

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
        onDone?.();
      }
    }, speedMs);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [text, speedMs, onDone]);

  return (
    <div className="typing-panel">
      <p>{visible}</p>
      <span className="cursor" aria-hidden>
        |
      </span>
    </div>
  );
}
