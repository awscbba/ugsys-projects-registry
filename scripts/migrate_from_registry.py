#!/usr/bin/env python3
"""Migration script: Registry PostgreSQL → ugsys-projects-registry DynamoDB.

Usage:
    REGISTRY_DB_URL=postgresql://... python scripts/migrate_from_registry.py

Environment variables:
    REGISTRY_DB_URL     PostgreSQL connection URL for the Registry database
    AWS_REGION          AWS region (default: us-east-1)
    PROJECTS_TABLE      DynamoDB projects table name
    SUBSCRIPTIONS_TABLE DynamoDB subscriptions table name
    FORM_SUBMISSIONS_TABLE DynamoDB form submissions table name
    DRY_RUN             Set to "true" to skip DynamoDB writes (default: false)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logging — plain text for migration script (not structlog JSON)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("migrate")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REGISTRY_DB_URL = os.environ.get("REGISTRY_DB_URL", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PROJECTS_TABLE = os.environ.get("PROJECTS_TABLE", "ugsys-projects-prod")
SUBSCRIPTIONS_TABLE = os.environ.get("SUBSCRIPTIONS_TABLE", "ugsys-subscriptions-prod")
FORM_SUBMISSIONS_TABLE = os.environ.get("FORM_SUBMISSIONS_TABLE", "ugsys-form-submissions-prod")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Summary tracking
# ---------------------------------------------------------------------------
@dataclass
class MigrationSummary:
    entity_type: str
    total: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def log(self) -> None:
        logger.info(
            "migration.summary",
            extra={
                "entity_type": self.entity_type,
                "total": self.total,
                "written": self.written,
                "skipped": self.skipped,
                "failed": self.failed,
            },
        )
        logger.info(
            f"[{self.entity_type}] total={self.total} written={self.written} "
            f"skipped={self.skipped} failed={self.failed}"
        )
        for err in self.errors[:10]:  # cap error output
            logger.warning(f"  error: {err}")


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------
def get_dynamodb_client() -> Any:
    return boto3.client("dynamodb", region_name=AWS_REGION)


def item_exists(client: Any, table_name: str, pk: str, sk: str) -> bool:
    """Check if an item with the given PK/SK already exists (idempotency check)."""
    try:
        response = client.get_item(
            TableName=table_name,
            Key={"PK": {"S": pk}, "SK": {"S": sk}},
            ProjectionExpression="PK",
        )
        return "Item" in response
    except ClientError as e:
        logger.error(f"DynamoDB get_item failed: {e}")
        return False


def put_item(client: Any, table_name: str, item: dict[str, Any]) -> bool:
    """Write item to DynamoDB. Returns True on success, False on failure."""
    if DRY_RUN:
        logger.debug(f"[DRY RUN] Would write to {table_name}: {item.get('PK', {}).get('S')}")
        return True
    try:
        client.put_item(
            TableName=table_name,
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Already exists — idempotent skip
            return False
        logger.error(f"DynamoDB put_item failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Field mapping helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def to_s(value: Any) -> dict[str, str]:
    return {"S": str(value)}


def to_bool(value: Any) -> dict[str, bool]:
    return {"BOOL": bool(value)}


def to_n(value: Any) -> dict[str, str]:
    return {"N": str(value)}


# ---------------------------------------------------------------------------
# Project migration
# ---------------------------------------------------------------------------
def map_project(row: dict[str, Any]) -> dict[str, Any]:
    """Map Registry project row → DynamoDB item."""
    project_id = str(row["id"])
    return {
        "PK": to_s(f"PROJECT#{project_id}"),
        "SK": to_s("PROJECT"),
        "id": to_s(project_id),
        "name": to_s(row.get("name", "")),
        "description": to_s(row.get("description", "")),
        "category": to_s(row.get("category", "general")),
        "status": to_s(row.get("status", "pending")),
        "is_enabled": to_bool(row.get("is_enabled", True)),
        "created_by": to_s(row.get("created_by", row.get("owner_id", "migrated"))),
        "current_participants": to_n(row.get("current_participants", 0)),
        "created_at": to_s(row.get("created_at", now_iso())),
        "updated_at": to_s(row.get("updated_at", now_iso())),
        "migrated_from": to_s("registry"),
        "migrated_at": to_s(now_iso()),
        "registry_original_id": to_s(project_id),
        # Optional fields
        **({} if not row.get("start_date") else {"start_date": to_s(str(row["start_date"]))}),
        **({} if not row.get("end_date") else {"end_date": to_s(str(row["end_date"]))}),
        **({} if not row.get("max_participants") else {"max_participants": to_n(row["max_participants"])}),
        **({} if not row.get("rich_text") else {"rich_text": to_s(row["rich_text"])}),
        **({} if not row.get("notification_emails") else {
            "notification_emails": {"SS": list(row["notification_emails"])}
        }),
    }


def migrate_projects(
    pg_conn: Any, dynamodb: Any, summary: MigrationSummary
) -> None:
    cursor = pg_conn.cursor()
    cursor.execute("SELECT * FROM projects ORDER BY created_at")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    for row_tuple in rows:
        row = dict(zip(columns, row_tuple, strict=False))
        summary.total += 1
        project_id = str(row["id"])
        pk = f"PROJECT#{project_id}"

        try:
            if item_exists(dynamodb, PROJECTS_TABLE, pk, "PROJECT"):
                logger.warning(f"projects: skipping existing {project_id}")
                summary.skipped += 1
                continue

            item = map_project(row)
            result = put_item(dynamodb, PROJECTS_TABLE, item)
            if result:
                summary.written += 1
                logger.info(f"projects: wrote {project_id}")
            else:
                summary.skipped += 1
        except Exception as e:
            summary.failed += 1
            summary.errors.append(f"{project_id}: {e}")
            logger.error(f"projects: failed {project_id}: {e}")


# ---------------------------------------------------------------------------
# Subscription migration
# ---------------------------------------------------------------------------
def map_subscription(row: dict[str, Any]) -> dict[str, Any]:
    """Map Registry subscription row → DynamoDB item."""
    sub_id = str(row["id"])
    person_id = str(row.get("person_id", row.get("user_id", "")))
    project_id = str(row.get("project_id", ""))
    return {
        "PK": to_s(f"SUBSCRIPTION#{sub_id}"),
        "SK": to_s("SUBSCRIPTION"),
        "id": to_s(sub_id),
        "project_id": to_s(project_id),
        "person_id": to_s(person_id),
        "status": to_s(row.get("status", "pending")),
        "person_project_key": to_s(f"{person_id}#{project_id}"),
        "created_at": to_s(row.get("created_at", now_iso())),
        "updated_at": to_s(row.get("updated_at", now_iso())),
        "migrated_from": to_s("registry"),
        "migrated_at": to_s(now_iso()),
        "registry_original_id": to_s(sub_id),
        **({} if not row.get("notes") else {"notes": to_s(row["notes"])}),
    }


def migrate_subscriptions(
    pg_conn: Any, dynamodb: Any, summary: MigrationSummary
) -> None:
    cursor = pg_conn.cursor()
    cursor.execute("SELECT * FROM subscriptions ORDER BY created_at")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    for row_tuple in rows:
        row = dict(zip(columns, row_tuple, strict=False))
        summary.total += 1
        sub_id = str(row["id"])
        pk = f"SUBSCRIPTION#{sub_id}"

        try:
            if item_exists(dynamodb, SUBSCRIPTIONS_TABLE, pk, "SUBSCRIPTION"):
                logger.warning(f"subscriptions: skipping existing {sub_id}")
                summary.skipped += 1
                continue

            item = map_subscription(row)
            result = put_item(dynamodb, SUBSCRIPTIONS_TABLE, item)
            if result:
                summary.written += 1
                logger.info(f"subscriptions: wrote {sub_id}")
            else:
                summary.skipped += 1
        except Exception as e:
            summary.failed += 1
            summary.errors.append(f"{sub_id}: {e}")
            logger.error(f"subscriptions: failed {sub_id}: {e}")


# ---------------------------------------------------------------------------
# Form submission migration
# ---------------------------------------------------------------------------
def map_form_submission(row: dict[str, Any]) -> dict[str, Any]:
    """Map Registry form submission row → DynamoDB item."""
    sub_id = str(row["id"])
    person_id = str(row.get("person_id", row.get("user_id", "")))
    project_id = str(row.get("project_id", ""))
    responses = row.get("responses", {})
    if isinstance(responses, str):
        try:
            responses = json.loads(responses)
        except json.JSONDecodeError:
            responses = {}
    return {
        "PK": to_s(f"FORM_SUBMISSION#{sub_id}"),
        "SK": to_s("FORM_SUBMISSION"),
        "id": to_s(sub_id),
        "project_id": to_s(project_id),
        "person_id": to_s(person_id),
        "responses": to_s(json.dumps(responses)),
        "submitted_at": to_s(row.get("submitted_at", row.get("created_at", now_iso()))),
        "migrated_from": to_s("registry"),
        "migrated_at": to_s(now_iso()),
        "registry_original_id": to_s(sub_id),
    }


def migrate_form_submissions(
    pg_conn: Any, dynamodb: Any, summary: MigrationSummary
) -> None:
    cursor = pg_conn.cursor()
    # Table may not exist in all Registry versions — handle gracefully
    try:
        cursor.execute("SELECT * FROM form_submissions ORDER BY submitted_at")
    except Exception:
        try:
            cursor.execute("SELECT * FROM form_submissions ORDER BY created_at")
        except Exception as e:
            logger.warning(f"form_submissions table not found or empty: {e}")
            return

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    for row_tuple in rows:
        row = dict(zip(columns, row_tuple, strict=False))
        summary.total += 1
        fs_id = str(row["id"])
        pk = f"FORM_SUBMISSION#{fs_id}"

        try:
            if item_exists(dynamodb, FORM_SUBMISSIONS_TABLE, pk, "FORM_SUBMISSION"):
                logger.warning(f"form_submissions: skipping existing {fs_id}")
                summary.skipped += 1
                continue

            item = map_form_submission(row)
            result = put_item(dynamodb, FORM_SUBMISSIONS_TABLE, item)
            if result:
                summary.written += 1
                logger.info(f"form_submissions: wrote {fs_id}")
            else:
                summary.skipped += 1
        except Exception as e:
            summary.failed += 1
            summary.errors.append(f"{fs_id}: {e}")
            logger.error(f"form_submissions: failed {fs_id}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    if not REGISTRY_DB_URL:
        logger.error("REGISTRY_DB_URL environment variable is required")
        return 1

    if DRY_RUN:
        logger.info("DRY RUN mode — no DynamoDB writes will be performed")

    logger.info(
        f"Starting migration: Registry → ugsys-projects-registry "
        f"(region={AWS_REGION}, dry_run={DRY_RUN})"
    )

    # Connect to PostgreSQL
    try:
        import psycopg2  # type: ignore[import-untyped]
        pg_conn = psycopg2.connect(REGISTRY_DB_URL)
        logger.info("Connected to Registry PostgreSQL")
    except Exception as e:
        logger.error(f"Failed to connect to Registry PostgreSQL: {e}")
        return 1

    dynamodb = get_dynamodb_client()

    summaries: list[MigrationSummary] = []

    # Migrate in dependency order: projects → subscriptions → form_submissions
    projects_summary = MigrationSummary("projects")
    migrate_projects(pg_conn, dynamodb, projects_summary)
    summaries.append(projects_summary)

    subscriptions_summary = MigrationSummary("subscriptions")
    migrate_subscriptions(pg_conn, dynamodb, subscriptions_summary)
    summaries.append(subscriptions_summary)

    form_submissions_summary = MigrationSummary("form_submissions")
    migrate_form_submissions(pg_conn, dynamodb, form_submissions_summary)
    summaries.append(form_submissions_summary)

    pg_conn.close()

    # Print final summary
    logger.info("=" * 60)
    logger.info("MIGRATION COMPLETE")
    logger.info("=" * 60)
    for s in summaries:
        s.log()

    total_failed = sum(s.failed for s in summaries)
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
