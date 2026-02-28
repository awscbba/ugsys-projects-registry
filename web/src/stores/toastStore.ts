import { atom } from "nanostores";

export interface Toast {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
}

export const $toasts = atom<Toast[]>([]);

export function addToast(
  type: Toast["type"],
  message: string,
  durationMs = 5000,
): void {
  const id = crypto.randomUUID();
  $toasts.set([...$toasts.get(), { id, type, message }]);
  setTimeout(() => removeToast(id), durationMs);
}

export function removeToast(id: string): void {
  $toasts.set($toasts.get().filter((t) => t.id !== id));
}
