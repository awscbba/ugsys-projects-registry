import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getErrorMessage, isApiError } from './errorHandling';

const FALLBACK = 'Ha ocurrido un error inesperado';

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('getErrorMessage', () => {
  it('returns error.message for an Error instance', () => {
    expect(getErrorMessage(new Error('msg'))).toBe('msg');
  });

  it('returns message property from plain object', () => {
    expect(getErrorMessage({ message: 'api msg' })).toBe('api msg');
  });

  it('returns fallback string for null', () => {
    expect(getErrorMessage(null)).toBe(FALLBACK);
  });

  it('returns fallback string for undefined', () => {
    expect(getErrorMessage(undefined)).toBe(FALLBACK);
  });

  it('returns fallback string for a number', () => {
    expect(getErrorMessage(42)).toBe(FALLBACK);
  });
});

describe('isApiError', () => {
  it('returns true for object with error property', () => {
    expect(isApiError({ error: 'NOT_FOUND' })).toBe(true);
  });

  it('returns true when error code matches', () => {
    expect(isApiError({ error: 'NOT_FOUND' }, 'NOT_FOUND')).toBe(true);
  });

  it('returns false when error code does not match', () => {
    expect(isApiError({ error: 'NOT_FOUND' }, 'CONFLICT')).toBe(false);
  });

  it('returns false for null', () => {
    expect(isApiError(null)).toBe(false);
  });

  it('returns false for object without error property', () => {
    expect(isApiError({ message: 'oops' })).toBe(false);
  });
});

// ── Property 9: getErrorMessage extraction ────────────────────────────────────
// Feature: web-frontend-quality, Property 9: getErrorMessage extraction
describe('Property 9: getErrorMessage extraction', () => {
  it('returns e.message for any Error instance', () => {
    fc.assert(
      fc.property(fc.string(), (msg) => {
        expect(getErrorMessage(new Error(msg))).toBe(msg);
      }),
      { numRuns: 100 }
    );
  });

  it('returns fallback for any non-Error value without a message property', () => {
    // Primitives and null/undefined have no message property
    const primitives = fc.oneof(
      fc.integer(),
      fc.float(),
      fc.boolean(),
      fc.constant(null),
      fc.constant(undefined)
    );
    fc.assert(
      fc.property(primitives, (value) => {
        expect(getErrorMessage(value)).toBe(FALLBACK);
      }),
      { numRuns: 100 }
    );
  });
});
