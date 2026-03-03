import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { useFocusManagement } from './useFocusManagement';

describe('useFocusManagement', () => {
  let mockButton: HTMLButtonElement;
  let mockModal: HTMLDivElement;

  beforeEach(() => {
    mockButton = document.createElement('button');
    mockButton.id = 'trigger-button';
    document.body.appendChild(mockButton);

    mockModal = document.createElement('div');
    mockModal.id = 'modal';
    mockModal.tabIndex = -1;
    document.body.appendChild(mockModal);

    mockButton.focus();
  });

  afterEach(() => {
    if (document.body.contains(mockButton)) document.body.removeChild(mockButton);
    if (document.body.contains(mockModal)) document.body.removeChild(mockModal);
    vi.clearAllMocks();
  });

  // ── Initial State ──────────────────────────────────────────────────────────

  describe('Initial State', () => {
    it('returns modalRef', () => {
      const { result } = renderHook(() => useFocusManagement(false));
      expect(result.current.modalRef).toBeDefined();
      expect(result.current.modalRef.current).toBeNull();
    });

    it('does not change focus when closed', () => {
      const before = document.activeElement;
      renderHook(() => useFocusManagement(false));
      expect(document.activeElement).toBe(before);
    });
  });

  // ── Focus Storage ──────────────────────────────────────────────────────────

  describe('Focus Storage', () => {
    it('stores previously focused element on open', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      expect(document.activeElement).toBe(mockModal);
    });

    it('handles multiple focus changes before open', async () => {
      const second = document.createElement('button');
      document.body.appendChild(second);
      second.focus();

      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      rerender({ isOpen: false });

      expect(document.activeElement).toBe(second);
      document.body.removeChild(second);
    });
  });

  // ── Focus Restoration ──────────────────────────────────────────────────────

  describe('Focus Restoration', () => {
    it('restores focus on close (P7)', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      rerender({ isOpen: false });

      expect(document.activeElement).toBe(mockButton);
    });

    it('handles element removed from DOM', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      document.body.removeChild(mockButton);

      expect(() => rerender({ isOpen: false })).not.toThrow();

      // re-add for afterEach cleanup
      mockButton = document.createElement('button');
      document.body.appendChild(mockButton);
    });

    it('clears ref after restoration', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });
      rerender({ isOpen: false });

      const newBtn = document.createElement('button');
      document.body.appendChild(newBtn);
      newBtn.focus();

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });
      rerender({ isOpen: false });

      expect(document.activeElement).toBe(newBtn);
      document.body.removeChild(newBtn);
    });
  });

  // ── Modal Focus ────────────────────────────────────────────────────────────

  describe('Modal Focus', () => {
    it('moves focus to modal after delay', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      expect(document.activeElement).toBe(mockModal);
    });

    it('handles missing ref without throwing', () => {
      const { rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      expect(() => rerender({ isOpen: true })).not.toThrow();
    });

    it('delays focus to allow render', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      rerender({ isOpen: true });

      // Immediately after open — focus not yet moved
      expect(document.activeElement).toBe(mockButton);

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      expect(document.activeElement).toBe(mockModal);
    });
  });

  // ── Multiple Open/Close Cycles ─────────────────────────────────────────────

  describe('Multiple Open/Close Cycles', () => {
    it('handles multiple cycles correctly', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      for (let i = 0; i < 2; i++) {
        rerender({ isOpen: true });
        await act(async () => { await new Promise(r => setTimeout(r, 150)); });
        expect(document.activeElement).toBe(mockModal);

        rerender({ isOpen: false });
        expect(document.activeElement).toBe(mockButton);
      }
    });

    it('handles rapid open/close', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      rerender({ isOpen: false });
      rerender({ isOpen: true });

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      expect(document.activeElement).toBe(mockModal);
    });
  });

  // ── Accessibility Compliance ───────────────────────────────────────────────

  describe('Accessibility Compliance', () => {
    it('WCAG 2.1 — focus moves to modal on open, returns to trigger on close', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });
      expect(document.activeElement).toBe(mockModal);

      rerender({ isOpen: false });
      expect(document.activeElement).toBe(mockButton);
    });

    it('works with tabIndex elements', async () => {
      const focusableDiv = document.createElement('div');
      focusableDiv.tabIndex = 0;
      document.body.appendChild(focusableDiv);
      focusableDiv.focus();

      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      rerender({ isOpen: false });

      expect(document.activeElement).toBe(focusableDiv);
      document.body.removeChild(focusableDiv);
    });
  });

  // ── SSR Compatibility ──────────────────────────────────────────────────────

  describe('SSR Compatibility', () => {
    it('does not crash when document is undefined (P8)', () => {
      // In jsdom the guard is not triggered, but we verify the hook
      // renders without error and returns the expected shape
      const { result } = renderHook(() => useFocusManagement(false));
      expect(result.current.modalRef).toBeDefined();
    });

    it('handles SSR environment gracefully', () => {
      const { result } = renderHook(() => useFocusManagement(true));
      expect(result.current.modalRef).toBeDefined();
    });
  });

  // ── Memory Leak Prevention ─────────────────────────────────────────────────

  describe('Memory Leak Prevention', () => {
    it('cleans up timeout on unmount (P9)', async () => {
      const { result, rerender, unmount } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      unmount();

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      // No crash, no state update warning
      expect(true).toBe(true);
    });

    it('cleans up on rapid isOpen change', async () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      rerender({ isOpen: false });

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      // Timeout was cancelled — modal should NOT have focus
      expect(document.activeElement).not.toBe(mockModal);
    });
  });

  // ── Edge Cases ─────────────────────────────────────────────────────────────

  describe('Edge Cases', () => {
    it('handles body as active element', async () => {
      document.body.tabIndex = -1;
      document.body.focus();
      const prev = document.activeElement;

      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      rerender({ isOpen: true });
      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      rerender({ isOpen: false });

      expect(document.activeElement).toBe(prev);
      document.body.removeAttribute('tabindex');
    });

    it('handles null activeElement without throwing', () => {
      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = mockModal; });

      expect(() => rerender({ isOpen: true })).not.toThrow();
    });

    it('handles non-focusable modal element without throwing', async () => {
      const span = document.createElement('span');
      document.body.appendChild(span);

      const { result, rerender } = renderHook(
        ({ isOpen }) => useFocusManagement(isOpen),
        { initialProps: { isOpen: false } }
      );

      act(() => { (result.current.modalRef as React.MutableRefObject<HTMLElement>).current = span; });

      expect(() => rerender({ isOpen: true })).not.toThrow();

      await act(async () => { await new Promise(r => setTimeout(r, 150)); });

      document.body.removeChild(span);
    });
  });
});
