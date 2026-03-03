# Requirements Document

## Introduction

A one-off data migration script to move project records from the legacy `ProjectsTableV2` DynamoDB table into the new `ugsys-projects-prod` DynamoDB table. The script handles schema transformation (camelCase → snake_case), composite key construction, GSI attribute population, migration metadata tagging, idempotency, dry-run preview, and AWS profile selection. It lives in `ugsys-projects-registry/scripts/` and is run manually by an operator.

## Glossary

- **Migration_Script**: The standalone Python script `scripts/migrate_projects_v2_to_ugsys.py`.
- **Source_Table**: The legacy DynamoDB table `ProjectsTableV2` containing projects in camelCase schema.
- **Target_Table**: The new DynamoDB table `ugsys-projects-prod` using snake_case schema with composite PK/SK and GSI attributes.
- **Old_Item**: A DynamoDB item read from the Source_Table.
- **New_Item**: A DynamoDB item ready to be written to the Target_Table, produced by mapping an Old_Item.
- **Dry_Run**: An execution mode where the Migration_Script reads and transforms data but performs no writes to the Target_Table.
- **Operator**: The person running the Migration_Script from a terminal.
- **Migration_Summary**: The final report printed by the Migration_Script showing total, written, skipped, and failed counts.

## Requirements

### Requirement 1: Source Table Scan

**User Story:** As an Operator, I want the Migration_Script to read all projects from the Source_Table, so that no records are missed during migration.

#### Acceptance Criteria

1. WHEN the Migration_Script runs, THE Migration_Script SHALL scan the Source_Table using paginated `scan` calls, following `LastEvaluatedKey` until all pages are exhausted.
2. IF the Source_Table scan returns a `ClientError`, THEN THE Migration_Script SHALL log the error with the DynamoDB error code and exit with a non-zero status code.
3. THE Migration_Script SHALL log the total number of items retrieved from the Source_Table before processing begins.

---

### Requirement 2: Field Mapping — camelCase to snake_case

**User Story:** As an Operator, I want the Migration_Script to transform old-schema fields into the new schema, so that migrated records are compatible with the `ugsys-projects-registry` service.

#### Acceptance Criteria

1. WHEN an Old_Item is mapped, THE Migration_Script SHALL produce a New_Item containing all required fields: `PK`, `SK`, `id`, `name`, `description`, `status`, `is_enabled`, `max_participants`, `current_participants`, `created_by`, `created_at`, `updated_at`.
2. WHEN an Old_Item is mapped, THE Migration_Script SHALL rename `isEnabled` → `is_enabled`, `createdAt` → `created_at`, `startDate` → `start_date`, `endDate` → `end_date`, `createdBy` → `created_by`, `currentParticipants` → `current_participants`, `maxParticipants` → `max_participants`, `notificationEmails` → `notification_emails`.
3. WHEN an Old_Item contains `notificationEmails` stored as a DynamoDB `SS` (StringSet), THE Migration_Script SHALL write `notification_emails` to the New_Item as a DynamoDB `SS` attribute with the same values — no type conversion is required.
3. WHEN an Old_Item contains `enableSubscriptionNotifications`, THE Migration_Script SHALL map it to `enable_subscription_notifications` in the New_Item.
4. WHEN an Old_Item contains `registrationEndDate`, THE Migration_Script SHALL omit that field from the New_Item.
5. WHEN an Old_Item field is absent or null, THE Migration_Script SHALL apply a safe default value: `is_enabled` defaults to `false`, `current_participants` defaults to `0`, `max_participants` defaults to `0`.
6. THE Migration_Script SHALL set `PK` to `PROJECT#<id>` and `SK` to `PROJECT` for every New_Item.

---

### Requirement 3: GSI Attribute Population

**User Story:** As an Operator, I want the Migration_Script to write the correct GSI attributes, so that the migrated records are queryable via the `status-index` and `created_by-index` GSIs.

#### Acceptance Criteria

1. WHEN a New_Item is constructed, THE Migration_Script SHALL set `GSI1PK` to `STATUS#<status>` and `GSI1SK` to the value of `created_at`.
2. WHEN a New_Item is constructed and `created_by` is non-empty, THE Migration_Script SHALL set `GSI2PK` to `OWNER#<created_by>` and `GSI2SK` to the value of `created_at`.

---

### Requirement 4: Migration Metadata

**User Story:** As an Operator, I want every migrated record to be tagged with its origin, so that migrated data can be identified and audited after the migration.

#### Acceptance Criteria

1. WHEN a New_Item is constructed, THE Migration_Script SHALL set `migrated_from` to the string `"registry"`.
2. WHEN a New_Item is constructed, THE Migration_Script SHALL set `migrated_at` to the current UTC timestamp in ISO 8601 format.

---

### Requirement 5: Idempotency

**User Story:** As an Operator, I want the Migration_Script to be safely re-runnable, so that re-executing the script after a partial failure does not create duplicate records.

#### Acceptance Criteria

1. BEFORE writing a New_Item, THE Migration_Script SHALL check whether an item with the same `PK` and `SK` already exists in the Target_Table.
2. WHEN an item already exists in the Target_Table, THE Migration_Script SHALL skip that item and increment the skipped counter.
3. THE Migration_Script SHALL use `ConditionExpression="attribute_not_exists(PK)"` on `put_item` calls as a secondary idempotency guard.
4. WHEN a `ConditionalCheckFailedException` is returned by DynamoDB, THE Migration_Script SHALL treat the item as already migrated, increment the skipped counter, and continue processing remaining items.

---

### Requirement 6: Per-Item Write

**User Story:** As an Operator, I want the Migration_Script to write each record individually, so that failures are attributed to a specific item and the script remains simple to reason about.

#### Acceptance Criteria

1. THE Migration_Script SHALL write each New_Item to the Target_Table using an individual `put_item` call with `ConditionExpression="attribute_not_exists(PK)"`.
2. WHEN a `put_item` call raises a `ClientError` other than `ConditionalCheckFailedException`, THE Migration_Script SHALL log the item's `id` and the DynamoDB error code, increment the failed counter, and continue processing the next item.
3. THE Migration_Script SHALL NOT use `batch_write_item` — per-item writes are required for precise error attribution.

---

### Requirement 7: Dry-Run Mode

**User Story:** As an Operator, I want to preview the migration without writing any data, so that I can verify the field mapping before committing changes to the Target_Table.

#### Acceptance Criteria

1. WHEN the `--dry-run` flag is provided, THE Migration_Script SHALL read and transform all items from the Source_Table without performing any `put_item` calls.
2. WHEN the `--dry-run` flag is provided, THE Migration_Script SHALL log each transformed New_Item's `id`, `status`, and `is_enabled` value to stdout.
3. WHEN the `--dry-run` flag is provided, THE Migration_Script SHALL print the Migration_Summary with `written=0` and all items counted as `skipped`.

---

### Requirement 8: AWS Profile Selection

**User Story:** As an Operator, I want to specify the AWS profile to use, so that the Migration_Script authenticates with the correct AWS account.

#### Acceptance Criteria

1. THE Migration_Script SHALL accept a `--profile` CLI argument that sets the AWS named profile for the boto3 session.
2. WHEN `--profile` is not provided, THE Migration_Script SHALL use the default AWS credential chain.
3. IF the specified AWS profile does not exist, THEN THE Migration_Script SHALL print a descriptive error message and exit with a non-zero status code.

---

### Requirement 9: Progress Logging and Final Summary

**User Story:** As an Operator, I want clear progress output during and after the migration, so that I can monitor progress and confirm the outcome.

#### Acceptance Criteria

1. THE Migration_Script SHALL log a progress message for each item processed, indicating whether the item was written, skipped, or failed, along with the item's `id`.
2. WHEN all items have been processed, THE Migration_Script SHALL print a Migration_Summary containing: total items scanned, items written, items skipped, and items failed.
3. WHEN one or more items failed, THE Migration_Script SHALL exit with status code `1`.
4. WHEN all items were written or skipped with zero failures, THE Migration_Script SHALL exit with status code `0`.
5. THE Migration_Script SHALL NOT log the full DynamoDB item contents at INFO level to avoid exposing data in terminal output; item `id` and status fields are sufficient.
