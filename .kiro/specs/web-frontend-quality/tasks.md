# Implementation Plan: web-frontend-quality

## Overview

Establish frontend quality infrastructure for `ugsys-projects-registry/web/` (React 19, TypeScript strict, Vite 6). Tasks follow a dependency-ordered sequence: tooling → token security → service ports → hooks → components → tests → logger → git hooks → CI → deploy.

## Tasks

- [x] 1. Install devDependencies and configure tooling
  - Add to `web/package.json` devDependencies: `vitest`, `@vitest/coverage-v8`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `fast-check`, `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `eslint-plugin-react`, `prettier`, `eslint-config-prettier`
  - Add scripts to `web/package.json`: `"test:run": "vitest run"`, `"test:watch": "vitest"`, `"test:coverage": "vitest run --coverage"`, `"format": "prettier --write src/"`, `"format:check": "prettier --check src/"`
  - Add `test` block to `web/vite.config.ts`: `environment: 'jsdom'`, `globals: true`, `setupFiles: ['./src/test/setup.ts']`, coverage thresholds at 80% for lines/functions/branches/statements using `provider: 'v8'`
  - Create `web/src/test/setup.ts` importing `@testing-library/jest-dom`
  - Create `web/.prettierrc` with `printWidth: 100`, `singleQuote: true`, `trailingComma: "es5"`, `semi: true`
  - Update `web/eslint.config.js` to enable `eslint-plugin-react-hooks` (`rules-of-hooks: error`, `exhaustive-deps: warn`), `eslint-plugin-jsx-a11y` (recommended), `eslint-plugin-react` (`jsx-key: error`, `jsx-no-duplicate-props: error`, `no-unescaped-entities: warn`), and `eslint-config-prettier`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 2. Token security hardening
  - Modify `web/src/stores/authStore.ts`: remove all `localStorage.setItem` / `localStorage.getItem` calls for `access_token` and `refresh_token`; add module-level `let _accessToken: string | null = null` and `let _refreshToken: string | null = null`; export `getAccessToken()` and `getRefreshToken()` getter functions; update `login()` to set in-memory vars; update `logout()` to clear in-memory vars and call `/api/v1/auth/logout`
  - Modify `web/src/services/httpClient.ts`: remove any local `getAccessToken`/`getRefreshToken` functions that read from `localStorage`; import `getAccessToken, getRefreshToken` from `../stores/authStore`; update the 401 refresh flow to write back to in-memory vars via authStore setters (not localStorage)
  - _Requirements: 7.5, 7.6, 7.7_

- [x] 3. Define service port interfaces
  - Create `web/src/services/ports.ts` with `IProjectApi` interface declaring `getPublicProjects`, `getProject`, `getProjectEnhanced` with their exact signatures
  - Add `ISubscriptionApi` interface to `web/src/services/ports.ts` declaring `subscribe`, `checkSubscription`, `getMySubscriptions`, `publicCheckEmail`, `publicSubscribe`, `publicRegister` with their exact signatures
  - _Requirements: 4.1, 4.2_

- [x] 4. Implement useProjectDetail hook
  - Create `web/src/hooks/useProjectDetail.ts` accepting `projectId: string | undefined` and optional `api: IProjectApi` (defaulting to `projectApi`)
  - On mount and when `projectId` changes, call `api.getProjectEnhanced(projectId)` with a `cancelled` flag to prevent state updates after unmount
  - Return `{ project: EnhancedProject | null, isLoading: boolean, error: string | null }`
  - Export `EnhancedProject` type alias (`Project & { form_schema?: FormSchema }`)
  - _Requirements: 4.4, 4.5, 4.13_

- [x] 5. Update useProjects hook with injected API
  - Modify `web/src/hooks/useProjects.ts` to accept an optional third parameter `api: IProjectApi` defaulting to the `projectApi` concrete module
  - Ensure return shape is `{ projects: Project[], total: number, isLoading: boolean, error: string | null }`
  - _Requirements: 4.3, 4.13_

- [x] 6. Implement usePublicSubscribe hook
  - Create `web/src/hooks/usePublicSubscribe.ts` accepting `onSuccess` callback and optional `api: ISubscriptionApi` (defaulting to `subscriptionApi`)
  - Implement `submit(projectId, data)`: validate required fields (`email`, `firstName`, `lastName`) first — if any are empty/whitespace, set `fieldErrors` and return without calling any API
  - If validation passes, call `api.publicCheckEmail(email)`: if `exists === true`, set `emailExistsFor` to the email and do NOT call `publicSubscribe`; if `exists === false`, call `api.publicSubscribe(...)` then invoke `onSuccess`
  - Set `isSubmitting: true` during async operations, clear in `finally`; set `apiError` on any caught exception
  - Return `{ submit, isSubmitting, apiError, fieldErrors, emailExistsFor }`
  - _Requirements: 4.6, 4.7, 4.8, 4.9, 4.10_

- [x] 7. Refactor SubscribePage and extract PublicSubscribeForm
  - Create `web/src/components/subscriptions/PublicSubscribeForm.tsx` extracted from `SubscribePage.tsx`; it receives `UsePublicSubscribeResult & { projectId: string }` as props and contains only rendering logic — no state, no API calls
  - Refactor `web/src/pages/SubscribePage.tsx` to use `useProjectDetail(projectId)` for project fetching and `usePublicSubscribe(handleSuccess)` for the subscription flow; pass the hook result to `<PublicSubscribeForm>`; remove all inline API calls and form-submission logic
  - _Requirements: 4.11, 4.12_

- [x] 8. Checkpoint — verify build and types pass
  - Ensure `npm run typecheck` and `npm run build` pass inside `web/` with no errors; ask the user if questions arise.

- [x] 9. Add ErrorTracker interface and configureLogger to logger
  - Modify `web/src/utils/logger.ts`: add `ErrorTracker` interface with `captureError(message: string, data?: unknown): void`; add module-level `let _tracker: ErrorTracker = noopTracker` (no-op default); add exported `configureLogger(tracker: ErrorTracker): void` function; update `logger.error` to call `_tracker.captureError(message, data)` when environment is non-development
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 10. Write unit and property-based tests
  - [x] 10.1 Write tests for usePublicSubscribe
    - Test: empty required field → `fieldErrors` set, no API called
    - Test: whitespace-only `firstName` → `fieldErrors` set, no API called
    - Test: `publicCheckEmail` returns `exists: true` → `emailExistsFor` set, `publicSubscribe` not called
    - Test: happy path → `publicSubscribe` called, `onSuccess` invoked
    - Test: `publicCheckEmail` throws → `apiError` set, `isSubmitting` false
    - _Requirements: 5.5_

  - [ ]* 10.2 Write property tests for usePublicSubscribe
    - **Property 3: usePublicSubscribe email-exists guard** — for any valid form data where `publicCheckEmail` returns `exists: true`, `submit` sets `emailExistsFor` and never calls `publicSubscribe`
    - **Property 4: usePublicSubscribe happy path** — for any valid form data where `publicCheckEmail` returns `exists: false` and `publicSubscribe` resolves, `submit` calls `publicSubscribe` with correct payload and invokes `onSuccess`
    - **Property 5: usePublicSubscribe field validation guard** — for any form data with at least one empty/whitespace required field, `submit` sets non-empty `fieldErrors` and calls neither API method
    - Tag format: `// Feature: web-frontend-quality, Property N: <text>`
    - **Validates: Requirements 4.8, 4.9, 4.10**

  - [x] 10.3 Write tests for useProjectDetail
    - Test: `isLoading` is `true` during fetch, `false` after
    - Test: resolved project returned on success with `error: null`
    - Test: `error` string set on API failure, `project` is `null`
    - Test: no state update after unmount (cancelled flag)
    - _Requirements: 5.6_

  - [ ]* 10.4 Write property test for useProjectDetail
    - **Property 2: useProjectDetail data flow** — for any `projectId` and mock `IProjectApi`, `getProjectEnhanced(projectId)` is called and the resolved project is returned with `isLoading: false` and `error: null` on success
    - Tag format: `// Feature: web-frontend-quality, Property 2: <text>`
    - **Validates: Requirements 4.4, 4.5**

  - [x] 10.5 Write tests for useProjects
    - Test: loading state transitions (true → false)
    - Test: `projects` and `total` set from paginated response on success
    - Test: `error` string set on API failure
    - Test: injected mock `api` is called with correct `page` and `pageSize`
    - _Requirements: 5.7_

  - [ ]* 10.6 Write property test for useProjects
    - **Property 1: useProjects uses injected API** — for any mock `IProjectApi`, `useProjects` calls `api.getPublicProjects` with the given page and pageSize
    - Tag format: `// Feature: web-frontend-quality, Property 1: <text>`
    - **Validates: Requirements 4.3**

  - [x] 10.7 Write unit and property tests for sanitize utils
    - Unit: `escapeHtml('<script>')` → `'&lt;script&gt;'`
    - Unit: `escapeHtml('a & b')` → `'a &amp; b'`
    - Unit: `stripHtml('<p>hello</p>')` → `'hello'`
    - Unit: `stripHtml('no tags')` → `'no tags'`
    - _Requirements: 5.8_

  - [ ]* 10.8 Write property tests for sanitize utils
    - **Property 6: escapeHtml character escaping** — for any string containing `<`, `>`, `&`, `"`, `'`, `escapeHtml` replaces each with its HTML entity
    - **Property 7: escapeHtml idempotence** — for any string `s`, `escapeHtml(escapeHtml(s)) === escapeHtml(s)`
    - **Property 8: stripHtml tag removal** — for any string, result contains no substrings matching `/<[^>]*>/`
    - Use `fc.string()` with `numRuns: 100`; tag format: `// Feature: web-frontend-quality, Property N: <text>`
    - **Validates: Requirements 5.8a, 5.8b, 5.8c**

  - [x] 10.9 Write tests for errorHandling utils
    - Test: `getErrorMessage(new Error('msg'))` → `'msg'`
    - Test: `getErrorMessage({ message: 'api msg' })` → `'api msg'`
    - Test: `getErrorMessage(null)` → fallback string `"Ha ocurrido un error inesperado"`
    - Test: `isApiError({ error: 'NOT_FOUND' })` → `true`
    - Test: `isApiError({ error: 'NOT_FOUND' }, 'NOT_FOUND')` → `true`
    - Test: `isApiError({ error: 'NOT_FOUND' }, 'CONFLICT')` → `false`
    - Test: `isApiError(null)` → `false`
    - _Requirements: 5.9_

  - [ ]* 10.10 Write property test for getErrorMessage
    - **Property 9: getErrorMessage extraction** — for any `Error` instance `e`, `getErrorMessage(e)` returns `e.message`; for any non-Error value without a `message` property, returns the fallback string
    - Tag format: `// Feature: web-frontend-quality, Property 9: <text>`
    - **Validates: Requirements 5.9**

  - [x] 10.11 Write tests for logger
    - Test: `configureLogger` + `logger.error` in non-dev → `captureError` called exactly once
    - Test: `logger.error` without `configureLogger` → does not throw
    - Test: `logger.error` in dev environment → `captureError` NOT called
    - _Requirements: 5.8 (logger), 7.8_

  - [ ]* 10.12 Write property test for logger error forwarding
    - **Property 10: logger error forwarding in non-dev environment** — for any error message string and optional data, when a non-noop `ErrorTracker` is configured and environment is non-development, `logger.error(message, data)` invokes `tracker.captureError(message, data)` exactly once
    - Tag format: `// Feature: web-frontend-quality, Property 10: <text>`
    - **Validates: Requirements 7.2**

  - [ ]* 10.13 Write property tests for token security
    - **Property 11: tokens not persisted to localStorage after login** — for any successful `login(email, password)` call, `localStorage.getItem('access_token')` and `localStorage.getItem('refresh_token')` both return `null`
    - **Property 12: logout clears in-memory token** — for any authenticated state where `getAccessToken()` returns non-null, calling `logout()` results in `getAccessToken()` returning `null`
    - Tag format: `// Feature: web-frontend-quality, Property N: <text>`
    - **Validates: Requirements 7.5, 7.7**

- [x] 11. Checkpoint — ensure all tests pass and coverage gate is met
  - Run `npm run test:coverage` inside `web/`; confirm all thresholds (lines/functions/branches/statements) are ≥ 80%; ask the user if questions arise.

- [x] 12. Update git pre-commit hook and justfile
  - Modify `scripts/hooks/pre-commit` (extend, do not replace): add staged-file detection for `web/` paths; if any staged file is under `web/`, run in sequence inside `web/`: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test:run`, `npm audit --audit-level=high`; exit non-zero on any failure; skip all web checks if no staged files are under `web/`
  - Add `web-test` recipe to `justfile`: runs `npm run test:run` inside `web/`
  - Add `web-audit` recipe to `justfile`: runs `npm audit --audit-level=high` inside `web/`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

- [x] 13. Create frontend CI pipeline workflow
  - Create `.github/workflows/ci-frontend.yml` triggered on push to `feature/**` and PR to `main` with path filter `web/**`
  - Include jobs: `lint` (`npm run lint`), `format` (`npm run format:check`), `typecheck` (`npm run typecheck`), `test` (`npm run test:coverage`, upload artifact `frontend-coverage`, fail if coverage < 80%), `build` (`npm run build`), `dependency-audit` (`npm audit --audit-level=high`), `secret-scan` (Gitleaks with `fetch-depth: 0`)
  - All jobs run inside `web/` working directory; all block merge on failure
  - Add `notify-failure` job: on any job failure, send Slack notification to channel `C0AE6QV0URH` using `SLACK_BOT_TOKEN` secret with username `ugsys CI/CD`
  - Note: this modifies `.github/workflows/` — explain the change per ai-guidelines.md before committing
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11_

- [x] 14. Create Amplify deploy workflow and amplify.yml
  - Create `web/amplify.yml` using static SPA pattern: `baseDirectory: dist`, `artifacts.files: ['**/*']`, build command `npm run build` — NOT the SSR pattern
  - Create `.github/workflows/deploy-frontend.yml` triggered on push to `main` with path filter `web/**`; require `environment: prod` approval gate; authenticate with AWS via OIDC (`aws-actions/configure-aws-credentials`, `role-to-assume: ${{ secrets.AWS_ROLE_ARN }}`); build with `npm run build` passing `VITE_API_BASE_URL` and `VITE_AUTH_API_URL` from secrets; upload `web/dist/` and call Amplify StartDeployment API using `AMPLIFY_APP_ID` secret for branch `main`; send Slack success notification with commit SHA on success; send Slack failure notification with workflow run link on failure
  - Note: this modifies `.github/workflows/` — explain the change per ai-guidelines.md before committing
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

- [x] 15. Final checkpoint — ensure all tests pass
  - Run `npm run test:coverage` and `npm run build` inside `web/`; confirm everything is green; ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use `fast-check` with tag format: `// Feature: web-frontend-quality, Property N: <text>`
- The pre-commit hook update extends the existing hook — do not replace it
- The amplify.yml uses the static SPA pattern (`dist/` baseDirectory) — not SSR
- Token security: authStore does NOT import httpClient for getter functions (no circular dependency)
