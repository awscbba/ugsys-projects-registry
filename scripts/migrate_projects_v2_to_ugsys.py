#!/usr/bin/env python3
"""Standalone migration script: ProjectsTableV2 (DynamoDB) → ugsys-projects-prod (DynamoDB).

Transforms camelCase legacy schema to snake_case, constructs composite PK/SK and GSI
attributes, tags each record with migration metadata, and is safe to re-run (idempotent).

Usage:
    python scripts/migrate_projects_v2_to_ugsys.py [--dry-run] [--profile PROFILE]
        [--source-table SOURCE_TABLE] [--target-table TARGET_TABLE] [--region REGION]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import boto3
from botocore.exceptions import ClientError, ProfileNotFound

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class WriteResult(Enum):
    WRITTEN = "written"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class Counts:
    total: int = 0
    written: int = 0
    skipped: int = 0
    failed: int = 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate projects from ProjectsTableV2 to ugsys-projects-prod"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and transform items without writing to Target_Table",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="AWS named profile (default: default credential chain)",
    )
    parser.add_argument(
        "--source-table",
        type=str,
        default="ProjectsTableV2",
        help="Source DynamoDB table name (default: ProjectsTableV2)",
    )
    parser.add_argument(
        "--target-table",
        type=str,
        default="ugsys-projects-prod",
        help="Target DynamoDB table name (default: ugsys-projects-prod)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Session and scan
# ---------------------------------------------------------------------------


def build_session(profile: str | None) -> boto3.Session:
    """Create a boto3 Session with an optional named profile.

    Exits with code 1 if the profile does not exist.
    """
    try:
        return boto3.Session(profile_name=profile)
    except ProfileNotFound as e:
        print(
            f"ERROR: AWS profile '{profile}' not found. "
            f"Check your ~/.aws/credentials or ~/.aws/config file. Details: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


def scan_source(client: Any, table: str) -> list[dict[str, Any]]:
    """Paginated scan of the source table. Exits with code 1 on ClientError."""
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"TableName": table}

    try:
        while True:
            response = client.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    except ClientError as e:
        code = e.response["Error"]["Code"]
        print(
            f"ERROR: DynamoDB scan on '{table}' failed with code '{code}': {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Scanned {len(items)} items from '{table}'")
    return items


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


def map_item(old: dict[str, Any]) -> dict[str, Any]:
    """Transform an Old_Item (camelCase DynamoDB AttributeValue dict) into a New_Item."""
    id_val: str = old["id"]["S"]
    status: str = old["status"]["S"]
    created_at: str = old["createdAt"]["S"]
    created_by: str = old.get("createdBy", {}).get("S", "")
    updated_at: str = old.get("updatedAt", {}).get("S", created_at)

    new: dict[str, Any] = {
        "PK": {"S": f"PROJECT#{id_val}"},
        "SK": {"S": "PROJECT"},
        "id": {"S": id_val},
        "name": {"S": old["name"]["S"]},
        "description": {"S": old.get("description", {}).get("S", "")},
        "status": {"S": status},
        "is_enabled": {"BOOL": old.get("isEnabled", {}).get("BOOL", False)},
        "created_at": {"S": created_at},
        "updated_at": {"S": updated_at},
        "created_by": {"S": created_by},
        "current_participants": {"N": old.get("currentParticipants", {}).get("N", "0")},
        "max_participants": {"N": old.get("maxParticipants", {}).get("N", "0")},
        "GSI1PK": {"S": f"STATUS#{status}"},
        "GSI1SK": {"S": created_at},
        "migrated_from": {"S": "registry"},
        "migrated_at": {"S": datetime.now(UTC).isoformat().replace("+00:00", "Z")},
    }

    # Optional S passthrough fields
    for old_key, new_key in [
        ("startDate", "start_date"),
        ("endDate", "end_date"),
    ]:
        if old_key in old:
            new[new_key] = old[old_key]

    # SS passthrough — no type conversion
    if "notificationEmails" in old:
        new["notification_emails"] = old["notificationEmails"]

    # BOOL passthrough
    if "enableSubscriptionNotifications" in old:
        new["enable_subscription_notifications"] = old["enableSubscriptionNotifications"]

    # GSI2 — only when created_by is non-empty
    if created_by:
        new["GSI2PK"] = {"S": f"OWNER#{created_by}"}
        new["GSI2SK"] = {"S": created_at}

    # registrationEndDate is intentionally omitted

    return new


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def item_exists(client: Any, table: str, pk: str) -> bool:
    """Return True if an item with the given PK and SK=PROJECT already exists."""
    response = client.get_item(
        TableName=table,
        Key={"PK": {"S": pk}, "SK": {"S": "PROJECT"}},
    )
    return "Item" in response


def write_item(client: Any, table: str, item: dict[str, Any], dry_run: bool) -> WriteResult:
    """Write a single item to the target table.

    Returns WriteResult.SKIPPED for dry-run or already-existing items,
    WriteResult.FAILED for unexpected errors, WriteResult.WRITTEN on success.
    """
    item_id: str = item.get("id", {}).get("S", "<unknown>")

    if dry_run:
        is_enabled = item.get("is_enabled", {}).get("BOOL", False)
        status = item.get("status", {}).get("S", "")
        print(f"[DRY RUN] id={item_id} status={status} is_enabled={is_enabled}")
        return WriteResult.SKIPPED

    pk: str = item["PK"]["S"]
    if item_exists(client, table, pk):
        print(f"skipping existing: {item_id}")
        return WriteResult.SKIPPED

    try:
        client.put_item(
            TableName=table,
            Item=item,
            ConditionExpression="attribute_not_exists(PK)",
        )
        return WriteResult.WRITTEN
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "ConditionalCheckFailedException":
            print(f"already exists (race): {item_id}")
            return WriteResult.SKIPPED
        print(f"ERROR: put_item failed for id={item_id} code={code}", file=sys.stderr)
        return WriteResult.FAILED


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def print_summary(counts: Counts) -> None:
    print("=" * 50)
    print("Migration Summary")
    print("=" * 50)
    print(f"  Total:   {counts.total}")
    print(f"  Written: {counts.written}")
    print(f"  Skipped: {counts.skipped}")
    print(f"  Failed:  {counts.failed}")
    print("=" * 50)


def migrate(args: argparse.Namespace) -> int:
    session = build_session(args.profile)
    client = session.client("dynamodb", region_name=args.region)

    items = scan_source(client, args.source_table)
    counts = Counts(total=len(items))

    for old_item in items:
        item_id = old_item.get("id", {}).get("S", "<unknown>")
        try:
            new_item = map_item(old_item)
        except (KeyError, TypeError) as e:
            print(f"ERROR: map_item failed for id={item_id}: {e}", file=sys.stderr)
            counts.failed += 1
            continue

        result = write_item(client, args.target_table, new_item, args.dry_run)

        if result is WriteResult.WRITTEN:
            counts.written += 1
            print(f"written: {item_id}")
        elif result is WriteResult.SKIPPED:
            counts.skipped += 1
            print(f"skipped: {item_id}")
        else:
            counts.failed += 1
            print(f"failed: {item_id}")

    print_summary(counts)
    return 1 if counts.failed > 0 else 0


if __name__ == "__main__":
    sys.exit(migrate(parse_args()))
