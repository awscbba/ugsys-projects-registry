import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as fc from 'fast-check';
import { usePublicSubscribe } from './usePublicSubscribe';
import type { ISubscriptionApi } from '../services/ports';

// Mock httpClient and authService to prevent module-level side effects
vi.mock('../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../services/authService', () => ({
  authService: { login: vi.fn(), register: vi.fn(), refreshToken: vi.fn() },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeMockApi(overrides: Partial<ISubscriptionApi> = {}): ISubscriptionApi {
  return {
    subscribe: vi.fn(),
    checkSubscription: vi.fn(),
    getMySubscriptions: vi.fn(),
    publicCheckEmail: vi.fn().mockResolvedValue({ exists: false }),
    publicSubscribe: vi.fn().mockResolvedValue({ subscription_id: 'sub-1' }),
    publicRegister: vi.fn(),
    ...overrides,
  };
}

const validData = {
  email: 'test@example.com',
  firstName: 'Ana',
  lastName: 'García',
  notes: '',
};

const PROJECT_ID = 'proj-1';

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('usePublicSubscribe', () => {
  let onSuccess: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    onSuccess = vi.fn();
  });

  it('sets fieldErrors and calls no API when email is empty', async () => {
    const api = makeMockApi();
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, { ...validData, email: '' });
    });

    expect(result.current.fieldErrors['email']).toBeTruthy();
    expect(api.publicCheckEmail).not.toHaveBeenCalled();
    expect(api.publicSubscribe).not.toHaveBeenCalled();
  });

  it('sets fieldErrors and calls no API when firstName is whitespace-only', async () => {
    const api = makeMockApi();
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, { ...validData, firstName: '   ' });
    });

    expect(result.current.fieldErrors['first_name']).toBeTruthy();
    expect(api.publicCheckEmail).not.toHaveBeenCalled();
    expect(api.publicSubscribe).not.toHaveBeenCalled();
  });

  it('sets emailExistsFor and does NOT call publicSubscribe when email exists', async () => {
    const api = makeMockApi({
      publicCheckEmail: vi.fn().mockResolvedValue({ exists: true }),
    });
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, validData);
    });

    expect(result.current.emailExistsFor).toBe(validData.email);
    expect(api.publicSubscribe).not.toHaveBeenCalled();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('calls publicSubscribe and invokes onSuccess on happy path', async () => {
    const api = makeMockApi();
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, validData);
    });

    expect(api.publicSubscribe).toHaveBeenCalledWith({
      email: validData.email,
      first_name: validData.firstName,
      last_name: validData.lastName,
      project_id: PROJECT_ID,
      notes: undefined,
    });
    expect(onSuccess).toHaveBeenCalledWith({ subscription_id: 'sub-1' });
    expect(result.current.apiError).toBeNull();
  });

  it('sets apiError and clears isSubmitting when publicCheckEmail throws', async () => {
    const api = makeMockApi({
      publicCheckEmail: vi.fn().mockRejectedValue(new Error('Network error')),
    });
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, validData);
    });

    expect(result.current.apiError).toBe('Network error');
    expect(result.current.isSubmitting).toBe(false);
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('isSubmitting is false after async operation completes', async () => {
    const api = makeMockApi();
    const { result } = renderHook(() => usePublicSubscribe(onSuccess, api));

    await act(async () => {
      await result.current.submit(PROJECT_ID, validData);
    });

    expect(result.current.isSubmitting).toBe(false);
  });

  // ── Property 3: email-exists guard ─────────────────────────────────────────
  // Feature: web-frontend-quality, Property 3: usePublicSubscribe email-exists guard
  it('Property 3: for any valid form data where publicCheckEmail returns exists=true, publicSubscribe is never called', async () => {
    const nonBlank = fc.string({ minLength: 1 }).filter((s) => s.trim().length > 0);
    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        nonBlank,
        nonBlank,
        async (email, firstName, lastName) => {
          const api = makeMockApi({
            publicCheckEmail: vi.fn().mockResolvedValue({ exists: true }),
          });
          const successFn = vi.fn();
          const { result } = renderHook(() => usePublicSubscribe(successFn, api));

          await act(async () => {
            await result.current.submit(PROJECT_ID, { email, firstName, lastName, notes: '' });
          });

          expect(result.current.emailExistsFor).toBe(email.trim());
          expect(api.publicSubscribe).not.toHaveBeenCalled();
        }
      ),
      { numRuns: 50 }
    );
  });

  // ── Property 4: happy path ──────────────────────────────────────────────────
  // Feature: web-frontend-quality, Property 4: usePublicSubscribe happy path
  it('Property 4: for any valid form data where email does not exist, publicSubscribe is called and onSuccess invoked', async () => {
    const nonBlank = fc.string({ minLength: 1 }).filter((s) => s.trim().length > 0);
    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        nonBlank,
        nonBlank,
        async (email, firstName, lastName) => {
          const subId = 'sub-prop';
          const api = makeMockApi({
            publicCheckEmail: vi.fn().mockResolvedValue({ exists: false }),
            publicSubscribe: vi.fn().mockResolvedValue({ subscription_id: subId }),
          });
          const successFn = vi.fn();
          const { result } = renderHook(() => usePublicSubscribe(successFn, api));

          await act(async () => {
            await result.current.submit(PROJECT_ID, { email, firstName, lastName, notes: '' });
          });

          expect(api.publicSubscribe).toHaveBeenCalledWith(
            expect.objectContaining({
              email: email.trim(),
              first_name: firstName.trim(),
              last_name: lastName.trim(),
              project_id: PROJECT_ID,
            })
          );
          expect(successFn).toHaveBeenCalledWith({ subscription_id: subId });
        }
      ),
      { numRuns: 50 }
    );
  });

  // ── Property 5: field validation guard ─────────────────────────────────────
  // Feature: web-frontend-quality, Property 5: usePublicSubscribe field validation guard
  it('Property 5: for any form data with at least one empty/whitespace required field, no API is called', async () => {
    // Generate data where at least one required field is blank
    const blankField = fc.constantFrom('email', 'firstName', 'lastName');
    await fc.assert(
      fc.asyncProperty(
        fc.record({
          email: fc.string(),
          firstName: fc.string(),
          lastName: fc.string(),
        }),
        blankField,
        async (data, fieldToClear) => {
          const invalidData = { ...data, notes: '', [fieldToClear]: '   ' };
          const api = makeMockApi();
          const successFn = vi.fn();
          const { result } = renderHook(() => usePublicSubscribe(successFn, api));

          await act(async () => {
            await result.current.submit(PROJECT_ID, invalidData);
          });

          expect(Object.keys(result.current.fieldErrors).length).toBeGreaterThan(0);
          expect(api.publicCheckEmail).not.toHaveBeenCalled();
          expect(api.publicSubscribe).not.toHaveBeenCalled();
        }
      ),
      { numRuns: 50 }
    );
  });
});
