# Implementation Plan: data-migration-projects

## Overview

Implement the standalone migration script `scripts/migrate_projects_v2_to_ugsys.py` using TDD: unit tests first, then implementation, then property-based tests. No FastAPI, no domain layer — pure sync `boto3`.

## Tasks

- [x] 1. Write unit tests for `map_item`
  - [x] 1.1 Test fully-populated Old_Item maps all required output fields
    - Assert `PK`, `SK`, `id`, `name`, `description`, `status`, `is_enabled`, `current_participants`, `max_participants`, `created_by`, `created_at`, `updated_at`, `GSI1PK`, `GSI1SK`, `migrated_from`, `migrated_at` all present
    - Assert camelCase → snake_case renames: `isEnabled` → `is_enabled`, `createdAt` → `created_at`, `createdBy` → `created_by`, `currentParticipants` → `current_participants`, `maxParticipants` → `max_participants`
    - Assert `PK = "PROJECT#<id>"` and `SK = "PROJECT"`
    - _Requirements: 2.1, 2.2, 2.6_

  - [x] 1.2 Test missing optional fields apply safe defaults
    - Old_Item without `isEnabled` → `is_enabled = {"BOOL": False}`
    - Old_Item without `currentParticipants` → `current_participants = {"N": "0"}`
    - Old_Item without `maxParticipants` → `max_participants = {"N": "0"}`
    - _Requirements: 2.5_

  - [x] 1.3 Test `notificationEmails` SS passthrough
    - Old_Item with `notificationEmails: {"SS": ["a@b.com", "c@d.com"]}` → `notification_emails: {"SS": ["a@b.com", "c@d.com"]}` with no type conversion
    - _Requirements: 2.3_

  - [x] 1.4 Test `registrationEndDate` is omitted from output
    - Old_Item with `registrationEndDate` present → assert neither `registrationEndDate` nor `registration_end_date` key exists in New_Item
    - _Requirements: 2.4_

  - [x] 1.5 Test GSI attribute construction
    - Assert `GSI1PK = "STATUS#<status>"` and `GSI1SK = created_at`
    - Old_Item with non-empty `createdBy` → assert `GSI2PK = "OWNER#<created_by>"` and `GSI2SK = created_at`
    - Old_Item with empty/absent `createdBy` → assert `GSI2PK` and `GSI2SK` absent from New_Item
    - _Requirements: 3.1, 3.2_

  - [x] 1.6 Test migration metadata fields
    - Assert `migrated_from = {"S": "registry"}` on every New_Item
    - Assert `migrated_at` is present and its value parses as ISO 8601
    - _Requirements: 4.1, 4.2_

- [x] 2. Write unit tests for `write_item`
  - [x] 2.1 Test dry-run mode skips `put_item`
    - Call `write_item` with `dry_run=True`; assert `put_item` never called and result is `WriteResult.SKIPPED`
    - _Requirements: 7.1, 7.3_

  - [x] 2.2 Test pre-check skip when item already exists
    - Mock `item_exists` returning `True`; assert `put_item` never called and result is `WriteResult.SKIPPED`
    - _Requirements: 5.1, 5.2_

  - [x] 2.3 Test `ConditionalCheckFailedException` treated as skipped
    - Mock `put_item` raising `ClientError` with code `ConditionalCheckFailedException`; assert result is `WriteResult.SKIPPED`
    - _Requirements: 5.3, 5.4_

  - [x] 2.4 Test other `ClientError` increments failed
    - Mock `put_item` raising `ClientError` with code `ProvisionedThroughputExceededException`; assert result is `WriteResult.FAILED`
    - _Requirements: 6.2_

- [x] 3. Write unit tests for `scan_source`, `build_session`, and exit code logic
  - [x] 3.1 Test `scan_source` exits on `ClientError`
    - Mock `scan` raising `ClientError`; assert `SystemExit` raised with non-zero code
    - _Requirements: 1.2_

  - [x] 3.2 Test `build_session` exits on invalid profile
    - Pass a non-existent profile name; assert `SystemExit` raised with non-zero code and descriptive message printed
    - _Requirements: 8.3_

  - [x] 3.3 Test exit code logic
    - `Counts(failed=1)` → exit code `1`
    - `Counts(failed=0)` → exit code `0`
    - _Requirements: 9.3, 9.4_

- [x] 4. Checkpoint — confirm all unit tests are RED before implementation
  - Run `uv run pytest tests/unit/scripts/test_migrate_projects_v2_to_ugsys.py -v`; all tests must fail (ImportError or AssertionError). Ask the user if questions arise.

- [x] 5. Implement the migration script
  - [x] 5.1 Scaffold `scripts/migrate_projects_v2_to_ugsys.py` with `WriteResult`, `Counts`, and `parse_args`
    - Define `WriteResult` enum (`WRITTEN`, `SKIPPED`, `FAILED`)
    - Define `Counts` dataclass with `total`, `written`, `skipped`, `failed`
    - Implement `parse_args()` with `--dry-run`, `--profile`, `--source-table`, `--target-table`, `--region`
    - _Requirements: 7.1, 8.1, 8.2_

  - [x] 5.2 Implement `build_session` and `scan_source`
    - `build_session(profile)`: create `boto3.Session`; catch `ProfileNotFound`, print descriptive error, `sys.exit(1)`
    - `scan_source(client, table)`: paginated `scan` following `LastEvaluatedKey`; catch `ClientError`, log error code, `sys.exit(1)`; log total items retrieved
    - _Requirements: 1.1, 1.2, 1.3, 8.1, 8.2, 8.3_

  - [x] 5.3 Implement `map_item`
    - Full camelCase → snake_case field mapping per the design's field mapping table
    - Composite `PK`/`SK` construction
    - GSI1 attributes always; GSI2 only when `created_by` non-empty
    - Safe defaults for absent `isEnabled`, `currentParticipants`, `maxParticipants`
    - SS passthrough for `notificationEmails`; BOOL passthrough for `enableSubscriptionNotifications`
    - Optional `startDate`/`endDate` passthrough; `registrationEndDate` intentionally omitted
    - `migrated_from = "registry"` and `migrated_at = datetime.utcnow().isoformat() + "Z"`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 4.1, 4.2_

  - [x] 5.4 Implement `item_exists` and `write_item`
    - `item_exists(client, table, pk)`: `get_item` with `PK`/`SK` keys; return `True` if `"Item"` in response
    - `write_item(client, table, item, dry_run)`: dry-run → log + return `SKIPPED`; pre-check via `item_exists` → `SKIPPED`; `put_item` with `ConditionExpression="attribute_not_exists(PK)"`; catch `ConditionalCheckFailedException` → `SKIPPED`; catch other `ClientError` → log id + error code, return `FAILED`; success → return `WRITTEN`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.2, 7.1, 7.2_

  - [x] 5.5 Implement `migrate` orchestration loop and `print_summary`
    - `migrate(args)`: build session, get DynamoDB client, scan source, loop over items calling `map_item` then `write_item`, update `Counts`, log per-item outcome with `id`; return exit code
    - `print_summary(counts)`: print total, written, skipped, failed counts
    - `if __name__ == "__main__": sys.exit(migrate(parse_args()))`
    - _Requirements: 1.3, 6.3, 7.3, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 6. Checkpoint — confirm all unit tests are GREEN
  - Run `uv run pytest tests/unit/scripts/test_migrate_projects_v2_to_ugsys.py -v`; all tests must pass. Ask the user if questions arise.

- [x] 7. Write property-based tests using `hypothesis`
  - [x]* 7.1 Property 1 — mapping completeness and correctness
    - Generate random Old_Items with all required fields; assert New_Item contains all required keys with correct names and `PK`/`SK` values
    - **Property 1: Mapping completeness and correctness**
    - **Validates: Requirements 2.1, 2.2, 2.6**

  - [x]* 7.2 Property 2 — `notificationEmails` SS passthrough
    - Generate Old_Items with random `SS` `notificationEmails`; assert `notification_emails` SS values are identical
    - **Property 2: notificationEmails SS passthrough**
    - **Validates: Requirements 2.3**

  - [x]* 7.3 Property 3 — `registrationEndDate` omission
    - Generate Old_Items with and without `registrationEndDate`; assert neither `registrationEndDate` nor `registration_end_date` appears in New_Item
    - **Property 3: registrationEndDate omission**
    - **Validates: Requirements 2.4**

  - [x]* 7.4 Property 4 — safe defaults for absent fields
    - Generate Old_Items missing `isEnabled`, `currentParticipants`, or `maxParticipants`; assert correct defaults applied
    - **Property 4: Safe defaults for absent fields**
    - **Validates: Requirements 2.5**

  - [x]* 7.5 Property 5 — GSI attributes correctly constructed
    - Generate random `status` and `created_by` values; assert `GSI1PK`/`GSI1SK`/`GSI2PK`/`GSI2SK` constructed correctly
    - **Property 5: GSI attributes are correctly constructed**
    - **Validates: Requirements 3.1, 3.2**

  - [x]* 7.6 Property 6 — migration metadata on every New_Item
    - Generate any Old_Item; assert `migrated_from == "registry"` and `migrated_at` parses as ISO 8601
    - **Property 6: Migration metadata on every New_Item**
    - **Validates: Requirements 4.1, 4.2**

  - [x]* 7.7 Property 7 — idempotency: existing items always skipped
    - Simulate N items where M already exist (mocked `item_exists`); assert `skipped == M`, `written == N-M`, `failed == 0`
    - **Property 7: Idempotency — existing items are always skipped**
    - **Validates: Requirements 5.1, 5.2, 5.4**

  - [x]* 7.8 Property 8 — per-item `put_item` writes
    - Generate N new items in non-dry-run mode; assert `put_item` called exactly N times
    - **Property 8: Per-item put_item writes**
    - **Validates: Requirements 6.1**

  - [x]* 7.9 Property 9 — dry-run produces no writes
    - Generate any item set with `dry_run=True`; assert `put_item` call count == 0
    - **Property 9: Dry-run produces no writes**
    - **Validates: Requirements 7.1**

  - [x]* 7.10 Property 10 — per-item progress log for every processed item
    - Generate any item set; assert log output contains exactly one entry per item with `id` and outcome
    - **Property 10: Per-item progress log for every processed item**
    - **Validates: Requirements 9.1**

- [x] 8. Checkpoint — confirm all tests pass
  - Run `uv run pytest tests/unit/scripts/ tests/property/scripts/ -v --hypothesis-seed=0`; all tests must pass. Ask the user if questions arise.

- [x] 9. Lint and type-check the script
  - [x] 9.1 Run ruff on the script and test files
    - `uv run ruff check scripts/migrate_projects_v2_to_ugsys.py tests/unit/scripts/ tests/property/scripts/`
    - `uv run ruff format scripts/migrate_projects_v2_to_ugsys.py tests/unit/scripts/ tests/property/scripts/`
    - Fix any reported issues
    - _Requirements: all (code quality gate)_

  - [x] 9.2 Run mypy strict on the script
    - `uv run mypy --strict scripts/migrate_projects_v2_to_ugsys.py`
    - Fix any type errors
    - _Requirements: all (type safety gate)_

- [~] 10. Dry-run verification against real AWS
  - Run `python scripts/migrate_projects_v2_to_ugsys.py --profile awscbba --dry-run` and confirm:
    - Script reads all items from `ProjectsTableV2` without error
    - Each item's `id`, `status`, and `is_enabled` are logged to stdout
    - Final summary prints `written=0` with all items counted as skipped
    - No writes are made to `ugsys-projects-prod`
  - _Requirements: 1.1, 1.3, 7.1, 7.2, 7.3_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- TDD order is strict: unit tests (tasks 1–3) must be written and confirmed RED before implementation (task 5)
- The script uses sync `boto3` — no `aioboto3`, no `asyncio`, no FastAPI imports
- `hypothesis` must be added to `pyproject.toml` dev dependencies before running property tests
- Property tests run with `--hypothesis-seed=0` for reproducibility in CI
- Task 10 requires real AWS credentials with read access to `ProjectsTableV2` and read access to `ugsys-projects-prod`
