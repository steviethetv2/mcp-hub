# Copyright 2026, Jamf Software LLC
"""MDM and DDM command lookup tools for Jamf Pro.

Provides visibility into:

- Per-device MDM command history (pending, completed, failed) via the Classic
  API `computerhistory` / `mobiledevicehistory` endpoints, which return three
  pre-bucketed lists for each device.
- Tenant-wide MDM command queries via the modern `/api/v2/mdm/commands`
  endpoint, filterable by client management UUID, command name, and status.
- DDM-driven Managed Software Update plans via
  `/api/v1/managed-software-updates/plans`, which surface the per-device
  status of declarative software-update activations.
"""

import logging
from typing import Optional

from ..client import JamfAPIError
from ._common import format_error, format_response, get_client_safe
from ._registry import jamf_tool

logger = logging.getLogger(__name__)


# Valid status values for /api/v2/mdm/commands. The API rejects anything else
# in an RSQL filter, so we validate up front for a clearer error.
VALID_MDM_COMMAND_STATUSES = {"Pending", "Acknowledged", "NotNow", "Error"}

# Valid subsets supported by /JSSResource/{computer,mobiledevice}history.
# Using a subset trims the response to a single section, which keeps the
# payload small for the common "just show me commands" use case.
VALID_HISTORY_SUBSETS = {
    "General",
    "ComputerUsageLogs",
    "Audits",
    "PolicyLogs",
    "CasperRemoteLogs",
    "ScreenSharingLogs",
    "CasperImagingLogs",
    "Commands",
    "UserLocation",
    "MacAppStoreApplications",
}


def _normalize_status(status: Optional[str]) -> Optional[str]:
    """Validate and normalize an MDM command status value.

    Args:
        status: Caller-supplied status (case-insensitive)

    Returns:
        The canonical status string, or None if no status was supplied

    Raises:
        ValueError: If the status is not a recognized MDM command status
    """
    if status is None:
        return None
    cleaned = status.strip()
    if not cleaned:
        return None
    # Match case-insensitively but return the canonical casing the API expects.
    for canonical in VALID_MDM_COMMAND_STATUSES:
        if canonical.lower() == cleaned.lower():
            return canonical
    raise ValueError(
        f"Invalid MDM command status: {status!r}. "
        f"Valid values: {', '.join(sorted(VALID_MDM_COMMAND_STATUSES))}"
    )


def _build_mdm_commands_filter(
    client_management_id: Optional[str],
    status: Optional[str],
    command: Optional[str],
) -> Optional[str]:
    """Compose an RSQL filter string for /api/v2/mdm/commands."""
    clauses = []
    if client_management_id:
        clauses.append(f'clientManagementId=="{client_management_id}"')
    if status:
        clauses.append(f'status=="{status}"')
    if command:
        clauses.append(f'command=="{command}"')
    return ";".join(clauses) if clauses else None


def _summarize_command_history(history_root: dict) -> dict:
    """Reduce a Classic-API history payload to its command buckets and counts.

    The Classic API returns the buckets nested under either `computer_history`
    or `mobile_device_history` depending on resource type. This helper handles
    both and adds a small summary block so callers can get an at-a-glance count
    without iterating.
    """
    container = (
        history_root.get("computer_history")
        or history_root.get("mobile_device_history")
        or history_root
    )

    completed = container.get("completed_commands", []) or []
    pending = container.get("pending_commands", []) or []
    failed = container.get("failed_commands", []) or []

    return {
        "summary": {
            "completed_count": len(completed),
            "pending_count": len(pending),
            "failed_count": len(failed),
        },
        "completed_commands": completed,
        "pending_commands": pending,
        "failed_commands": failed,
    }


@jamf_tool
async def jamf_get_mdm_commands(
    client_management_id: Optional[str] = None,
    status: Optional[str] = None,
    command: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
    sort: str = "dateSent:desc",
) -> str:
    """List MDM commands across the Jamf Pro tenant.

    Queries `/api/v2/mdm/commands`, the modern endpoint for inspecting MDM
    command history. Use this for tenant-wide views or when you already know
    the client management UUID for a device. For a per-device pending /
    completed / failed breakdown keyed by Jamf Pro ID, use
    `jamf_get_computer_management_history` or
    `jamf_get_mobile_device_management_history` instead.

    Args:
        client_management_id: Client management UUID of a specific device
            (the `general.managementId` field on a computer or mobile device
            inventory record). Filters results to that device.
        status: Filter by command status. One of: Pending, Acknowledged,
            NotNow, Error. Case-insensitive.
        command: Filter by MDM command name (e.g., "DeviceLock",
            "EraseDevice", "InstallApplication", "DeviceInformation").
        page: Page number for pagination (0-indexed, default: 0).
        page_size: Number of results per page (default: 100, max: 2000).
        sort: Sort expression in `field:direction` form. Defaults to newest
            first by `dateSent:desc`. Other useful fields include
            `dateCompleted` and `status`.

    Returns:
        JSON containing a list of MDM command records with their UUIDs,
        target device, command name, status, and timestamps.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        normalized_status = _normalize_status(status)
        filter_str = _build_mdm_commands_filter(
            client_management_id, normalized_status, command
        )

        params: dict = {
            "page": page,
            "page-size": page_size,
            "sort": sort,
        }
        if filter_str:
            params["filter"] = filter_str

        result = await client.v2_get("mdm/commands", params=params)
        count = result.get("totalCount", len(result.get("results", [])))
        return format_response(result, f"Retrieved {count} MDM commands")

    except ValueError as e:
        return format_error(e)
    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting MDM commands")
        return format_error(e)


@jamf_tool
async def jamf_get_computer_management_history(
    computer_id: int,
    commands_only: bool = True,
) -> str:
    """Get MDM command history for a single computer.

    Returns the pending, completed, and failed MDM command buckets that the
    Classic API surfaces under `/JSSResource/computerhistory/id/{id}`. This is
    the most direct way to answer "what commands has this Mac received and
    what is their state?" using the Jamf Pro computer ID.

    Args:
        computer_id: Jamf Pro computer ID (required).
        commands_only: When True (default), requests just the Commands subset,
            which keeps the response small. When False, returns the full
            management history (policy logs, audits, screen-sharing logs,
            etc.) in addition to commands.

    Returns:
        JSON containing `summary` counts plus `pending_commands`,
        `completed_commands`, and `failed_commands` arrays. When
        `commands_only` is False, the full Classic API history payload is
        returned under `data.full_history` alongside the command summary.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        endpoint = f"/JSSResource/computerhistory/id/{computer_id}"
        if commands_only:
            endpoint += "/subset/Commands"

        result = await client._request("GET", endpoint)

        if not isinstance(result, dict):
            return format_error(
                JamfAPIError(
                    f"Unexpected response type from {endpoint}: {type(result).__name__}"
                )
            )

        summary = _summarize_command_history(result)
        if not commands_only:
            summary["full_history"] = result

        return format_response(
            summary,
            f"Retrieved command history for computer ID {computer_id}",
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting computer management history")
        return format_error(e)


@jamf_tool
async def jamf_get_mobile_device_management_history(
    device_id: int,
    commands_only: bool = True,
) -> str:
    """Get MDM command history for a single mobile device.

    Returns the pending, completed, and failed MDM command buckets that the
    Classic API surfaces under `/JSSResource/mobiledevicehistory/id/{id}`.

    Args:
        device_id: Jamf Pro mobile device ID (required).
        commands_only: When True (default), requests just the Commands subset
            to keep the response small. When False, returns the full mobile
            device management history alongside the command summary.

    Returns:
        JSON containing `summary` counts plus `pending_commands`,
        `completed_commands`, and `failed_commands` arrays. When
        `commands_only` is False, the full Classic API history payload is
        returned under `data.full_history`.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        endpoint = f"/JSSResource/mobiledevicehistory/id/{device_id}"
        if commands_only:
            endpoint += "/subset/Commands"

        result = await client._request("GET", endpoint)

        if not isinstance(result, dict):
            return format_error(
                JamfAPIError(
                    f"Unexpected response type from {endpoint}: {type(result).__name__}"
                )
            )

        summary = _summarize_command_history(result)
        if not commands_only:
            summary["full_history"] = result

        return format_response(
            summary,
            f"Retrieved command history for mobile device ID {device_id}",
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting mobile device management history")
        return format_error(e)


@jamf_tool
async def jamf_get_managed_software_update_plans(
    management_id: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
    sort: str = "planUuid:desc",
) -> str:
    """List Managed Software Update (DDM) plans and their per-device status.

    Managed Software Updates is the primary DDM-driven workflow Jamf Pro
    exposes through its public API. Each plan represents a declarative
    software-update activation targeted at a device, with a status field that
    reflects DDM progress (e.g., PlanCreated, PlanScheduled,
    UpdateDownloading, Complete, Error).

    Use this tool to answer "what DDM software-update commands are pending /
    in-flight / complete for this device or fleet?".

    Args:
        management_id: Optional client management UUID to filter plans for a
            single device (matches the `device.objectId` / management UUID on
            the plan).
        page: Page number for pagination (0-indexed, default: 0).
        page_size: Number of results per page (default: 100).
        sort: Sort expression in `field:direction` form. Defaults to
            `planUuid:desc`.

    Returns:
        JSON containing the plan list with per-device status, target version,
        and timestamps.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        params: dict = {
            "page": page,
            "page-size": page_size,
            "sort": sort,
        }
        if management_id:
            params["filter"] = f'device.objectId=="{management_id}"'

        result = await client.v1_get("managed-software-updates/plans", params=params)
        count = result.get("totalCount", len(result.get("results", [])))
        return format_response(
            result, f"Retrieved {count} managed software update plans"
        )

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting managed software update plans")
        return format_error(e)
