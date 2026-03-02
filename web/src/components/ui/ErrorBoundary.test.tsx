/**
 * Bug condition exploration tests — Task 1
 *
 * These tests encode the EXPECTED behavior after the fix.
 * They MUST FAIL on unfixed code — failure confirms the bug exists.
 * They MUST PASS after the fix is applied (Task 3.4 verification).
 *
 * Bug condition C(X):
 *   (a) X.hasErrorBoundaryAroundRouter = false AND X.componentThrowsDuringRender = true
 *   (b) X.accessToken = null AND X.refreshToken = null AND X.apiReturns401 = true
 *
 * Cases covered here: (a) render crash with no boundary, (c) null root element
 * Case (b) is covered in httpClient.test.ts
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

// ── Case 1: Render crash with no ErrorBoundary ────────────────────────────────
// On UNFIXED code: React propagates the throw to the root, #root is emptied → FAILS
// On FIXED code:   ErrorBoundary catches it, fallback UI is shown → PASSES

describe('Bug condition (a): render crash with no ErrorBoundary', () => {
  // Suppress React's console.error noise for expected throws in tests
  let consoleError: typeof console.error;
  beforeEach(() => {
    consoleError = console.error;
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = consoleError;
  });

  it('shows fallback UI instead of blank page when a child component throws', () => {
    // Arrange — a component that throws synchronously during render
    function ThrowingChild(): React.ReactElement {
      throw new Error('Simulated render crash');
    }

    // Act
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );

    // Assert — fallback UI must be visible, page must not be blank
    expect(screen.getByText(/algo salió mal/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reintentar/i })).toBeInTheDocument();
  });

  it('renders children normally when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Normal content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Normal content')).toBeInTheDocument();
    expect(screen.queryByText(/algo salió mal/i)).not.toBeInTheDocument();
  });
});

// ── Case 3: Null root element in main.tsx ─────────────────────────────────────
// On UNFIXED code: ReactDOM.createRoot(null!) throws TypeError → FAILS
// On FIXED code:   console.error is called, no TypeError thrown → PASSES

describe('Bug condition (c): null root element', () => {
  it('logs console.error and does not throw when #root element is missing', async () => {
    // Arrange
    const originalGetElementById = document.getElementById.bind(document);
    const getElementByIdSpy = vi
      .spyOn(document, 'getElementById')
      .mockImplementation((id: string) => {
        if (id === 'root') return null;
        return originalGetElementById(id);
      });
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    // Act — dynamically import main.tsx so the module-level code runs with our mock
    // We use a fresh import each time via cache-busting
    vi.resetModules();
    vi.mock('./App', () => ({ default: () => <div>App</div> }));
    vi.mock('../../stores/authStore', () => ({ initializeAuth: vi.fn() }));

    let threw = false;
    try {
      await import('../../main');
    } catch {
      threw = true;
    }

    // Assert
    expect(threw).toBe(false);
    expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('#root'));

    // Cleanup
    getElementByIdSpy.mockRestore();
    consoleErrorSpy.mockRestore();
  });
});
