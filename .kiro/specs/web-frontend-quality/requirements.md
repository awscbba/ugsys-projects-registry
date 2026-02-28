# Requirements Document

## Introduction

This feature establishes frontend quality infrastructure for the `ugsys-projects-registry` web application (`web/`). The scope covers seven areas: (1) git pre-commit hooks that enforce quality gates for the `web/` directory, (2) CI pipeline jobs for lint, format, typecheck, unit tests, and security scanning, (3) a deploy workflow targeting AWS Amplify, (4) an architecture refactor that extracts orchestration logic from `SubscribePage` into hooks and introduces port/interface abstractions for services, (5) a unit test suite using vitest and `@testing-library/react` with an 80% coverage gate, (6) ESLint and Prettier configuration improvements, and (7) logger error forwarding and token security hardening.

The existing codebase (React 19, TypeScript strict, Vite 6, Tailwind 4, nanostores, react-router-dom 7) has zero tests, no frontend CI jobs, no git hooks covering `web/`, and several issues: inline form logic in `SubscribePage`, tokens stored in `localStorage`, a logger that silences errors in production, and ESLint missing hooks and accessibility rules.

## Glossary

- **Web_App**: The React SPA located at `ugsys-projects-registry/web/`.
- **Pre_Commit_Hook**: The git pre-commit script at `scripts/hooks/pre-commit` that runs quality checks before each commit.
- **CI_Frontend**: The GitHub Actions workflow `ci-frontend.yml` that runs quality gates on every push to `feature/**` and every PR to `main` when `web/**` files change.
- **Deploy_Frontend**: The GitHub Actions workflow `deploy-frontend.yml` that deploys the Web_App to AWS Amplify on merge to `main`.
- **Hook**: A React custom hook (`use*`) that encapsulates state and side-effect logic.
- **Service_Port**: A TypeScript interface that defines the contract for an API service module, enabling dependency injection and test isolation.
- **Concrete_Service**: A module (e.g., `projectApi`, `subscriptionApi`) that implements a Service_Port by calling `httpClient`.
- **usePublicSubscribe**: The Hook that encapsulates the public subscription flow: email-existence check followed by the public subscribe API call.
- **useProjectDetail**: The Hook that encapsulates fetching a single project by ID via `projectApi.getProjectEnhanced`.
- **useProjects**: The existing Hook that fetches the paginated public project list.
- **Error_Tracker**: An adapter that receives error events from the logger and forwards them to an external error-tracking service (e.g., Sentry) or a no-op stub.
- **Coverage_Gate**: The minimum line/branch/function/statement coverage threshold (80%) enforced in CI and in the vitest configuration.
- **Amplify**: AWS Amplify Hosting, the target deployment platform for the Web_App (static SPA deploy — `dist/` as baseDirectory, same pattern as `devsecops-poc/web`).
- **OIDC**: OpenID Connect — the mechanism used for keyless AWS authentication in CI/CD workflows.
- **Prettier**: Code formatter enforced in CI and pre-commit to ensure consistent style across the codebase.
- **eslint-plugin-react-hooks**: ESLint plugin that enforces the Rules of Hooks (`rules-of-hooks: error`, `exhaustive-deps: warn`).

---

## Requirements

### Requirement 1: Git Pre-Commit Hook for Web

**User Story:** As a developer, I want the pre-commit hook to enforce frontend quality gates, so that lint errors, type errors, formatting issues, failing tests, and vulnerable dependencies are caught before they reach the remote branch.

#### Acceptance Criteria

1. WHEN a developer runs `just install-hooks`, THE Pre_Commit_Hook SHALL be installed to `.git/hooks/pre-commit` and be executable.
2. WHEN a commit is attempted on branch `main`, THE Pre_Commit_Hook SHALL exit with a non-zero code and print a message preventing the commit.
3. WHEN staged files include any path under `web/`, THE Pre_Commit_Hook SHALL run `npm run lint` inside `web/` and exit with a non-zero code if ESLint reports any error.
4. WHEN staged files include any path under `web/`, THE Pre_Commit_Hook SHALL run `npm run format:check` inside `web/` and exit with a non-zero code if any file is not formatted.
5. WHEN staged files include any path under `web/`, THE Pre_Commit_Hook SHALL run `npm run typecheck` inside `web/` and exit with a non-zero code if TypeScript reports any type error.
6. WHEN staged files include any path under `web/`, THE Pre_Commit_Hook SHALL run `npm run test:run` inside `web/` and exit with a non-zero code if any unit test fails.
7. WHEN staged files include any path under `web/`, THE Pre_Commit_Hook SHALL run `npm audit --audit-level=high` inside `web/` and exit with a non-zero code if any HIGH or CRITICAL vulnerability is found.
8. IF no staged files are under `web/`, THEN THE Pre_Commit_Hook SHALL skip all frontend checks and proceed without error.
9. THE `justfile` SHALL include a `web-test` recipe that runs `npm run test:run` inside `web/`.
10. THE `justfile` SHALL include a `web-audit` recipe that runs `npm audit --audit-level=high` inside `web/`.

---

### Requirement 2: Frontend CI Pipeline

**User Story:** As a developer, I want CI to automatically validate the frontend on every push and PR, so that regressions are caught before merge.

#### Acceptance Criteria

1. WHEN a push is made to a `feature/**` branch with changes under `web/**`, THE CI_Frontend SHALL trigger automatically.
2. WHEN a pull request targets `main` with changes under `web/**`, THE CI_Frontend SHALL trigger automatically.
3. THE CI_Frontend SHALL include a `lint` job that runs `npm run lint` inside `web/` and blocks merge on any ESLint error.
4. THE CI_Frontend SHALL include a `format` job that runs `npm run format:check` inside `web/` and blocks merge if any file is not formatted.
5. THE CI_Frontend SHALL include a `typecheck` job that runs `npm run typecheck` inside `web/` and blocks merge on any TypeScript error.
6. THE CI_Frontend SHALL include a `test` job that runs `npm run test:coverage` inside `web/` and blocks merge if line coverage falls below 80%.
7. THE CI_Frontend SHALL include a `build` job that runs `npm run build` inside `web/` and blocks merge if the build fails.
8. THE CI_Frontend SHALL include a `dependency-audit` job that runs `npm audit --audit-level=high` inside `web/` and blocks merge on HIGH or CRITICAL findings.
9. THE CI_Frontend SHALL include a `secret-scan` job using Gitleaks with `fetch-depth: 0` that blocks merge on any detected secret.
10. WHEN any CI_Frontend job fails, THE CI_Frontend SHALL send a Slack notification to channel `C0AE6QV0URH` using the `SLACK_BOT_TOKEN` secret with username `ugsys CI/CD`.
11. THE CI_Frontend `test` job SHALL upload the coverage report as a build artifact named `frontend-coverage`.

---

### Requirement 3: AWS Amplify Deploy Workflow

**User Story:** As a developer, I want the frontend to be deployed to AWS Amplify automatically on merge to `main`, so that production always reflects the latest approved code.

#### Acceptance Criteria

1. WHEN a merge to `main` includes changes under `web/**`, THE Deploy_Frontend SHALL trigger automatically.
2. THE Deploy_Frontend SHALL authenticate with AWS using OIDC via `aws-actions/configure-aws-credentials` with `role-to-assume: ${{ secrets.AWS_ROLE_ARN }}` — no static AWS credentials SHALL be used.
3. THE Deploy_Frontend SHALL require `environment: prod` approval before executing any deployment step.
4. THE Deploy_Frontend SHALL build the Web_App using `npm run build` with `VITE_API_BASE_URL` and `VITE_AUTH_API_URL` sourced from repository secrets.
5. THE Web_App SHALL include an `amplify.yml` at `web/amplify.yml` using `dist/` as `baseDirectory` (static SPA pattern — no SSR).
6. THE Deploy_Frontend SHALL start an Amplify deployment by uploading the `web/dist/` artifact and calling the Amplify StartDeployment API for the app ID stored in secret `AMPLIFY_APP_ID` and branch `main`.
7. WHEN the deployment succeeds, THE Deploy_Frontend SHALL send a Slack success notification containing the commit SHA.
8. IF the deployment fails, THEN THE Deploy_Frontend SHALL send a Slack failure notification containing a link to the failed workflow run.

---

### Requirement 4: Architecture Refactor — Hook Extraction and Service Ports

**User Story:** As a developer, I want orchestration logic extracted from page components into hooks and service interfaces defined as TypeScript ports, so that components are thin, logic is testable in isolation, and concrete API modules can be swapped in tests.

#### Acceptance Criteria

1. THE Web_App SHALL define a `IProjectApi` TypeScript interface in `src/services/ports.ts` that declares all methods currently on `projectApi` with their exact signatures.
2. THE Web_App SHALL define a `ISubscriptionApi` TypeScript interface in `src/services/ports.ts` that declares all methods currently on `subscriptionApi` with their exact signatures.
3. THE `useProjects` Hook SHALL accept an optional `api` parameter of type `IProjectApi`, defaulting to the `projectApi` concrete module.
4. THE `useProjectDetail` Hook SHALL accept a `projectId` string and an optional `api` parameter of type `IProjectApi`, defaulting to the `projectApi` concrete module.
5. WHEN `useProjectDetail` is called with a valid `projectId`, THE `useProjectDetail` Hook SHALL return `{ project, isLoading, error }` where `project` is the resolved `EnhancedProject` or `null`.
6. THE `usePublicSubscribe` Hook SHALL accept an optional `api` parameter of type `ISubscriptionApi`, defaulting to the `subscriptionApi` concrete module.
7. WHEN `usePublicSubscribe` is called, THE `usePublicSubscribe` Hook SHALL return `{ submit, isSubmitting, apiError, fieldErrors, emailExistsFor }`.
8. WHEN `usePublicSubscribe.submit` is called with valid form data, THE `usePublicSubscribe` Hook SHALL first call `api.publicCheckEmail`, and IF the email exists THEN set `emailExistsFor` to the submitted email WITHOUT calling `api.publicSubscribe`.
9. WHEN `usePublicSubscribe.submit` is called with valid form data and the email does not exist, THE `usePublicSubscribe` Hook SHALL call `api.publicSubscribe` and invoke the `onSuccess` callback with the result.
10. WHEN `usePublicSubscribe.submit` is called with missing required fields, THE `usePublicSubscribe` Hook SHALL set `fieldErrors` for each missing field and SHALL NOT call any API method.
11. THE `SubscribePage` component SHALL be refactored to use `useProjectDetail` for project fetching and `usePublicSubscribe` for the public subscription flow, containing no inline API calls or form-submission logic.
12. THE `PublicSubscribeForm` component SHALL be extracted from `SubscribePage.tsx` into `src/components/subscriptions/PublicSubscribeForm.tsx` and SHALL receive `usePublicSubscribe`'s return value as props.
13. FOR ALL data-fetching hooks (`useProjects`, `useProjectDetail`), THE Hook SHALL return a consistent shape of `{ data | projects, isLoading: boolean, error: string | null }`.

---

### Requirement 5: Unit Test Suite with Coverage Gate

**User Story:** As a developer, I want a vitest + @testing-library/react test suite with an 80% coverage gate, so that regressions are caught automatically and the codebase is verifiably correct.

#### Acceptance Criteria

1. THE Web_App `package.json` SHALL include `vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, and `jsdom` as `devDependencies`.
2. THE `vite.config.ts` SHALL include a `test` block configuring vitest with `environment: 'jsdom'`, `globals: true`, `setupFiles: ['./src/test/setup.ts']`, and coverage thresholds of 80% for lines, functions, branches, and statements.
3. THE Web_App SHALL include a `src/test/setup.ts` file that imports `@testing-library/jest-dom` matchers.
4. THE `package.json` `scripts` SHALL include `"test:run": "vitest run"`, `"test:watch": "vitest"`, and `"test:coverage": "vitest run --coverage"`.
5. THE Web_App SHALL include unit tests for `usePublicSubscribe` covering: (a) field validation rejects empty required fields without calling any API, (b) email-exists path sets `emailExistsFor` and does not call `publicSubscribe`, (c) happy path calls `publicSubscribe` and invokes `onSuccess`.
6. THE Web_App SHALL include unit tests for `useProjectDetail` covering: (a) loading state is `true` during fetch, (b) resolved project is returned on success, (c) error string is set on API failure.
7. THE Web_App SHALL include unit tests for `useProjects` covering: (a) loading state transitions, (b) projects and total are set on success, (c) error string is set on API failure.
8. THE Web_App SHALL include unit tests for `escapeHtml` and `stripHtml` in `src/utils/sanitize.ts` covering: (a) `escapeHtml` escapes `<`, `>`, `&`, `"`, `'`, (b) `escapeHtml` is idempotent — `escapeHtml(escapeHtml(s))` equals `escapeHtml(s)` for any string `s`, (c) `stripHtml` removes all HTML tags from a string.
9. THE Web_App SHALL include unit tests for `getErrorMessage` and `isApiError` in `src/utils/errorHandling.ts`.
10. WHEN the vitest coverage report is generated, THE Coverage_Gate SHALL fail the test run if line, branch, function, or statement coverage falls below 80%.
11. THE CI_Frontend `test` job SHALL run `npm run test:coverage` and fail the job if the Coverage_Gate threshold is not met.

---

### Requirement 6: ESLint and Prettier Configuration

**User Story:** As a developer, I want ESLint to enforce React hooks rules and accessibility best practices, and Prettier to enforce consistent formatting, so that code quality issues are caught at commit time and in CI.

#### Acceptance Criteria

1. THE Web_App `package.json` SHALL include `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `eslint-plugin-react`, `prettier`, and `eslint-config-prettier` as `devDependencies`.
2. THE `eslint.config.js` SHALL enable `eslint-plugin-react-hooks` with `react-hooks/rules-of-hooks: error` and `react-hooks/exhaustive-deps: warn`.
3. THE `eslint.config.js` SHALL enable `eslint-plugin-jsx-a11y` with recommended rules to catch accessibility issues.
4. THE `eslint.config.js` SHALL enable `eslint-plugin-react` with `react/jsx-key: error`, `react/jsx-no-duplicate-props: error`, and `react/no-unescaped-entities: warn`.
5. THE Web_App SHALL include a `.prettierrc` file defining consistent formatting rules (`printWidth: 100`, `singleQuote: true`, `trailingComma: "es5"`, `semi: true`).
6. THE `package.json` `scripts` SHALL include `"format": "prettier --write src/"` and `"format:check": "prettier --check src/"`.
7. THE Pre_Commit_Hook SHALL run `npm run format:check` inside `web/` and exit with a non-zero code if any file is not formatted (covered in Requirement 1 AC 4).
8. THE CI_Frontend SHALL include a `format` job that runs `npm run format:check` inside `web/` and blocks merge if any file is not formatted (covered in Requirement 2 AC 4).

---

### Requirement 7: Logger Error Forwarding and Token Security

**User Story:** As a developer, I want production errors forwarded to an error-tracking adapter and tokens stored securely in memory, so that silent failures are observable and XSS-based token theft is prevented.

#### Acceptance Criteria

1. THE `logger` in `src/utils/logger.ts` SHALL accept an optional `ErrorTracker` adapter injected at app startup via a `configureLogger` function.
2. WHEN `logger.error` is called in a non-development environment, THE `logger` SHALL forward the error event to the configured `ErrorTracker` adapter if one has been set.
3. THE Web_App SHALL define an `ErrorTracker` interface in `src/utils/logger.ts` with a single method `captureError(message: string, data?: unknown): void`.
4. THE Web_App SHALL provide a no-op `ErrorTracker` implementation used by default when no adapter is configured, so that the logger never throws if no tracker is set.
5. THE `authStore` SHALL NOT store `access_token` or `refresh_token` in `localStorage`.
6. THE `httpClient` SHALL read the `access_token` from an in-memory variable populated by `authStore` rather than from `localStorage`.
7. WHEN `authStore.logout` is called, THE `authStore` SHALL clear the in-memory token and call the backend `/api/v1/auth/logout` endpoint to invalidate the server-side session.
8. THE Web_App SHALL include unit tests for the `logger` verifying that `logger.error` invokes the `ErrorTracker.captureError` method when a tracker is configured and the environment is non-development.
