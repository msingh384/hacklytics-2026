import { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type ToastType = 'loading' | 'success' | 'error' | 'info';

export type Toast = {
  id: string;
  message: string;
  type: ToastType;
  stage?: string;
  progress?: number;
  duration?: number;
};

type ToastInput = Omit<Toast, 'id'> & { id?: string };

type ToastContextValue = {
  toasts: Toast[];
  addToast: (t: ToastInput) => string;
  removeToast: (id: string) => void;
  updateToast: (id: string, patch: Partial<Toast>) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

function generateId() {
  return `toast-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((input: ToastInput) => {
    const id = input.id ?? generateId();
    const toast: Toast = {
      id,
      message: input.message,
      type: input.type,
      stage: input.stage,
      progress: input.progress,
      duration: input.duration ?? (input.type === 'loading' ? undefined : 4000),
    };
    setToasts((prev) => {
      const next = prev.filter((t) => t.id !== id);
      next.unshift(toast);
      return next;
    });
    if (toast.duration != null && toast.duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, toast.duration);
    }
    return id;
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const updateToast = useCallback((id: string, patch: Partial<Toast>) => {
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ...patch } : t))
    );
  }, []);

  const value = useMemo(
    () => ({ toasts, addToast, removeToast, updateToast }),
    [toasts, addToast, removeToast, updateToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}
