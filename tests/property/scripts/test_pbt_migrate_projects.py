"""Property-based tests for migrate_projects_v2_to_ugsys.py.

Uses Hypothesis to verify correctness properties hold for arbitrary inputs.
Run with: uv run pytest tests/property/scripts/ -v --hypothesis-seed=0
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.migrate_projects_v2_to_ugsys import (
    WriteResult,
    map_item,
    write_item,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

nonempty_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)

iso_timestamp = st.just("2024-01-15T10:00:00Z")

email_strategy = st.emails()


def old_item_strategy(
    *,
    include_notification_emails: bool | None = None,
    include_registration_end_date: bool | None = None,
    include_is_enabled: bool | None = None,
    include_current_participants: bool | None = None,
    include_max_participants: bool | None = None,
) -> st.SearchStrategy[dict]:
    """Build a strategy that generates Old_Item dicts."""

    @st.composite
    def _build(draw: st.DrawFn) -> dict:
        item_id = draw(nonempty_text)
        status = draw(nonempty_text)
        created_at = draw(iso_timestamp)
        updated_at = draw(iso_timestamp)
        created_by = draw(nonempty_text)

        old: dict = {
            "id": {"S": item_id},
            "name": {"S": draw(nonempty_text)},
            "description": {"S": draw(st.text(max_size=100))},
            "status": {"S": status},
            "createdAt": {"S": created_at},
            "updatedAt": {"S": updated_at},
            "createdBy": {"S": created_by},
        }

        include_enabled = draw(st.booleans()) if include_is_enabled is None else include_is_enabled
        if include_enabled:
            old["isEnabled"] = {"BOOL": draw(st.booleans())}

        include_cur = (
            draw(st.booleans())
            if include_current_participants is None
            else include_current_participants
        )
        if include_cur:
            old["currentParticipants"] = {"N": str(draw(st.integers(min_value=0, max_value=1000)))}

        include_max = (
            draw(st.booleans()) if include_max_participants is None else include_max_participants
        )
        if include_max:
            old["maxParticipants"] = {"N": str(draw(st.integers(min_value=0, max_value=1000)))}

        include_emails = (
            draw(st.booleans())
            if include_notification_emails is None
            else include_notification_emails
        )
        if include_emails:
            emails = draw(st.lists(email_strategy, min_size=1, max_size=5))
            old["notificationEmails"] = {"SS": emails}

        include_reg_end = (
            draw(st.booleans())
            if include_registration_end_date is None
            else include_registration_end_date
        )
        if include_reg_end:
            old["registrationEndDate"] = {"S": "2024-09-30T00:00:00Z"}

        return old

    return _build()


REQUIRED_KEYS = [
    "PK",
    "SK",
    "id",
    "name",
    "description",
    "status",
    "is_enabled",
    "current_participants",
    "max_participants",
    "created_by",
    "created_at",
    "updated_at",
    "GSI1PK",
    "GSI1SK",
    "migrated_from",
    "migrated_at",
]

TABLE = "ugsys-projects-prod"


# ---------------------------------------------------------------------------
# Property 1 — Mapping completeness and correctness
# Validates: Requirements 2.1, 2.2, 2.6
# ---------------------------------------------------------------------------


@given(old_item_strategy())
@settings(max_examples=100)
def test_property_1_mapping_completeness(old: dict) -> None:
    """All required keys present with correct PK/SK format for any valid Old_Item."""
    new = map_item(old)

    for key in REQUIRED_KEYS:
        assert key in new, f"Missing required key: {key}"

    item_id = old["id"]["S"]
    assert new["PK"] == {"S": f"PROJECT#{item_id}"}
    assert new["SK"] == {"S": "PROJECT"}
    assert new["id"] == {"S": item_id}
    assert new["status"] == old["status"]
    assert new["created_at"] == old["createdAt"]


# ---------------------------------------------------------------------------
# Property 2 — notificationEmails SS passthrough
# Validates: Requirement 2.3
# ---------------------------------------------------------------------------


@given(old_item_strategy(include_notification_emails=True))
@settings(max_examples=100)
def test_property_2_notification_emails_passthrough(old: dict) -> None:
    """notification_emails SS values are identical to notificationEmails SS values."""
    new = map_item(old)

    assert "notification_emails" in new
    assert new["notification_emails"]["SS"] == old["notificationEmails"]["SS"]
    assert "SS" in new["notification_emails"]
    assert "S" not in new["notification_emails"]


# ---------------------------------------------------------------------------
# Property 3 — registrationEndDate omission
# Validates: Requirement 2.4
# ---------------------------------------------------------------------------


@given(old_item_strategy(include_registration_end_date=True))
@settings(max_examples=100)
def test_property_3_registration_end_date_omitted_when_present(old: dict) -> None:
    """registrationEndDate is never written to New_Item even when present in Old_Item."""
    new = map_item(old)

    assert "registrationEndDate" not in new
    assert "registration_end_date" not in new


@given(old_item_strategy(include_registration_end_date=False))
@settings(max_examples=50)
def test_property_3_registration_end_date_omitted_when_absent(old: dict) -> None:
    """Neither key appears in New_Item when registrationEndDate is absent."""
    new = map_item(old)

    assert "registrationEndDate" not in new
    assert "registration_end_date" not in new


# ---------------------------------------------------------------------------
# Property 4 — Safe defaults for absent fields
# Validates: Requirement 2.5
# ---------------------------------------------------------------------------


@given(old_item_strategy(include_is_enabled=False))
@settings(max_examples=100)
def test_property_4_default_is_enabled_false(old: dict) -> None:
    """is_enabled defaults to False when isEnabled is absent."""
    new = map_item(old)
    assert new["is_enabled"] == {"BOOL": False}


@given(old_item_strategy(include_current_participants=False))
@settings(max_examples=100)
def test_property_4_default_current_participants_zero(old: dict) -> None:
    """current_participants defaults to 0 when currentParticipants is absent."""
    new = map_item(old)
    assert new["current_participants"] == {"N": "0"}


@given(old_item_strategy(include_max_participants=False))
@settings(max_examples=100)
def test_property_4_default_max_participants_zero(old: dict) -> None:
    """max_participants defaults to 0 when maxParticipants is absent."""
    new = map_item(old)
    assert new["max_participants"] == {"N": "0"}


# ---------------------------------------------------------------------------
# Property 5 — GSI attributes correctly constructed
# Validates: Requirements 3.1, 3.2
# ---------------------------------------------------------------------------


@given(old_item_strategy())
@settings(max_examples=100)
def test_property_5_gsi1_always_present(old: dict) -> None:
    """GSI1PK and GSI1SK are always present and correctly formatted."""
    new = map_item(old)

    status = old["status"]["S"]
    created_at = old["createdAt"]["S"]

    assert new["GSI1PK"] == {"S": f"STATUS#{status}"}
    assert new["GSI1SK"] == {"S": created_at}


@given(old_item_strategy())
@settings(max_examples=100)
def test_property_5_gsi2_present_iff_created_by_nonempty(old: dict) -> None:
    """GSI2PK/GSI2SK present iff created_by is non-empty."""
    new = map_item(old)
    created_by = old.get("createdBy", {}).get("S", "")

    if created_by:
        assert new["GSI2PK"] == {"S": f"OWNER#{created_by}"}
        assert new["GSI2SK"] == new["created_at"]
    else:
        assert "GSI2PK" not in new
        assert "GSI2SK" not in new


# ---------------------------------------------------------------------------
# Property 6 — Migration metadata on every New_Item
# Validates: Requirements 4.1, 4.2
# ---------------------------------------------------------------------------


@given(old_item_strategy())
@settings(max_examples=100)
def test_property_6_migration_metadata(old: dict) -> None:
    """migrated_from is always 'registry' and migrated_at parses as ISO 8601."""
    new = map_item(old)

    assert new["migrated_from"] == {"S": "registry"}
    assert "migrated_at" in new
    value = new["migrated_at"]["S"]
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    assert parsed is not None


# ---------------------------------------------------------------------------
# Property 7 — Idempotency: existing items always skipped
# Validates: Requirements 5.1, 5.2, 5.4
# ---------------------------------------------------------------------------


@given(
    st.lists(nonempty_text, min_size=1, max_size=20, unique=True),
    st.integers(min_value=0, max_value=20),
)
@settings(max_examples=50)
def test_property_7_idempotency_existing_items_skipped(
    item_ids: list[str], existing_count_raw: int
) -> None:
    """skipped == M, written == N-M, failed == 0 when M items already exist."""
    n = len(item_ids)
    m = min(existing_count_raw, n)
    existing_ids = set(item_ids[:m])

    mock_client = MagicMock()

    def fake_item_exists(client: object, table: str, pk: str) -> bool:
        item_id = pk.replace("PROJECT#", "")
        return item_id in existing_ids

    written = 0
    skipped = 0
    failed = 0

    with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", side_effect=fake_item_exists):
        for item_id in item_ids:
            item = {
                "PK": {"S": f"PROJECT#{item_id}"},
                "SK": {"S": "PROJECT"},
                "id": {"S": item_id},
                "status": {"S": "active"},
                "is_enabled": {"BOOL": True},
            }
            result = write_item(mock_client, TABLE, item, dry_run=False)
            if result is WriteResult.WRITTEN:
                written += 1
            elif result is WriteResult.SKIPPED:
                skipped += 1
            else:
                failed += 1

    assert skipped == m
    assert written == n - m
    assert failed == 0


# ---------------------------------------------------------------------------
# Property 8 — Per-item put_item writes
# Validates: Requirement 6.1
# ---------------------------------------------------------------------------


@given(st.lists(nonempty_text, min_size=1, max_size=20, unique=True))
@settings(max_examples=50)
def test_property_8_put_item_called_exactly_n_times(item_ids: list[str]) -> None:
    """put_item is called exactly N times for N new items in non-dry-run mode."""
    mock_client = MagicMock()

    with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
        for item_id in item_ids:
            item = {
                "PK": {"S": f"PROJECT#{item_id}"},
                "SK": {"S": "PROJECT"},
                "id": {"S": item_id},
                "status": {"S": "active"},
                "is_enabled": {"BOOL": True},
            }
            write_item(mock_client, TABLE, item, dry_run=False)

    assert mock_client.put_item.call_count == len(item_ids)


# ---------------------------------------------------------------------------
# Property 9 — Dry-run produces no writes
# Validates: Requirement 7.1
# ---------------------------------------------------------------------------


@given(st.lists(nonempty_text, min_size=0, max_size=20))
@settings(max_examples=50)
def test_property_9_dry_run_no_writes(item_ids: list[str]) -> None:
    """put_item is never called when dry_run=True regardless of item count."""
    mock_client = MagicMock()

    for item_id in item_ids:
        item = {
            "PK": {"S": f"PROJECT#{item_id}"},
            "SK": {"S": "PROJECT"},
            "id": {"S": item_id},
            "status": {"S": "active"},
            "is_enabled": {"BOOL": True},
        }
        result = write_item(mock_client, TABLE, item, dry_run=True)
        assert result is WriteResult.SKIPPED

    mock_client.put_item.assert_not_called()


# ---------------------------------------------------------------------------
# Property 10 — Per-item outcome for every processed item
# Validates: Requirement 9.1
# ---------------------------------------------------------------------------


@given(st.lists(nonempty_text, min_size=1, max_size=10, unique=True))
@settings(max_examples=30)
def test_property_10_per_item_outcome(item_ids: list[str]) -> None:
    """Every item produces exactly one WriteResult — no item is silently dropped.

    write_item returns a result per item; the migrate() loop logs each one.
    This property verifies N items → N results, all WRITTEN for new items.
    """
    mock_client = MagicMock()
    results = []

    with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
        for item_id in item_ids:
            item = {
                "PK": {"S": f"PROJECT#{item_id}"},
                "SK": {"S": "PROJECT"},
                "id": {"S": item_id},
                "status": {"S": "active"},
                "is_enabled": {"BOOL": True},
            }
            results.append(write_item(mock_client, TABLE, item, dry_run=False))

    assert len(results) == len(item_ids)
    assert all(r is WriteResult.WRITTEN for r in results)
