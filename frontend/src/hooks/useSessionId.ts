import { useMemo } from 'react';

const KEY = 'directorscut-session-id';

function createSessionId() {
  return `sess-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

export function useSessionId() {
  return useMemo(() => {
    const existing = window.localStorage.getItem(KEY);
    if (existing) return existing;
    const next = createSessionId();
    window.localStorage.setItem(KEY, next);
    return next;
  }, []);
}
