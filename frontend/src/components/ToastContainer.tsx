import { useToast } from '../contexts/ToastContext';

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`toast toast--${toast.type}`}
          role={toast.type === 'loading' ? 'status' : 'alert'}
        >
          {toast.type === 'loading' && (
            <span className="toast-spinner" aria-hidden />
          )}
          <div className="toast-body">
            <p className="toast-message">{toast.message}</p>
            {toast.type === 'loading' && (toast.stage ?? toast.progress != null) && (
              <p className="toast-stage">
                {toast.stage?.replaceAll('_', ' ') ?? `${toast.progress}%`}
              </p>
            )}
          </div>
          {toast.type !== 'loading' && (
            <button
              type="button"
              className="toast-dismiss"
              aria-label="Dismiss"
              onClick={() => removeToast(toast.id)}
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
