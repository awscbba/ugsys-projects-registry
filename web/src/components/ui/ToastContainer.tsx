import type React from "react";
import { useStore } from "@nanostores/react";
import { $toasts, removeToast, type Toast } from "@/stores/toastStore";

const toastConfig: Record<
  Toast["type"],
  { border: string; bg: string; text: string; icon: React.ReactElement }
> = {
  success: {
    border: "border-l-4 border-green-500",
    bg: "bg-green-50",
    text: "text-green-800",
    icon: (
      <svg className="h-5 w-5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
  },
  error: {
    border: "border-l-4 border-red-500",
    bg: "bg-red-50",
    text: "text-red-800",
    icon: (
      <svg className="h-5 w-5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  },
  warning: {
    border: "border-l-4 border-yellow-500",
    bg: "bg-yellow-50",
    text: "text-yellow-800",
    icon: (
      <svg className="h-5 w-5 text-yellow-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
    ),
  },
  info: {
    border: "border-l-4 border-blue-500",
    bg: "bg-blue-50",
    text: "text-blue-800",
    icon: (
      <svg className="h-5 w-5 text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
};

function ToastCard({ toast }: { toast: Toast }) {
  const config = toastConfig[toast.type];

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={[
        "flex items-start gap-3 rounded-md px-4 py-3 shadow-md",
        config.border,
        config.bg,
        config.text,
        "min-w-64 max-w-sm",
      ].join(" ")}
    >
      {config.icon}
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        type="button"
        onClick={() => removeToast(toast.id)}
        aria-label="Cerrar notificación"
        className="ml-1 shrink-0 rounded p-0.5 opacity-60 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useStore($toasts);

  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notificaciones"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    >
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
