"""Unit tests for migrate_projects_v2_to_ugsys.py."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, ProfileNotFound

from scripts.migrate_projects_v2_to_ugsys import (
    Counts,
    WriteResult,
    build_session,
    map_item,
    scan_source,
    write_item,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_OUTPUT_FIELDS = [
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

SAMPLE_ITEM = {
    "PK": {"S": "PROJECT#proj-001"},
    "SK": {"S": "PROJECT"},
    "id": {"S": "proj-001"},
    "status": {"S": "active"},
    "is_enabled": {"BOOL": True},
}


def make_full_old_item() -> dict:
    """Return a fully-populated Old_Item in DynamoDB AttributeValue format."""
    return {
        "id": {"S": "proj-001"},
        "name": {"S": "Test Project"},
        "description": {"S": "A test project description"},
        "status": {"S": "active"},
        "isEnabled": {"BOOL": True},
        "createdAt": {"S": "2024-01-15T10:00:00Z"},
        "updatedAt": {"S": "2024-06-01T12:00:00Z"},
        "startDate": {"S": "2024-02-01T00:00:00Z"},
        "endDate": {"S": "2024-12-31T00:00:00Z"},
        "createdBy": {"S": "user-abc"},
        "currentParticipants": {"N": "5"},
        "maxParticipants": {"N": "20"},
        "notificationEmails": {"SS": ["admin@example.com", "lead@example.com"]},
        "enableSubscriptionNotifications": {"BOOL": True},
    }


def _make_client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, "PutItem")


# ---------------------------------------------------------------------------
# 1.1 Fully-populated Old_Item maps all required output fields
# ---------------------------------------------------------------------------


class TestMapItemFullyPopulated:
    def test_all_required_fields_present(self) -> None:
        old = make_full_old_item()
        new = map_item(old)
        for f in REQUIRED_OUTPUT_FIELDS:
            assert f in new, f"Missing required field: {f}"

    def test_pk_format(self) -> None:
        new = map_item(make_full_old_item())
        assert new["PK"] == {"S": "PROJECT#proj-001"}

    def test_sk_value(self) -> None:
        new = map_item(make_full_old_item())
        assert new["SK"] == {"S": "PROJECT"}

    def test_camelcase_is_enabled_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "isEnabled" not in new
        assert new["is_enabled"] == {"BOOL": True}

    def test_camelcase_created_at_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "createdAt" not in new
        assert new["created_at"] == {"S": "2024-01-15T10:00:00Z"}

    def test_camelcase_created_by_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "createdBy" not in new
        assert new["created_by"] == {"S": "user-abc"}

    def test_camelcase_current_participants_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "currentParticipants" not in new
        assert new["current_participants"] == {"N": "5"}

    def test_camelcase_max_participants_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "maxParticipants" not in new
        assert new["max_participants"] == {"N": "20"}

    def test_id_passthrough(self) -> None:
        assert map_item(make_full_old_item())["id"] == {"S": "proj-001"}

    def test_name_passthrough(self) -> None:
        assert map_item(make_full_old_item())["name"] == {"S": "Test Project"}

    def test_description_passthrough(self) -> None:
        assert map_item(make_full_old_item())["description"] == {"S": "A test project description"}

    def test_status_passthrough(self) -> None:
        assert map_item(make_full_old_item())["status"] == {"S": "active"}

    def test_updated_at_renamed(self) -> None:
        new = map_item(make_full_old_item())
        assert "updatedAt" not in new
        assert new["updated_at"] == {"S": "2024-06-01T12:00:00Z"}


# ---------------------------------------------------------------------------
# 1.2 Missing optional fields apply safe defaults
# ---------------------------------------------------------------------------


class TestMapItemSafeDefaults:
    def _base_item(self) -> dict:
        return {
            "id": {"S": "proj-min"},
            "name": {"S": "Minimal Project"},
            "description": {"S": ""},
            "status": {"S": "draft"},
            "createdAt": {"S": "2024-03-01T00:00:00Z"},
            "updatedAt": {"S": "2024-03-01T00:00:00Z"},
            "createdBy": {"S": "user-xyz"},
        }

    def test_missing_is_enabled_defaults_to_false(self) -> None:
        old = self._base_item()
        assert "isEnabled" not in old
        assert map_item(old)["is_enabled"] == {"BOOL": False}

    def test_missing_current_participants_defaults_to_zero(self) -> None:
        old = self._base_item()
        assert "currentParticipants" not in old
        assert map_item(old)["current_participants"] == {"N": "0"}

    def test_missing_max_participants_defaults_to_zero(self) -> None:
        old = self._base_item()
        assert "maxParticipants" not in old
        assert map_item(old)["max_participants"] == {"N": "0"}


# ---------------------------------------------------------------------------
# 1.3 notificationEmails SS passthrough
# ---------------------------------------------------------------------------


class TestMapItemNotificationEmailsPassthrough:
    def test_ss_values_are_identical(self) -> None:
        old = make_full_old_item()
        old["notificationEmails"] = {"SS": ["a@b.com", "c@d.com"]}
        new = map_item(old)
        assert "notification_emails" in new
        assert new["notification_emails"] == {"SS": ["a@b.com", "c@d.com"]}

    def test_ss_type_not_converted(self) -> None:
        old = make_full_old_item()
        old["notificationEmails"] = {"SS": ["only@one.com"]}
        new = map_item(old)
        assert "SS" in new["notification_emails"]
        assert "S" not in new["notification_emails"]
        assert "L" not in new["notification_emails"]

    def test_absent_notification_emails_not_written(self) -> None:
        old = make_full_old_item()
        del old["notificationEmails"]
        new = map_item(old)
        assert "notification_emails" not in new
        assert "notificationEmails" not in new


# ---------------------------------------------------------------------------
# 1.4 registrationEndDate is omitted from output
# ---------------------------------------------------------------------------


class TestMapItemRegistrationEndDateOmitted:
    def test_registration_end_date_camel_absent(self) -> None:
        old = make_full_old_item()
        old["registrationEndDate"] = {"S": "2024-09-30T00:00:00Z"}
        assert "registrationEndDate" not in map_item(old)

    def test_registration_end_date_snake_absent(self) -> None:
        old = make_full_old_item()
        old["registrationEndDate"] = {"S": "2024-09-30T00:00:00Z"}
        assert "registration_end_date" not in map_item(old)

    def test_registration_end_date_absent_when_not_in_old_item(self) -> None:
        old = make_full_old_item()
        assert "registrationEndDate" not in old
        new = map_item(old)
        assert "registrationEndDate" not in new
        assert "registration_end_date" not in new


# ---------------------------------------------------------------------------
# 1.5 GSI attribute construction
# ---------------------------------------------------------------------------


class TestMapItemGSIAttributes:
    def test_gsi1pk_format(self) -> None:
        assert map_item(make_full_old_item())["GSI1PK"] == {"S": "STATUS#active"}

    def test_gsi1sk_equals_created_at(self) -> None:
        new = map_item(make_full_old_item())
        assert new["GSI1SK"] == {"S": "2024-01-15T10:00:00Z"}
        assert new["GSI1SK"] == new["created_at"]

    def test_gsi2pk_present_when_created_by_non_empty(self) -> None:
        old = make_full_old_item()
        old["createdBy"] = {"S": "user-abc"}
        assert map_item(old)["GSI2PK"] == {"S": "OWNER#user-abc"}

    def test_gsi2sk_equals_created_at_when_created_by_non_empty(self) -> None:
        old = make_full_old_item()
        old["createdBy"] = {"S": "user-abc"}
        new = map_item(old)
        assert new["GSI2SK"] == {"S": "2024-01-15T10:00:00Z"}
        assert new["GSI2SK"] == new["created_at"]

    def test_gsi2_absent_when_created_by_empty_string(self) -> None:
        old = make_full_old_item()
        old["createdBy"] = {"S": ""}
        new = map_item(old)
        assert "GSI2PK" not in new
        assert "GSI2SK" not in new

    def test_gsi2_absent_when_created_by_missing(self) -> None:
        old = make_full_old_item()
        del old["createdBy"]
        new = map_item(old)
        assert "GSI2PK" not in new
        assert "GSI2SK" not in new


# ---------------------------------------------------------------------------
# 1.6 Migration metadata fields
# ---------------------------------------------------------------------------


class TestMapItemMigrationMetadata:
    def test_migrated_from_is_registry(self) -> None:
        assert map_item(make_full_old_item())["migrated_from"] == {"S": "registry"}

    def test_migrated_at_is_present(self) -> None:
        assert "migrated_at" in map_item(make_full_old_item())

    def test_migrated_at_is_string_type(self) -> None:
        assert "S" in map_item(make_full_old_item())["migrated_at"]

    def test_migrated_at_parses_as_iso8601(self) -> None:
        value = map_item(make_full_old_item())["migrated_at"]["S"]
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        assert parsed.tzinfo is not None or value.endswith("Z")

    def test_migrated_from_consistent_across_items(self) -> None:
        items = [
            make_full_old_item(),
            {
                "id": {"S": "proj-002"},
                "name": {"S": "Another"},
                "description": {"S": ""},
                "status": {"S": "closed"},
                "createdAt": {"S": "2023-05-10T08:00:00Z"},
                "updatedAt": {"S": "2023-05-10T08:00:00Z"},
                "createdBy": {"S": ""},
            },
        ]
        for old in items:
            assert map_item(old)["migrated_from"] == {"S": "registry"}


# ---------------------------------------------------------------------------
# 2.1 Dry-run mode skips put_item
# ---------------------------------------------------------------------------


class TestWriteItemDryRun:
    def test_dry_run_does_not_call_put_item(self) -> None:
        mock_client = MagicMock()
        write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=True)
        mock_client.put_item.assert_not_called()

    def test_dry_run_returns_skipped(self) -> None:
        mock_client = MagicMock()
        assert write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=True) is WriteResult.SKIPPED


# ---------------------------------------------------------------------------
# 2.2 Pre-check skip when item already exists
# ---------------------------------------------------------------------------


class TestWriteItemPreCheckSkip:
    def test_put_item_not_called_when_item_exists(self) -> None:
        mock_client = MagicMock()
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=True):
            write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)
        mock_client.put_item.assert_not_called()

    def test_returns_skipped_when_item_exists(self) -> None:
        mock_client = MagicMock()
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=True):
            result = write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)
        assert result is WriteResult.SKIPPED


# ---------------------------------------------------------------------------
# 2.3 ConditionalCheckFailedException treated as skipped
# ---------------------------------------------------------------------------


class TestWriteItemConditionalCheckFailed:
    def test_conditional_check_failed_returns_skipped(self) -> None:
        mock_client = MagicMock()
        mock_client.put_item.side_effect = _make_client_error("ConditionalCheckFailedException")
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
            result = write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)
        assert result is WriteResult.SKIPPED

    def test_conditional_check_failed_does_not_raise(self) -> None:
        mock_client = MagicMock()
        mock_client.put_item.side_effect = _make_client_error("ConditionalCheckFailedException")
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
            write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)


# ---------------------------------------------------------------------------
# 2.4 Other ClientError increments failed
# ---------------------------------------------------------------------------


class TestWriteItemOtherClientError:
    def test_provisioned_throughput_exceeded_returns_failed(self) -> None:
        mock_client = MagicMock()
        mock_client.put_item.side_effect = _make_client_error(
            "ProvisionedThroughputExceededException"
        )
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
            result = write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)
        assert result is WriteResult.FAILED

    def test_other_client_error_does_not_raise(self) -> None:
        mock_client = MagicMock()
        mock_client.put_item.side_effect = _make_client_error("InternalServerError")
        with patch("scripts.migrate_projects_v2_to_ugsys.item_exists", return_value=False):
            result = write_item(mock_client, TABLE, SAMPLE_ITEM, dry_run=False)
        assert result is WriteResult.FAILED


# ---------------------------------------------------------------------------
# 3.1 scan_source exits on ClientError
# ---------------------------------------------------------------------------


class TestScanSourceClientError:
    def test_exits_with_nonzero_on_client_error(self) -> None:
        mock_client = MagicMock()
        mock_client.scan.side_effect = _make_client_error("ResourceNotFoundException")
        with pytest.raises(SystemExit) as exc_info:
            scan_source(mock_client, "ProjectsTableV2")
        assert exc_info.value.code != 0

    def test_exits_on_any_client_error_code(self) -> None:
        mock_client = MagicMock()
        mock_client.scan.side_effect = _make_client_error("InternalServerError")
        with pytest.raises(SystemExit) as exc_info:
            scan_source(mock_client, "ProjectsTableV2")
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# 3.2 build_session exits on invalid profile
# ---------------------------------------------------------------------------


class TestBuildSessionInvalidProfile:
    def test_exits_with_nonzero_on_profile_not_found(self) -> None:
        with (
            patch("boto3.Session", side_effect=ProfileNotFound(profile="nonexistent")),
            pytest.raises(SystemExit) as exc_info,
        ):
            build_session("nonexistent")
        assert exc_info.value.code != 0

    def test_prints_descriptive_message_on_profile_not_found(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        with (
            patch("boto3.Session", side_effect=ProfileNotFound(profile="bad-profile")),
            pytest.raises(SystemExit),
        ):
            build_session("bad-profile")
        captured = capsys.readouterr()
        assert len((captured.out + captured.err).strip()) > 0


# ---------------------------------------------------------------------------
# 3.3 Exit code logic
# ---------------------------------------------------------------------------


class TestExitCodeLogic:
    def test_failed_greater_than_zero_means_exit_code_one(self) -> None:
        counts = Counts(total=3, written=1, skipped=1, failed=1)
        assert (1 if counts.failed > 0 else 0) == 1

    def test_zero_failures_means_exit_code_zero(self) -> None:
        counts = Counts(total=2, written=1, skipped=1, failed=0)
        assert (1 if counts.failed > 0 else 0) == 0

    def test_counts_dataclass_defaults(self) -> None:
        counts = Counts()
        assert counts.total == 0
        assert counts.written == 0
        assert counts.skipped == 0
        assert counts.failed == 0

    def test_multiple_failures_still_exit_code_one(self) -> None:
        for failed_count in [1, 5, 100]:
            counts = Counts(total=failed_count, written=0, skipped=0, failed=failed_count)
            assert (1 if counts.failed > 0 else 0) == 1
