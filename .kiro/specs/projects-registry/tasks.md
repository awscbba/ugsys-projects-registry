# Implementation Plan: ugsys-projects-registry

## Overview

Scaffold and implement the `ugsys-projects-registry` microservice from scratch following hexagonal architecture, TDD, and platform standards. Tasks are ordered: repo scaffold → domain layer → infrastructure layer → application layer → presentation layer → CI/CD → migration script.

## Tasks

- [x] 1. Scaffold repository structure and project configuration
  - Create `ugsys-projects-registry/` directory with canonical hexagonal layout (`src/presentation/`, `src/application/`, `src/domain/`, `src/infrastructure/`, `tests/unit/`, `tests/integration/`)
  - Create `pyproject.toml` with Python 3.13+, FastAPI, Pydantic v2, aioboto3, httpx, mangum, python-ulid, hypothesis, moto, pytest-asyncio, structlog, pydantic-settings, ugsys-auth-client, ugsys-logging-lib, ugsys-event-lib; ruff and mypy strict config; bandit config; 80% coverage gate
  - Create `devbox.json`, `justfile` with targets `install-hooks`, `lint`, `format`, `typecheck`, `test`, `test-integration`, `diff`
  - Create `scripts/hooks/pre-commit` and `scripts/install-hooks.sh` blocking commits to `main`, running ruff + unit tests
  - Create `src/config.py` with `pydantic-settings` `Settings` class including all fields from design (DynamoDB table properties, S3, Identity Manager, Cognito, EventBridge)
  - Create `handler.py` at repo root with `Mangum(app, lifespan="on")`
  - Define `SERVICE_CONFIG_SCHEMA` and `SERVICE_ROLES` constants in `src/config.py` per Section 14.2 of platform-contract
  - Add `service_id`, `display_name`, `version`, `nav_icon`, `public_base_url` fields to `Settings` class
  - Add operator-configurable fields to `Settings`: `max_subscriptions_per_project`, `admin_notification_email`, `subscription_approval_required`
  - Implement `apply_remote_config(config: dict) -> None` method on `Settings` class
  - _Requirements: 1.1, 1.6, 1.7, 1.10, 1.11, 1.12, 16.6, 16.7, 18.5, 18.6, 18.7_

- [x] 2. Implement domain layer — entities, value objects, exceptions, and repository ABCs
  - [x] 2.1 Create `src/domain/exceptions.py` with full exception hierarchy: `DomainError`, `ValidationError`, `NotFoundError`, `ConflictError`, `AuthenticationError`, `AuthorizationError`, `RepositoryError`, `ExternalServiceError`
    - _Requirements: 1.9, 18.1_

  - [x] 2.2 Create `src/domain/value_objects/project_status.py` with `ProjectStatus` and `SubscriptionStatus` `StrEnum` classes
    - _Requirements: 2.1, 4.1_

  - [x] 2.3 Create `src/domain/entities/form_schema.py` with `FieldType`, `CustomField`, `FormSchema` dataclasses
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.9_

  - [x]* 2.4 Write unit tests for `FormSchema` entity — field count limit, duplicate IDs, poll option bounds, valid construction
    - _Requirements: 5.2, 5.3, 5.4, 17.1_

  - [x] 2.5 Create `src/domain/entities/project.py` with `ProjectImage` and `Project` dataclasses (all fields from design)
    - _Requirements: 2.1, 2.11, 13.3, 13.4, 13.5_

  - [x]* 2.6 Write unit tests for `Project` entity — creation invariants (status=pending, current_participants=0, ULID id), date range validation, max_participants validation
    - **Property 2: Project creation invariants**
    - **Property 3: Date range validation**
    - _Requirements: 2.1, 2.2, 2.3, 17.1_

  - [x] 2.7 Create `src/domain/entities/subscription.py` and `src/domain/entities/form_submission.py` dataclasses
    - _Requirements: 4.1, 4.9, 6.8_

  - [x]* 2.8 Write unit tests for `Subscription` entity — status transitions, is_active flag
    - **Property 7: Subscription status transition invariant**
    - _Requirements: 4.1, 4.4, 4.5, 4.6, 17.1_

  - [x] 2.9 Create all repository ABCs in `src/domain/repositories/`: `project_repository.py`, `subscription_repository.py`, `form_submission_repository.py`, `event_publisher.py`, `identity_client.py`, `circuit_breaker.py`
    - `circuit_breaker.py`: `CircuitBreaker` ABC with `state() -> CircuitState`, `record_success()`, `record_failure()`, `allow_request() -> bool`; `CircuitState` StrEnum (`closed`, `open`, `half_open`)
    - `project_repository.py`: add `list_by_query(query: ProjectListQuery) -> tuple[list[Project], int]` method alongside existing methods
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 18.3, 20.7, 21.2_


- [x] 3. Implement infrastructure layer — DynamoDB repositories
  - [x] 3.1 Create `src/infrastructure/logging.py` with `configure_logging()` using structlog JSON processors
    - _Requirements: 1.7, 15.1_

  - [x] 3.2 Implement `DynamoDBProjectRepository` in `src/infrastructure/persistence/dynamodb_project_repository.py`
    - Implement `save`, `find_by_id`, `update`, `delete`, `list_paginated`, `list_public`, `list_by_query` with full `_to_item`/`_from_item` serialization
    - `list_by_query` accepts `ProjectListQuery` object; uses GSI-1 when `status` filter is set; builds `FilterExpression` for other criteria; applies in-memory sort and pagination
    - All boto3 calls wrapped in `try/except ClientError`; `_raise_repository_error()` logs internally, raises `RepositoryError` with safe `user_message`
    - `_from_item` uses `.get()` with safe defaults for all optional fields; `_to_item` omits `None`/empty optional fields
    - GSI-1 (`status-index`) used for `list_public` and filtered listing; GSI-2 (`created_by-index`) for owner queries
    - `list_public` filters `status=active AND is_enabled=true`, strips `notification_emails`
    - _Requirements: 2.5, 2.11, 19.6, 19.12, 21.3_

  - [x]* 3.3 Write integration tests for `DynamoDBProjectRepository` using `moto mock_aws`
    - Create table with all GSIs matching production schema
    - Test `save`/`find_by_id` round-trip for all fields including optional ones
    - Test backward compatibility: items missing optional fields deserialize with safe defaults
    - Test `ConditionalCheckFailedException` on duplicate `save` raises `RepositoryError`
    - Test `list_public` returns only active+enabled projects and excludes `notification_emails`
    - _Requirements: 17.2, 19.12_

  - [x] 3.4 Implement `DynamoDBSubscriptionRepository` in `src/infrastructure/persistence/dynamodb_subscription_repository.py`
    - Implement all ABC methods including `find_by_person_and_project` (GSI-3 `person-project-index`), `cancel_all_for_person`, `list_by_project` (GSI-2), `list_by_person` (GSI-1)
    - `person_project_key` attribute = `{person_id}#{project_id}` written to item for GSI-3
    - _Requirements: 4.9, 19.7, 19.12_

  - [x]* 3.5 Write integration tests for `DynamoDBSubscriptionRepository` using `moto mock_aws`
    - Test `find_by_person_and_project` via GSI-3 returns correct subscription
    - Test `cancel_all_for_person` updates all active/pending subscriptions and returns count
    - Test `ClientError` wrapping raises `RepositoryError`
    - _Requirements: 17.2, 19.12_

  - [x] 3.6 Implement `DynamoDBFormSubmissionRepository` in `src/infrastructure/persistence/dynamodb_form_submission_repository.py`
    - Implement `save`, `find_by_person_and_project`, `list_by_project` with GSI queries
    - `responses` stored as JSON string attribute
    - _Requirements: 6.8, 19.8, 19.12_

  - [x]* 3.7 Write integration tests for `DynamoDBFormSubmissionRepository` using `moto mock_aws`
    - Test `_to_item`/`_from_item` round-trip preserving all `responses` dict entries
    - Test `find_by_person_and_project` returns `None` when no submission exists
    - **Property 12: FormSubmission round-trip**
    - _Requirements: 6.7, 17.2_

  - [x] 3.8 Implement `EventBridgePublisher` in `src/infrastructure/messaging/event_publisher.py`
    - Wrap `put_events` in `try/except ClientError`; raise `ExternalServiceError` on failure
    - Envelope includes `event_id`, `event_version`, `timestamp`, `correlation_id`, `payload`
    - _Requirements: 10.9, 19.9_

  - [x] 3.9 Implement `S2STokenProvider` in `src/infrastructure/adapters/s2s_token_provider.py`
    - TTL-based in-memory cache; refresh 60 seconds before expiry via `client_credentials` grant
    - _Requirements: 1.11_

  - [x] 3.10 Implement `IdentityManagerClient` in `src/infrastructure/adapters/identity_manager_client.py`
    - `check_email_exists` and `create_user` via httpx with S2S bearer token; wrap every call with circuit breaker (`allow_request()` check before call, `record_success()`/`record_failure()` after); raise `ExternalServiceError(SERVICE_UNAVAILABLE)` when circuit is open
    - `register_service` (POST to `/api/v1/services/register` with schema, roles, metadata) and `get_service_config` (GET from `/api/v1/services/{service_id}/config`) — both via S2S bearer token, both wrapped with circuit breaker
    - Implement `_call_with_circuit_breaker(operation, coro_factory)` helper to DRY the pattern across all methods
    - _Requirements: 1.11, 1.12, 7.1, 7.2, 19.10, 20.1, 20.2, 20.3_

  - [x] 3.11 Implement `InMemoryCircuitBreaker` in `src/infrastructure/adapters/in_memory_circuit_breaker.py`
    - Implement `CircuitBreaker` ABC with `failure_threshold=5`, `cooldown_seconds=30` defaults
    - State machine: CLOSED → OPEN after N consecutive failures; OPEN → HALF_OPEN after cooldown; HALF_OPEN → CLOSED on success, HALF_OPEN → OPEN on failure
    - Log every state transition with `structlog` including service name
    - _Requirements: 20.1, 20.2, 20.4, 20.5, 20.6, 20.7, 20.8_

  - [x]* 3.12 Write unit tests for `InMemoryCircuitBreaker`
    - Test CLOSED → OPEN after 5 consecutive failures
    - Test OPEN rejects requests immediately with `allow_request() == False`
    - Test OPEN → HALF_OPEN after cooldown expires (mock `time.monotonic`)
    - Test HALF_OPEN → CLOSED on success
    - Test HALF_OPEN → OPEN on failure
    - Test success resets failure count
    - **Property 21: Circuit Breaker state transitions**
    - _Requirements: 20.1, 20.2, 20.4, 20.5, 20.6, 17.1_


- [x] 4. Implement application layer — commands, queries, DTOs, and services
  - [x] 4.1 Create all command and query dataclasses in `src/application/commands/` and `src/application/queries/`
    - `CreateProjectCommand`, `UpdateProjectCommand`, `CreateSubscriptionCommand`, `ApproveSubscriptionCommand`, `RejectSubscriptionCommand`, `SubmitFormCommand`, `PublicRegisterCommand`, `PublicSubscribeCommand`, `GenerateUploadUrlCommand`, `BulkActionCommand`
    - `ProjectListQuery` (frozen dataclass with `page`, `page_size`, `status`, `category`, `owner_id`, `sort_by`, `sort_order`, `has_filters()` method), `PaginatedUsersQuery`
    - _Requirements: 2.1, 2.4, 4.1, 4.4, 4.5, 4.6, 6.1, 7.2, 7.4, 8.1, 9.4, 9.5, 21.1_

  - [x] 4.2 Create response DTOs in `src/application/dtos/` — `ProjectResponse`, `SubscriptionResponse`, `EnrichedSubscriptionResponse`, `FormSubmissionResponse`, `DashboardData`, `EnhancedDashboardData`, `AnalyticsData`, `BulkActionResult`, `UploadUrlResult`, `PublicRegisterResult`
    - _Requirements: 1.4, 9.1, 9.2, 9.3, 9.5, 8.1_

  - [x] 4.3 Implement `ProjectService` in `src/application/services/project_service.py`
    - `create`: validate date range (raise `ValidationError` with `INVALID_DATE_RANGE`), validate `max_participants >= 1` (raise `INVALID_MAX_PARTICIPANTS`), generate ULID, set `status=pending`, `current_participants=0`, publish `projects.project.created`; catch and log event publish failure without rollback
    - `get`: raise `NotFoundError` with `PROJECT_NOT_FOUND` if missing
    - `list_all`: paginated, admin only
    - `list_public`: delegates to `project_repo.list_public`, strips `notification_emails`
    - `update`: IDOR check (owner or admin, raise `AuthorizationError` with `FORBIDDEN`); if `status→active` publish `projects.project.published`; if `status→completed|cancelled` cascade subscriptions and set `is_enabled=False`; publish `projects.project.updated`
    - `delete`: admin only, publish `projects.project.deleted`
    - Log `duration_ms` on every method
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 3.1, 3.2, 10.1, 10.2, 10.3, 10.4, 10.10, 12.1, 12.2_

  - [x]* 4.4 Write unit tests for `ProjectService`
    - Test `create` happy path: ULID generated, status=pending, current_participants=0, event published
    - Test `create` with end_date < start_date raises `ValidationError(INVALID_DATE_RANGE)`
    - Test `create` with max_participants < 1 raises `ValidationError(INVALID_MAX_PARTICIPANTS)`
    - Test `update` by non-owner non-admin raises `AuthorizationError(FORBIDDEN)`
    - Test `update` status→active publishes `projects.project.published`
    - Test `update` status→cancelled cascades subscriptions
    - Test event publish failure does not raise (logged only)
    - **Property 2: Project creation invariants**
    - **Property 3: Date range validation**
    - **Property 8: Project status cascade**
    - _Requirements: 17.1, 17.3, 17.4_

  - [x] 4.5 Implement `SubscriptionService` in `src/application/services/subscription_service.py`
    - `subscribe`: duplicate check via `find_by_person_and_project` (raise `ConflictError(SUBSCRIPTION_ALREADY_EXISTS)`); status=active if super_admin else pending; increment `current_participants` if active; publish `projects.subscription.created` with `notification_emails`
    - `approve`: admin only, status→active, increment count, publish `projects.subscription.approved`
    - `reject`: admin only, status→rejected, publish `projects.subscription.rejected`
    - `cancel`: owner or admin (raise `AuthorizationError(FORBIDDEN)`); decrement count if was active; publish `projects.subscription.cancelled`
    - `list_by_project`, `list_by_person` with IDOR check on person endpoint
    - Log `duration_ms` on every method
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.10, 4.11, 10.5, 10.6, 10.7, 10.8, 12.2, 12.6_

  - [x]* 4.6 Write unit tests for `SubscriptionService`
    - Test `subscribe` happy path: ULID, status=pending, event published with notification_emails
    - Test `subscribe` super_admin: status=active, current_participants incremented
    - Test `subscribe` duplicate raises `ConflictError(SUBSCRIPTION_ALREADY_EXISTS)`
    - Test `approve` increments current_participants and publishes event
    - Test `cancel` by non-owner non-admin raises `AuthorizationError(FORBIDDEN)`
    - Test `cancel` of active subscription decrements current_participants
    - Test `list_by_person` by different user raises `AuthorizationError(FORBIDDEN)`
    - **Property 5: Participant count invariant**
    - **Property 6: Subscription uniqueness invariant**
    - **Property 7: Subscription status transition invariant**
    - _Requirements: 17.1, 17.3, 17.4_

  - [x] 4.7 Implement `FormService` in `src/application/services/form_service.py`
    - `update_schema`: IDOR check; validate field count ≤20 (`FORM_SCHEMA_TOO_MANY_FIELDS`), no duplicate IDs (`FORM_SCHEMA_DUPLICATE_FIELD_IDS`), poll options 2-10 (`FORM_SCHEMA_INVALID_OPTIONS`), serialized size ≤50KB (`FORM_SCHEMA_TOO_LARGE`); persist on project
    - `submit`: load project, check schema exists (`PROJECT_HAS_NO_FORM_SCHEMA`); validate required fields (`FORM_SUBMISSION_MISSING_REQUIRED_FIELD`), poll_single values (`FORM_SUBMISSION_INVALID_RESPONSE`), poll_multiple values (`FORM_SUBMISSION_INVALID_RESPONSE`); save submission
    - `get_submission`: IDOR check; raise `NotFoundError(FORM_SUBMISSION_NOT_FOUND)` if missing
    - `list_by_project`: admin only
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x]* 4.8 Write unit tests for `FormService`
    - Test `update_schema` with 21 fields raises `ValidationError(FORM_SCHEMA_TOO_MANY_FIELDS)`
    - Test `update_schema` with duplicate field IDs raises `ValidationError(FORM_SCHEMA_DUPLICATE_FIELD_IDS)`
    - Test `update_schema` poll field with 1 option raises `ValidationError(FORM_SCHEMA_INVALID_OPTIONS)`
    - Test `submit` missing required field raises `ValidationError(FORM_SUBMISSION_MISSING_REQUIRED_FIELD)`
    - Test `submit` invalid poll_single value raises `ValidationError(FORM_SUBMISSION_INVALID_RESPONSE)`
    - Test `submit` for project with no schema raises `ValidationError(PROJECT_HAS_NO_FORM_SCHEMA)`
    - **Property 1: FormSchema serialization round-trip**
    - **Property 9: FormSchema validation — field count**
    - **Property 10: FormSchema validation — poll options**
    - **Property 11: FormSubmission validation**
    - _Requirements: 17.1, 17.3, 17.5, 17.6_

  - [x] 4.9 Implement `PublicService` in `src/application/services/public_service.py`
    - `check_email`: delegates to `identity_client.check_email_exists`
    - `register`: check email exists (raise `ConflictError(EMAIL_ALREADY_EXISTS)` if true); call `identity_client.create_user`; return `PublicRegisterResult`
    - `subscribe`: create user if not exists; duplicate check; create subscription with `status=pending` always; publish `projects.subscription.created` with `notification_emails`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x]* 4.10 Write unit tests for `PublicService`
    - Test `register` with existing email raises `ConflictError(EMAIL_ALREADY_EXISTS)`
    - Test `subscribe` always creates subscription with status=pending regardless of any input
    - Test `subscribe` duplicate raises `ConflictError(SUBSCRIPTION_ALREADY_EXISTS)`
    - **Property 13: Public subscription always pending**
    - _Requirements: 17.1, 17.3_

  - [x] 4.11 Implement `AdminService` in `src/application/services/admin_service.py`
    - `dashboard`: aggregate counts from all three repositories
    - `enhanced_dashboard`: adds per-project stats and recent signups
    - `analytics`: breakdown by status
    - `paginated_users`: delegates to `IdentityClient`
    - `bulk_action`: validate action and userIds (raise `ValidationError(VALIDATION_ERROR)` if missing/empty); for `delete` check active/pending subscriptions (return `BUSINESS_RULE_VIOLATION` per user); process each user, collect per-user results
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x]* 4.12 Write unit tests for `AdminService`
    - Test `bulk_action` with empty `userIds` raises `ValidationError(VALIDATION_ERROR)`
    - Test `bulk_action` delete for user with active subscriptions returns `BUSINESS_RULE_VIOLATION` for that user and continues processing others
    - _Requirements: 9.6, 9.8, 17.1_

  - [x] 4.13 Implement `ImageService` in `src/application/services/image_service.py`
    - Validate `file_size <= 10MB` (raise `ValidationError(IMAGE_TOO_LARGE)`); validate `content_type` in allowed set (raise `ValidationError(IMAGE_INVALID_CONTENT_TYPE)`)
    - Generate ULID `image_id`; call S3 `generate_presigned_url` with 300s TTL; return presigned URL + CloudFront URL
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x]* 4.14 Write unit tests for `ImageService`
    - Test file_size > 10MB raises `ValidationError(IMAGE_TOO_LARGE)`
    - Test invalid content_type raises `ValidationError(IMAGE_INVALID_CONTENT_TYPE)`
    - Test valid request returns presigned URL and CloudFront URL with correct format
    - _Requirements: 8.1, 8.2, 8.3, 17.1_

  - [x] 4.15 Implement `EventConsumerService` in `src/application/services/event_consumer_service.py`
    - `handle_user_deactivated`: call `subscription_repo.cancel_all_for_person`; publish `projects.subscription.cancelled` for each cancelled subscription; log count; if no subscriptions, complete successfully
    - _Requirements: 11.1, 11.2, 11.4_

  - [x]* 4.16 Write unit tests for `EventConsumerService`
    - Test `handle_user_deactivated` cancels all subscriptions and publishes one event per cancelled subscription
    - Test `handle_user_deactivated` for user with no subscriptions completes without error
    - **Property 19: User deactivation cascade**
    - _Requirements: 11.1, 11.2, 17.1_

- [x] 5. Checkpoint — Ensure all domain and application layer tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 6. Implement presentation layer — middleware, exception handler, and API routers
  - [x] 6.1 Create `src/presentation/middleware/correlation_id.py` (`CorrelationIdMiddleware`), `security_headers.py` (`SecurityHeadersMiddleware` with all required headers including removal of `Server` header), `rate_limiting.py` (`RateLimitMiddleware` 60 req/min per JWT `sub`, fallback to IP, 429 with `Retry-After` and `X-RateLimit-*` headers)
    - _Requirements: 1.2, 15.5, 15.6, 15.7_

  - [x] 6.1a Add `CORSMiddleware` to `create_app()` in `src/main.py` with `allow_origins=settings.allowed_origins` (explicit allowlist from `Settings`), `allow_credentials=True`, methods `GET POST PUT PATCH DELETE`, headers `Authorization Content-Type X-Request-ID`
    - Add `allowed_origins: list[str]` field to `Settings` in `src/config.py` loaded from env var `ALLOWED_ORIGINS`
    - _Requirements: 1.2, 12.3_ (security.md CORS policy)

  - [x] 6.1b Verify `ugsys-auth-client` dependency is configured with `algorithms=["RS256"]` only — confirm HS256 and `none` algorithm tokens are rejected before signature verification; add integration test asserting HTTP 401 on HS256-signed token
    - _Requirements: 1.3, 12.5_

  - [x]* 6.2 Write unit tests for middleware
    - Test `CorrelationIdMiddleware` sets `X-Request-ID` on response and binds to structlog context
    - Test `SecurityHeadersMiddleware` sets all required headers on every response and removes `Server` header
    - Test `RateLimitMiddleware` returns 429 with `Retry-After` after limit exceeded
    - **Property 17: Security headers invariant**
    - _Requirements: 1.2, 15.5, 15.6, 15.7, 17.1_

  - [x] 6.3 Create `src/presentation/middleware/exception_handler.py` with `domain_exception_handler` and `unhandled_exception_handler`
    - Map all domain exception types to correct HTTP status codes per design
    - `user_message` in response body, full `message` in logs only
    - _Requirements: 1.5, 1.9_

  - [x] 6.4 Create `src/presentation/dependencies.py` with `get_*_service()` dependency functions reading from `app.state`
    - _Requirements: 18.4, 18.5_

  - [x] 6.5 Create `src/presentation/api/v1/health.py` with `GET /health` and `GET /` routes (no auth)
    - _Requirements: 1.1_

  - [x] 6.6 Create `src/presentation/api/v1/projects.py` with all project routes
    - `POST /api/v1/projects` (JWT), `GET /api/v1/projects` (Admin JWT), `GET /api/v1/projects/public` (no auth), `GET /api/v1/projects/{id}` (JWT), `PUT /api/v1/projects/{id}` (JWT), `DELETE /api/v1/projects/{id}` (Admin JWT)
    - `GET /api/v1/projects/{id}/enhanced` (JWT), `POST /api/v1/projects/enhanced` (JWT)
    - `PUT /api/v1/projects/{id}/form-schema` (JWT)
    - All responses wrapped in `{ "data": ..., "meta": { "request_id": "..." } }` envelope
    - Extract requester identity from JWT `sub` only — never from request body
    - _Requirements: 1.1, 1.4, 2.1, 2.4, 2.5, 2.6, 2.7, 2.9, 5.1, 5.6, 5.7, 12.1_

  - [x]* 6.7 Write unit tests for projects router
    - Test `POST /api/v1/projects` returns 201 with envelope
    - Test `GET /api/v1/projects/public` returns only active+enabled projects without notification_emails
    - Test `PUT /api/v1/projects/{id}` by non-owner returns 403
    - Test `DELETE /api/v1/projects/{id}` without admin JWT returns 403
    - **Property 4: Public endpoint filter invariant**
    - _Requirements: 2.5, 2.8, 3.3, 3.4, 17.1_

  - [x] 6.8 Create `src/presentation/api/v1/subscriptions.py` with all subscription routes
    - `POST /api/v1/projects/{id}/subscriptions` (JWT), `GET /api/v1/projects/{id}/subscriptions` (Admin/Mod JWT), `PUT /api/v1/projects/{id}/subscribers/{sub_id}` (Admin JWT), `DELETE /api/v1/projects/{id}/subscribers/{sub_id}` (JWT)
    - `GET /api/v1/subscriptions/person/{person_id}` (JWT with IDOR check), `POST /api/v1/subscriptions/check` (JWT)
    - _Requirements: 4.1, 4.4, 4.5, 4.6, 4.7, 4.10, 4.11, 7.9, 12.6_

  - [x]* 6.9 Write unit tests for subscriptions router
    - Test `POST /api/v1/projects/{id}/subscriptions` returns 201 with envelope
    - Test `GET /api/v1/subscriptions/person/{person_id}` by different user returns 403
    - Test `DELETE /api/v1/projects/{id}/subscribers/{sub_id}` by non-owner returns 403
    - _Requirements: 4.7, 12.6, 17.1_

  - [x] 6.10 Create `src/presentation/api/v1/public.py` with public routes (no auth)
    - `POST /api/v1/public/check-email`, `POST /api/v1/public/register`, `POST /api/v1/public/subscribe`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

  - [x] 6.11 Create `src/presentation/api/v1/form_submissions.py`, `images.py`, and `admin.py` routers
    - `form_submissions.py`: `POST /api/v1/form-submissions` (JWT), `GET /api/v1/form-submissions/project/{project_id}` (Admin JWT), `GET /api/v1/form-submissions/person/{person_id}/project/{project_id}` (JWT with IDOR)
    - `images.py`: `POST /api/v1/images/upload-url` (JWT)
    - `admin.py`: all 6 admin routes (Admin JWT)
    - _Requirements: 6.1, 6.6, 6.7, 8.1, 9.1, 9.2, 9.3, 9.4, 9.5, 9.7_

  - [x] 6.12 Create `src/presentation/event_consumer.py` — separate Lambda handler entry point for EventBridge events
    - Route `identity.user.deactivated` to `EventConsumerService.handle_user_deactivated`
    - Log every received event at `info` level with `detail_type`, `source`, `correlation_id`
    - Re-raise on transient errors (do not swallow)
    - _Requirements: 11.1, 11.3, 11.4_

  - [x] 6.13 Create `src/main.py` — composition root with `lifespan` and `create_app()`
    - Call `configure_logging()` first; wire all repositories, services, and adapters in lifespan; register all middleware and exception handlers; include all routers; disable `/docs` and `/redoc` in prod
    - Create `InMemoryCircuitBreaker(service_name="identity-manager", failure_threshold=5, cooldown_seconds=30)` and inject into `IdentityManagerClient` constructor
    - In lifespan, after wiring services: call `identity_client.register_service()` with `SERVICE_CONFIG_SCHEMA` and `SERVICE_ROLES` (non-fatal — log warning on failure, per Section 14.7 of platform-contract)
    - In lifespan, after registration: call `identity_client.get_service_config()` and `settings.apply_remote_config()` (non-fatal — use env var defaults on failure)
    - _Requirements: 1.2, 1.7, 1.10, 1.11, 1.12, 18.5, 18.7, 20.9_


- [x] 7. Add property-based tests (hypothesis) for cross-cutting correctness properties
  - [x]* 7.1 Write property test for FormSchema round-trip
    - Implement `form_schema_strategy()` generating valid `FormSchema` objects (0–20 fields, valid types, 2–10 poll options, unique IDs, questions ≤500 chars)
    - `@given(form_schema_strategy()) @settings(max_examples=200)` — serialize to JSON, deserialize, assert equality
    - **Property 1: FormSchema serialization round-trip**
    - _Requirements: 6.9, 17.5_

  - [x]* 7.2 Write property test for subscription uniqueness invariant
    - Use `InMemorySubscriptionRepository` (implement in `tests/` only); generate random `person_id`/`project_id` ULIDs and 2–5 subscribe attempts
    - Assert first attempt succeeds, all subsequent raise `ConflictError(SUBSCRIPTION_ALREADY_EXISTS)`
    - Assert exactly one non-cancelled subscription exists after all attempts
    - **Property 6: Subscription uniqueness invariant**
    - _Requirements: 4.3, 17.6_

  - [x]* 7.3 Write property test for participant count invariant
    - Generate random `n_approvals` (0–10) and `n_cancellations` (0–min(5, n_approvals))
    - Assert `project.current_participants == n_approvals - n_cancellations` after all operations
    - Assert count matches actual active subscriptions in repository
    - **Property 5: Participant count invariant**
    - _Requirements: 4.2, 4.4, 4.6, 2.10_

  - [x]* 7.4 Write property test for public subscribe always pending
    - Generate arbitrary person data and project IDs; call `public_service.subscribe`
    - Assert resulting subscription always has `status=pending`
    - **Property 13: Public subscription always pending**
    - _Requirements: 7.7_

  - [x]* 7.5 Write property test for input length validation
    - Generate `Project.name` strings with length 201–500; assert `ValidationError(VALIDATION_ERROR)` raised
    - Repeat for `description` (>5000), `rich_text` (>10000), `Subscription.notes` (>1000), `CustomField.question` (>500)
    - **Property 16: Input length validation**
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7_

  - [x]* 7.6 Write property test for Circuit Breaker state transitions
    - Generate random sequences of success/failure calls (0–20 each); verify state machine invariants hold after each call
    - After N consecutive failures (N ≥ failure_threshold): state must be OPEN, `allow_request()` must return False
    - After success in any state: failure count resets to 0
    - **Property 21: Circuit Breaker state transitions**
    - _Requirements: 20.1, 20.2, 20.5, 17.1_

- [x] 8. Checkpoint — Ensure all tests pass including property-based tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Create CI/CD workflows
  - [x] 9.1 Create `.github/workflows/ci.yml`
    - Jobs in order: `lint` (ruff check + format check), `typecheck` (mypy strict), `test` (pytest unit, 80% coverage gate), `sast` (Bandit `bandit -r src/ -c pyproject.toml -ll`), `sast-semgrep` (p/python, p/security-audit, p/owasp-top-ten, p/secrets), `dependency-scan` (Safety, advisory), `sbom` (CycloneDX → Trivy CRITICAL/HIGH, blocks merge), `secret-scan` (Gitleaks, `fetch-depth: 0`), `arch-guard` (grep domain/application layer imports), `notify-failure` (Slack on any failure)
    - Triggers: push to `feature/**`, PR to `main`
    - OIDC role `ugsys-github-deploy-ugsys-projects-registry`
    - _Requirements: 16.1, 16.5_

  - [x] 9.2 Create `.github/workflows/deploy.yml`
    - Trigger: merge to `main` only; `environment: prod` gate; OIDC auth; Slack success/failure notification
    - _Requirements: 16.2, 16.5_

  - [x] 9.3 Create `.github/workflows/codeql.yml`
    - Triggers: PR to `main` + weekly Monday 06:00 UTC; Python `security-extended,security-and-quality`; SARIF upload to GitHub Security tab
    - _Requirements: 16.3_

  - [x] 9.4 Create `.github/workflows/security-scan.yml`
    - Triggers: post-deploy to `main` + `workflow_dispatch`; OWASP ZAP baseline + Nuclei; block on critical findings; Slack notification
    - _Requirements: 16.4_

- [x] 10. Implement data migration script
  - [x]* 10.1 Create `scripts/migrate_from_registry.py`
    - Connect to Registry PostgreSQL via `REGISTRY_DB_URL` env var; connect to DynamoDB via IAM role
    - For each entity type (projects, subscriptions, form_submissions): SELECT all from PostgreSQL; for each record check DynamoDB for existing item with `registry_original_id`; if exists log warning and skip; if not exists map fields, set `migrated_from="registry"`, `migrated_at=now()`, write to DynamoDB; on `ClientError` log error and continue
    - Log summary: total, written, skipped, failed
    - **Property 20: Migration idempotency**
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [x] 11. Final checkpoint — full test suite and architecture guard
  - Run full unit + integration test suite; verify 80%+ coverage; verify arch-guard grep passes (no domain→infra imports, no application→infra imports); ensure all tests pass, ask the user if questions arise.

- [x] 11.5. Add AWS X-Ray distributed tracing instrumentation
  - [x] 11.5.1 Add `aws-xray-sdk` to `pyproject.toml` dependencies and `xray_tracing_enabled`, `xray_sampling_rate` fields to `Settings` in `src/config.py`
    - _Requirements: 31.8, 31.9_

  - [x] 11.5.2 Create `src/infrastructure/tracing.py` with `traced_subsegment()` context manager and `@traced` decorator — graceful fallback when X-Ray is unavailable
    - _Requirements: 31.3, 31.7_

  - [x] 11.5.3 Create `src/presentation/middleware/xray_middleware.py` — reads trace header, annotates segment with service name, version, environment, correlation_id, user_id; adds error annotations on 4xx/5xx
    - _Requirements: 31.4, 31.5, 31.6_

  - [x] 11.5.4 Add X-Ray boto3 patching to `src/main.py` startup (conditional on `settings.xray_tracing_enabled`), add `XRayMiddleware` to middleware stack in `create_app()`
    - _Requirements: 31.1, 31.8_

  - [x] 11.5.5 Add `@traced` decorator to all application service methods in `src/application/services/` (ProjectService, SubscriptionService, FormService, PublicService, AdminService, ImageService, EventConsumerService)
    - _Requirements: 31.3_

  - [x] 11.5.6 Propagate `X-Amzn-Trace-Id` header in `IdentityManagerClient` httpx calls — create subsegment per outbound call
    - _Requirements: 31.2_

  - [x]* 11.5.7 Write unit test for `@traced` decorator — verify it creates subsegment name correctly, records exceptions, and falls back gracefully when X-Ray is unavailable
    - _Requirements: 31.3, 31.7_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- TDD workflow: write the `*` test task first (RED), then implement the parent task (GREEN)
- Each task references specific requirements for traceability
- Property tests use `hypothesis` — never implement PBT from scratch
- All IDs are ULIDs — use `python-ulid` library
- Mock at the port boundary: `AsyncMock(spec=ProjectRepository)` — never mock boto3 directly
- Integration tests use `moto mock_aws` — no real AWS calls
- `user_message` in exceptions must never contain internal details, stack traces, or PII
- Event publish failures are logged but never roll back the primary DynamoDB operation
- The migration script (task 10.1) is optional — it can be run independently after the service is deployed


- [x] 12. Scaffold frontend project (`web/`)
  - [x] 12.1 Initialize Vite + React 19 + TypeScript project in `ugsys-projects-registry/web/`
    - Create `package.json` with React 19, React Router 7, nanostores, Tailwind CSS 4, Vite 6, TypeScript 5.7, ESLint 9
    - Create `vite.config.ts` with React plugin, proxy config for local dev (`/api/v1/` → backend)
    - Create `tsconfig.json` with strict mode, path aliases (`@/` → `src/`)
    - Create `tailwind.config.ts` and `postcss.config.js`
    - Create `eslint.config.js` with TypeScript ESLint flat config
    - Create `index.html` with root div and Vite script entry
    - Create `.env.example` with `VITE_API_BASE_URL` and `VITE_AUTH_API_URL`
    - _Requirements: 22.1, 28.5, 29.1_

  - [x] 12.2 Create app shell and routing
    - Create `src/app/App.tsx` — root component with `RouterProvider`
    - Create `src/app/router.tsx` — route definitions for `/`, `/login`, `/register`, `/reset-password/:token`, `/subscribe/:projectId`, `/dashboard`
    - Create `src/app/providers.tsx` — Toast and Auth context providers
    - Create `src/pages/` placeholder page components for all routes
    - _Requirements: 22.1, 26.7_

  - [x] 12.3 Create TypeScript type definitions
    - Create `src/types/project.ts` — `Project`, `Subscription`, `ProjectImage`, `ProjectStatus`, `SubscriptionStatus`
    - Create `src/types/auth.ts` — `AuthUser`, `LoginRequest`, `RegisterRequest`, `TokenPair`, `PasswordChangeRequest`
    - Create `src/types/form.ts` — `FormSchema`, `CustomField`, `FieldType`, `FormSubmission`
    - Create `src/types/api.ts` — `ApiResponse<T>`, `ApiError`, `PaginatedResponse<T>`, `PaginatedMeta`
    - _Requirements: 28.4_

  - [x] 12.4 Create utility modules
    - Create `src/utils/dateUtils.ts` — date formatting helpers (ISO → display)
    - Create `src/utils/errorHandling.ts` — API error envelope → toast message mapping
    - Create `src/utils/sanitize.ts` — HTML/XSS sanitization for user-provided text
    - Create `src/utils/logger.ts` — structured console logger (dev only, no-op in prod)
    - _Requirements: 25.8, 22.6_

- [x] 13. Implement shared services layer
  - [x] 13.1 Implement `httpClient.ts`
    - Singleton HTTP client wrapping `fetch`
    - Automatic `Authorization: Bearer <token>` injection from auth store
    - `X-Request-ID` header (UUID v4) on every request
    - 401 interceptor: attempt one token refresh → retry → force logout on failure
    - Response parsing: unwrap `{ data, meta }` envelope on success, extract `{ error, message }` on failure
    - 15-second request timeout
    - Base URL from `VITE_API_BASE_URL` env var
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5, 28.6_

  - [x] 13.2 Implement `authService.ts`
    - `login(email, password)` → `POST /api/v1/auth/login`
    - `register(data)` → `POST /api/v1/auth/register`
    - `refreshToken(refreshToken)` → `POST /api/v1/auth/refresh`
    - `forgotPassword(email)` → `POST /api/v1/auth/forgot-password`
    - `resetPassword(token, newPassword)` → `POST /api/v1/auth/reset-password`
    - `changePassword(currentPassword, newPassword)` → `POST /api/v1/auth/change-password`
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.6_

  - [x] 13.3 Implement `projectApi.ts`
    - `getPublicProjects(page, pageSize)` → `GET /api/v1/projects/public`
    - `getProject(id)` → `GET /api/v1/projects/{id}`
    - `getProjectEnhanced(id)` → `GET /api/v1/projects/{id}/enhanced`
    - _Requirements: 22.1, 24.1_

  - [x] 13.4 Implement `subscriptionApi.ts`
    - `subscribe(projectId)` → `POST /api/v1/projects/{id}/subscriptions`
    - `checkSubscription(personId, projectId)` → `POST /api/v1/subscriptions/check`
    - `getMySubscriptions(personId)` → `GET /api/v1/subscriptions/person/{id}`
    - `publicCheckEmail(email)` → `POST /api/v1/public/check-email`
    - `publicSubscribe(data)` → `POST /api/v1/public/subscribe`
    - `publicRegister(data)` → `POST /api/v1/public/register`
    - _Requirements: 23.2, 23.3, 23.4, 24.2, 26.1_

  - [x] 13.5 Implement `formApi.ts`
    - `submitForm(projectId, personId, responses)` → `POST /api/v1/form-submissions`
    - _Requirements: 27.5_

- [x] 14. Implement auth store and auth flows
  - [x] 14.1 Implement `authStore.ts` (nanostores)
    - `$user` atom, `$isLoading` atom, `$isAuthenticated` computed
    - `initializeAuth()` — read tokens from localStorage, validate expiry, set `$user` from token claims
    - `login(email, password)` — call authService, store tokens, set `$user`
    - `logout()` — clear localStorage, set `$user` to null, redirect to `/`
    - _Requirements: 25.1, 25.5, 25.6, 25.7_

  - [x] 14.2 Implement `toastStore.ts`
    - Toast notification queue with auto-dismiss (5 seconds)
    - Support for success, error, warning, info types
    - _Requirements: 22.6, 24.4_

  - [x] 14.3 Implement `useAuth.ts` hook
    - Wraps authStore atoms for React component consumption
    - _Requirements: 25.1_

  - [x] 14.4 Implement `useProtectedRoute.ts` hook
    - Check `$isAuthenticated`, redirect to `/login?redirect=<current_path>` if false
    - _Requirements: 26.7_

  - [x] 14.5 Implement `LoginPage.tsx` and `LoginForm` component
    - Email + password form, calls `login()` from auth store
    - Redirect to `/dashboard` (or `redirect` query param) on success
    - Display API error messages on failure
    - _Requirements: 25.1_

  - [x] 14.6 Implement `RegisterPage.tsx` and `RegisterForm` component
    - Email, full name, password form
    - Calls `authService.register()`, redirects to `/login` on success
    - _Requirements: 25.2_

  - [x] 14.7 Implement `ForgotPasswordModal` component
    - Email input, calls `authService.forgotPassword()`
    - Displays "check your email" message on success
    - _Requirements: 25.3_

  - [x] 14.8 Implement `ResetPasswordPage.tsx`
    - New password form, reads token from URL params
    - Calls `authService.resetPassword()`, redirects to `/login` on success
    - _Requirements: 25.4_

- [x] 15. Implement project showcase page
  - [x] 15.1 Implement `ProjectCard` component
    - Displays project name, description (truncated), category badge, participant count, date range, status badge, thumbnail image
    - Subscribe button (navigates to `/subscribe/:projectId` if unauthenticated, calls API if authenticated)
    - _Requirements: 22.3, 22.4, 24.1_

  - [x] 15.2 Implement `ProjectGrid`, `ProjectList`, `ProjectCompact` view components
    - Grid: 3-column responsive card layout
    - List: full-width rows with expanded details
    - Compact: dense table-like rows
    - _Requirements: 22.2_

  - [x] 15.3 Implement `ViewToggle` component
    - Toggle between grid/list/compact, persist selection in `localStorage`
    - _Requirements: 22.2_

  - [x] 15.4 Implement `usePagination` hook
    - Generic pagination logic with page, pageSize, total, totalPages
    - _Requirements: 22.5_

  - [x] 15.5 Implement `useProjects` hook
    - Fetches projects from `projectApi.getPublicProjects()` with pagination
    - Loading state, error state, retry function
    - _Requirements: 22.1, 22.6_

  - [x] 15.6 Implement `HomePage.tsx`
    - Compose ProjectShowcase with ViewToggle, Pagination, and project view components
    - Error state with retry button
    - Accessible: ARIA labels, keyboard navigation
    - _Requirements: 22.1, 22.5, 22.6, 22.7_

- [x] 16. Implement subscription flows
  - [x] 16.1 Implement `DynamicFormRenderer` component
    - Renders `FormSchema` fields as appropriate inputs: text → input, textarea → textarea, poll_single → radio group, poll_multiple → checkbox group, date → date input, number → number input
    - Required field indicators and client-side validation
    - Inline error display for API validation errors
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6_

  - [x] 16.2 Implement `SubscriptionForm` component
    - For unauthenticated users: email, first name, last name, notes fields + dynamic form
    - For authenticated users: notes field + dynamic form only
    - Client-side validation of required fields before submission
    - _Requirements: 23.1, 23.8, 24.3_

  - [x] 16.3 Implement `SubscribePage.tsx`
    - Fetches project detail via `projectApi.getProjectEnhanced()`
    - Renders project info + SubscriptionForm
    - Implements public subscription flow: check-email → subscribe/check-subscription → display result
    - Implements authenticated subscription flow: direct subscribe
    - Success/error toast notifications
    - _Requirements: 23.2, 23.3, 23.4, 23.5, 23.6, 23.9, 24.2, 24.4, 24.5, 24.6_

- [x] 17. Implement user dashboard
  - [x] 17.1 Implement `SubscriptionList` component
    - Displays enriched subscription cards: project name, project status, subscription status badge, subscription date
    - Click navigates to project detail
    - _Requirements: 26.1, 26.2_

  - [x] 17.2 Implement `ProfileSection` component
    - Displays user name and email from auth store
    - _Requirements: 26.3_

  - [x] 17.3 Implement `PasswordChange` component
    - Current password + new password form
    - Calls `authService.changePassword()`
    - Success toast on success, error display on failure
    - _Requirements: 26.4, 26.5, 26.6_

  - [x] 17.4 Implement `DashboardPage.tsx`
    - Protected route (redirects to login if unauthenticated)
    - Compose SubscriptionList, ProfileSection, PasswordChange
    - _Requirements: 26.1, 26.7_

- [x] 18. Implement shared UI components
  - [x] 18.1 Implement `Button`, `Modal`, `Toast`, `LoadingSpinner` base components
    - Accessible: proper ARIA attributes, keyboard support, focus management
    - _Requirements: 22.7_

  - [x] 18.2 Implement `Pagination` component
    - Page navigation with previous/next, page numbers
    - _Requirements: 22.5_

  - [x] 18.3 Implement `Toast` notification system
    - Reads from `toastStore`, auto-dismiss after 5 seconds
    - Success, error, warning, info variants
    - _Requirements: 24.4, 26.5_

- [x] 19. Frontend CI/CD
  - [x] 19.1 Create `.github/workflows/ci-frontend.yml`
    - Triggers: push to `feature/**`, PR to `main` (only when `web/` files change)
    - Jobs: `lint` (ESLint), `typecheck` (tsc --noEmit), `build` (vite build), `lighthouse` (Lighthouse CI, perf ≥ 80, a11y ≥ 90 — advisory), `secret-scan` (Gitleaks)
    - Lint, typecheck, and build block merge on failure
    - _Requirements: 30.1, 30.2, 30.3, 30.5_

  - [x] 19.2 Create `.github/workflows/deploy-frontend.yml`
    - Triggers: merge to `main` (only when `web/` files change)
    - Steps: install deps, `vite build`, upload `web/dist/` to S3 `ugsys-frontend-{env}`, invalidate CloudFront cache
    - OIDC auth — no static AWS keys
    - _Requirements: 29.2, 30.4_

  - [x] 19.3 Add frontend targets to `justfile`
    - `web-install`: `cd web && npm install`
    - `web-dev`: `cd web && npm run dev`
    - `web-lint`: `cd web && npm run lint`
    - `web-typecheck`: `cd web && npm run typecheck`
    - `web-build`: `cd web && npm run build`
    - _Requirements: 30.1_

- [x] 20. Frontend deployment infrastructure
  - [x] 20.1 Add S3 bucket and CloudFront distribution to CDK stack
    - S3 bucket `ugsys-frontend-{env}` with OAC (Origin Access Control) for CloudFront
    - CloudFront distribution at `cbba.cloud.org.bo` with ACM certificate
    - Custom error response: 403/404 → `/index.html` (200) for SPA routing
    - Cache behaviors: `/assets/*` → 1 year immutable; default → no-cache
    - CSP response header via CloudFront response headers policy
    - _Requirements: 29.2, 29.3, 29.4, 29.5, 29.6_

- [ ] 21. Final frontend checkpoint
  - Run `npm run lint`, `npm run typecheck`, `npm run build` in `web/`
  - Verify all pages render correctly with mock data
  - Verify auth flow works end-to-end (login → dashboard → logout)
  - Verify public subscription flow works end-to-end
  - Verify dynamic form rendering for all field types
  - Ensure all tests pass, ask the user if questions arise

- [x] 22. Update deploy workflow for container image packaging
  - [x] 22.1 Create `Dockerfile.lambda` at repo root
    - Base image: `public.ecr.aws/lambda/python:3.13`
    - Install deps via `uv pip install --system`
    - Entry point: `handler.handler`
    - _Requirements: 16.2_

  - [x] 22.2 Update `.github/workflows/deploy.yml` for ECR container deploy
    - Add `ECR_REGISTRY: 142728997126.dkr.ecr.us-east-1.amazonaws.com` and `ECR_REPOSITORY: ugsys-projects-registry` as workflow env vars (not secrets)
    - Steps: OIDC auth → ECR login → `docker build -f Dockerfile.lambda` → tag `main-{short-sha}` + `latest` → push → `aws lambda update-function-code --image-uri`
    - Slack notify on success/failure via `slackapi/slack-github-action@v2.0.0`, channel `C0AE6QV0URH`, username `ugsys CI/CD`
    - _Requirements: 16.2, 16.5_
