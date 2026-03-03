# Design Document

## Overview

A standalone Python migration script that reads all project records from the legacy `ProjectsTableV2` DynamoDB table and writes them into the new `ugsys-projects-prod` table. The script transforms the old camelCase schema into the new snake_case schema, constructs composite PK/SK keys and GSI attributes, tags each record with migration metadata, and is safe to re-run (idempotent). It is invoked manually by an operator from a terminal.

The script lives at `ugsys-projects-registry/scripts/migrate_projects_v2_to_ugsys.py` and has no dependency on the FastAPI application, domain layer, or any ugsys shared library. It uses `boto3` (sync) directly.

---

## Architecture

The script is a single-file CLI tool. There is no web server, no dependency injection container, and no async runtime. All DynamoDB calls are synchronous boto3 calls.

```
┌─────────────────────────────────────────────────────────────┐
│  Operator terminal                                          │
│  python migrate_projects_v2_to_ugsys.py [--dry-run]        │
│                                          [--profile NAME]   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  migrate_projects_v2_to_ugsys.py                            │
│                                                             │
│  parse_args()          CLI argument parsing (argparse)      │
│  build_session()       boto3.Session with optional profile  │
│  scan_source()         paginated Scan on ProjectsTableV2    │
│  map_item()            Old_Item → New_Item transformation   │
│  migrate()             orchestration loop                   │
│  write_item()          put_item with ConditionExpression    │
│  print_summary()       final counts + exit code            │
└──────────┬──────────────────────────────┬───────────────────┘
           │                              │
           ▼                              ▼
  ProjectsTableV2               ugsys-projects-prod
  (Source_Table)                (Target_Table)
  boto3 DynamoDB                boto3 DynamoDB
```

### Key design decisions

- **Sync boto3, not aioboto3**: The script runs in a plain terminal, not inside an async event loop. Sync is simpler and has no drawbacks for a one-off migration.
- **Per-item `put_item`, not `batch_write_item`**: Each item is written individually so that failures are attributed to a specific item ID. This trades throughput for debuggability, which is the right trade-off for a one-off migration.
- **No domain layer imports**: The script is self-contained. Importing the FastAPI application would pull in aioboto3, lifespan, and other runtime concerns that are irrelevant here.
- **Pre-check + ConditionExpression**: Two-layer idempotency. The `get_item` pre-check avoids unnecessary write attempts; the `ConditionExpression` is the authoritative guard against races or pre-check misses.

---

## Components and Interfaces

### CLI Interface

```
usage: migrate_projects_v2_to_ugsys.py [-h] [--dry-run] [--profile PROFILE]
                                        [--source-table SOURCE_TABLE]
                                        [--target-table TARGET_TABLE]
                                        [--region REGION]

optional arguments:
  --dry-run             Read and transform items without writing to Target_Table
  --profile PROFILE     AWS named profile (default: default credential chain)
  --source-table        Source DynamoDB table name (default: ProjectsTableV2)
  --target-table        Target DynamoDB table name (default: ugsys-projects-prod)
  --region              AWS region (default: us-east-1)
```

### Functions

| Function | Signature | Responsibility |
|---|---|---|
| `parse_args` | `() -> argparse.Namespace` | Parse CLI arguments |
| `build_session` | `(profile: str \| None) -> boto3.Session` | Create boto3 session; exit on ProfileNotFound |
| `scan_source` | `(client, table: str) -> list[dict]` | Paginated scan; exit on ClientError |
| `item_exists` | `(client, table: str, pk: str) -> bool` | get_item pre-check |
| `map_item` | `(old: dict) -> dict` | Transform Old_Item → New_Item |
| `write_item` | `(client, table: str, item: dict, dry_run: bool) -> WriteResult` | put_item or dry-run skip |
| `migrate` | `(args) -> int` | Orchestration loop; returns exit code |
| `print_summary` | `(counts: Counts) -> None` | Print final Migration_Summary |

### WriteResult

```python
from enum import Enum

class WriteResult(Enum):
    WRITTEN = "written"
    SKIPPED = "skipped"
    FAILED  = "failed"
```

### Counts

```python
from dataclasses import dataclass

@dataclass
class Counts:
    total:   int = 0
    written: int = 0
    skipped: int = 0
    failed:  int = 0
```

---

## Data Models

### Field Mapping Table

| Old field (camelCase) | DynamoDB type | New field (snake_case) | DynamoDB type | Notes |
|---|---|---|---|---|
| `id` | S | `id` | S | Unchanged |
| `name` | S | `name` | S | Unchanged |
| `description` | S | `description` | S | Unchanged |
| `status` | S | `status` | S | Unchanged |
| `isEnabled` | BOOL | `is_enabled` | BOOL | Default `false` if absent |
| `createdAt` | S | `created_at` | S | ISO 8601 |
| `updatedAt` | S | `updated_at` | S | ISO 8601 |
| `startDate` | S | `start_date` | S | Optional |
| `endDate` | S | `end_date` | S | Optional |
| `createdBy` | S | `created_by` | S | Used for GSI2 |
| `currentParticipants` | N | `current_participants` | N | Default `0` if absent |
| `maxParticipants` | N | `max_participants` | N | Default `0` if absent |
| `notificationEmails` | SS | `notification_emails` | SS | No type conversion — SS passthrough |
| `enableSubscriptionNotifications` | BOOL | `enable_subscription_notifications` | BOOL | Optional |
| `registrationEndDate` | S | *(omitted)* | — | Dropped during migration |
| *(new)* | — | `PK` | S | `PROJECT#<id>` |
| *(new)* | — | `SK` | S | `PROJECT` |
| *(new)* | — | `GSI1PK` | S | `STATUS#<status>` |
| *(new)* | — | `GSI1SK` | S | value of `created_at` |
| *(new)* | — | `GSI2PK` | S | `OWNER#<created_by>` (only if `created_by` non-empty) |
| *(new)* | — | `GSI2SK` | S | value of `created_at` (only if `created_by` non-empty) |
| *(new)* | — | `migrated_from` | S | `"registry"` |
| *(new)* | — | `migrated_at` | S | UTC ISO 8601 timestamp at migration time |

### map_item logic (pseudocode)

```python
def map_item(old: dict) -> dict:
    id_val    = old["id"]["S"]
    status    = old["status"]["S"]
    created_at = old["createdAt"]["S"]
    created_by = old.get("createdBy", {}).get("S", "")

    new: dict = {
        "PK":          {"S": f"PROJECT#{id_val}"},
        "SK":          {"S": "PROJECT"},
        "id":          {"S": id_val},
        "name":        {"S": old["name"]["S"]},
        "description": {"S": old.get("description", {}).get("S", "")},
        "status":      {"S": status},
        "is_enabled":  {"BOOL": old.get("isEnabled", {}).get("BOOL", False)},
        "created_at":  {"S": created_at},
        "updated_at":  {"S": old.get("updatedAt", {}).get("S", created_at)},
        "created_by":  {"S": created_by},
        "current_participants": {"N": old.get("currentParticipants", {}).get("N", "0")},
        "max_participants":     {"N": old.get("maxParticipants", {}).get("N", "0")},
        "GSI1PK":      {"S": f"STATUS#{status}"},
        "GSI1SK":      {"S": created_at},
        "migrated_from": {"S": "registry"},
        "migrated_at":   {"S": datetime.utcnow().isoformat() + "Z"},
    }

    # Optional fields — only write if present in old item
    for old_key, new_key in [
        ("startDate", "start_date"),
        ("endDate", "end_date"),
    ]:
        if old_key in old:
            new[new_key] = old[old_key]  # S passthrough

    if "notificationEmails" in old:
        new["notification_emails"] = old["notificationEmails"]  # SS passthrough

    if "enableSubscriptionNotifications" in old:
        new["enable_subscription_notifications"] = old["enableSubscriptionNotifications"]  # BOOL passthrough

    # GSI2 — only when created_by is non-empty
    if created_by:
        new["GSI2PK"] = {"S": f"OWNER#{created_by}"}
        new["GSI2SK"] = {"S": created_at}

    # registrationEndDate is intentionally omitted

    return new
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Mapping completeness and correctness

*For any* valid Old_Item, `map_item` must return a New_Item that contains all required fields (`PK`, `SK`, `id`, `name`, `description`, `status`, `is_enabled`, `current_participants`, `max_participants`, `created_by`, `created_at`, `updated_at`, `GSI1PK`, `GSI1SK`, `migrated_from`, `migrated_at`), with all camelCase source fields renamed to their snake_case equivalents, and with `PK = "PROJECT#<id>"` and `SK = "PROJECT"`.

**Validates: Requirements 2.1, 2.2, 2.6**

### Property 2: notificationEmails SS passthrough

*For any* Old_Item containing `notificationEmails` as a DynamoDB `SS` attribute, the New_Item produced by `map_item` must contain `notification_emails` as a `SS` attribute with identical values and no type conversion.

**Validates: Requirements 2.3**

### Property 3: registrationEndDate omission

*For any* Old_Item that contains a `registrationEndDate` field, the New_Item produced by `map_item` must not contain a `registrationEndDate` or `registration_end_date` key.

**Validates: Requirements 2.4**

### Property 4: Safe defaults for absent fields

*For any* Old_Item missing `isEnabled`, `currentParticipants`, or `maxParticipants`, the New_Item must have `is_enabled = false`, `current_participants = "0"`, and `max_participants = "0"` respectively.

**Validates: Requirements 2.5**

### Property 5: GSI attributes are correctly constructed

*For any* New_Item produced by `map_item`, `GSI1PK` must equal `"STATUS#" + status` and `GSI1SK` must equal `created_at`. When `created_by` is non-empty, `GSI2PK` must equal `"OWNER#" + created_by` and `GSI2SK` must equal `created_at`.

**Validates: Requirements 3.1, 3.2**

### Property 6: Migration metadata on every New_Item

*For any* New_Item produced by `map_item`, `migrated_from` must equal the string `"registry"` and `migrated_at` must be a valid ISO 8601 UTC timestamp string.

**Validates: Requirements 4.1, 4.2**

### Property 7: Idempotency — existing items are always skipped

*For any* set of items where some already exist in the Target_Table (detected by `get_item` pre-check or `ConditionalCheckFailedException`), those items must be counted as skipped and never counted as written or failed.

**Validates: Requirements 5.1, 5.2, 5.4**

### Property 8: Per-item put_item writes

*For any* set of N new items (not already in Target_Table) processed in non-dry-run mode, exactly N individual `put_item` calls must be made — one per item.

**Validates: Requirements 6.1**

### Property 9: Dry-run produces no writes

*For any* input set of items, when the script runs with `--dry-run`, zero `put_item` calls must be made regardless of item count or content.

**Validates: Requirements 7.1**

### Property 10: Per-item progress log for every processed item

*For any* item processed by the migration loop, exactly one progress log message must be emitted containing the item's `id` and its outcome (`written`, `skipped`, or `failed`).

**Validates: Requirements 9.1**

---

## Error Handling

| Scenario | Handling |
|---|---|
| `ClientError` during Source_Table scan | Log error code + message, exit with code 1 immediately |
| `ProfileNotFound` from boto3 | Print descriptive message, exit with code 1 |
| `ConditionalCheckFailedException` on `put_item` | Treat as already migrated → increment `skipped`, continue |
| Any other `ClientError` on `put_item` | Log item `id` + DynamoDB error code, increment `failed`, continue |
| `KeyError` / `TypeError` during `map_item` | Log item `id` + exception message, increment `failed`, continue |
| `failed > 0` at end | Exit with code 1 |
| `failed == 0` at end | Exit with code 0 |

The script never surfaces raw exception tracebacks to stdout in normal operation. All error detail goes to stderr via the logger. The full DynamoDB item is never logged at INFO level — only `id` and outcome fields are logged per item.

---

## Testing Strategy

### Dual approach

Both unit tests and property-based tests are required. Unit tests cover specific examples and error paths; property tests verify universal correctness of the mapping and orchestration logic across many generated inputs.

### Unit tests (`tests/unit/scripts/test_migrate_projects_v2_to_ugsys.py`)

Focus on specific examples and error conditions:

- `map_item` with a fully-populated Old_Item → verify every output field
- `map_item` with missing optional fields → verify defaults applied
- `map_item` with `notificationEmails` SS → verify SS passthrough
- `map_item` with `registrationEndDate` present → verify field absent in output
- `map_item` with empty `created_by` → verify GSI2 keys absent
- `write_item` with `--dry-run` → verify `put_item` never called
- `write_item` when `item_exists` returns True → verify skipped, no `put_item`
- `write_item` when `put_item` raises `ConditionalCheckFailedException` → verify skipped
- `write_item` when `put_item` raises other `ClientError` → verify failed
- `scan_source` when `scan` raises `ClientError` → verify SystemExit with code 1
- `build_session` with invalid profile → verify SystemExit with code 1
- Final summary: `failed > 0` → exit code 1; `failed == 0` → exit code 0

### Property-based tests (`tests/property/scripts/test_migrate_properties.py`)

Use `hypothesis` for Python. Minimum 100 iterations per property (configured via `@settings(max_examples=100)`).

Each test is tagged with a comment referencing the design property:
```
# Feature: data-migration-projects, Property <N>: <property_text>
```

| Property | Test description |
|---|---|
| Property 1 | Generate random Old_Items with all required fields; assert New_Item has all required keys with correct names and PK/SK values |
| Property 2 | Generate Old_Items with random SS notificationEmails; assert notification_emails SS values are identical |
| Property 3 | Generate Old_Items with and without registrationEndDate; assert neither key appears in New_Item |
| Property 4 | Generate Old_Items with missing isEnabled/currentParticipants/maxParticipants; assert correct defaults |
| Property 5 | Generate random status and created_by values; assert GSI1PK/GSI1SK/GSI2PK/GSI2SK constructed correctly |
| Property 6 | Generate any Old_Item; assert migrated_from == "registry" and migrated_at parses as ISO 8601 |
| Property 7 | Simulate N items where M already exist; assert skipped == M, written == N-M, failed == 0 |
| Property 8 | Generate N new items; assert put_item called exactly N times |
| Property 9 | Generate any item set with dry_run=True; assert put_item call count == 0 |
| Property 10 | Generate any item set; assert log output contains one entry per item with id and outcome |

### Property-based testing library

`hypothesis` — already available in the Python ecosystem, no custom PBT implementation needed.

```toml
# pyproject.toml (dev dependencies)
hypothesis = ">=6.0"
```

### Running tests

```bash
# Unit tests only
uv run pytest tests/unit/scripts/ -v

# Property tests (single run, no watch mode)
uv run pytest tests/property/scripts/ -v --hypothesis-seed=0

# All migration tests
uv run pytest tests/unit/scripts/ tests/property/scripts/ -v
```
