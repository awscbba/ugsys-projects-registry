import { useEffect, useRef } from 'react';

interface UseFocusManagementReturn {
  modalRef: React.RefObject<HTMLElement | null>;
}

/**
 * Manages focus when a modal/dropdown opens and closes.
 * Implements WCAG 2.1 focus management:
 * - Stores the previously focused element on open
 * - Moves focus into the modal after a brief render delay
 * - Restores focus to the trigger element on close
 * - SSR-safe, memory-leak-free
 */
export function useFocusManagement(isOpen: boolean): UseFocusManagementReturn {
  const modalRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof document === 'undefined') return;

    if (isOpen) {
      previousFocusRef.current = document.activeElement as HTMLElement;

      const timeoutId = setTimeout(() => {
        modalRef.current?.focus();
      }, 100);

      return () => clearTimeout(timeoutId);
    } else {
      if (previousFocusRef.current && document.body.contains(previousFocusRef.current)) {
        previousFocusRef.current.focus();
      }
      previousFocusRef.current = null;
    }
  }, [isOpen]);

  return { modalRef };
}
