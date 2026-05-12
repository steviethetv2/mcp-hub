# Copyright 2026, Jamf Software LLC
"""Composite report tools for Jamf Pro.

These tools combine data from multiple API endpoints to provide
aggregated insights that would otherwise require many individual
tool calls.
"""

import logging
from collections import defaultdict
from typing import Optional

from ..client import JamfAPIError
from ._common import format_error, format_response, get_client_safe
from ._registry import ToolType, jamf_tool

logger = logging.getLogger(__name__)

MAX_SAMPLE_DEVICES = 5


@jamf_tool(tool_type=ToolType.COMPLEX)
async def jamf_get_profile_deployment_failures(
    profile_name: Optional[str] = None,
    max_pages: int = 10,
) -> str:
    """Get a summary of configuration profile deployment failures across the fleet.

    Automatically paginates through InstallProfile MDM command errors and
    correlates profile IDs with human-readable profile names. Returns an
    aggregated report sorted by failure count (highest first).

    This composite tool replaces the manual workflow of:
    1. Paginating jamf_get_mdm_commands(command="InstallProfile", status="Error")
    2. Correlating profileIdentifier values via jamf_get_computer_configuration_profiles

    Args:
        profile_name: Optional filter to focus on a specific profile by name
            (case-insensitive partial match). Only profiles whose name contains
            this string will appear in results.
        max_pages: Safety cap on API pagination (default: 10, meaning up to
            1000 error records with page_size=100). Increase if you have a
            very large error backlog.

    Returns:
        JSON containing an aggregated failure report with:
        - Total error count and affected profile count
        - Per-profile breakdown: profile ID, name, failure count,
          unique device count, error messages with counts,
          and sample affected device UUIDs
        - Sorted by failure count (most failures first)
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        # Step 1: Build profile ID -> name map
        profiles_result = await client.classic_get("osxconfigurationprofiles")
        profiles_list = profiles_result.get("os_x_configuration_profiles", [])
        profile_name_map = {
            str(p["id"]): p.get("name", f"Unknown (ID {p['id']})")
            for p in profiles_list
        }

        # Step 2: Auto-paginate through InstallProfile errors
        page_size = 100
        all_errors: list[dict] = []
        filter_str = 'command=="InstallProfile";status=="Error"'
        pages_fetched = 0
        pagination_complete = False

        for page_num in range(max_pages):
            params = {
                "page": page_num,
                "page-size": page_size,
                "sort": "dateSent:desc",
                "filter": filter_str,
            }
            result = await client.v2_get("mdm/commands", params=params)
            results = result.get("results", [])
            all_errors.extend(results)
            pages_fetched = page_num + 1

            total_count = result.get("totalCount", 0)
            if (page_num + 1) * page_size >= total_count:
                pagination_complete = True
                break
            if not results:
                pagination_complete = True
                break

        # Step 3: Aggregate errors by profile ID
        aggregated: dict[str, dict] = defaultdict(lambda: {
            "failure_count": 0,
            "error_messages": defaultdict(int),
            "affected_devices": set(),
        })

        for cmd in all_errors:
            profile_id = cmd.get("profileIdentifier", "unknown")
            entry = aggregated[profile_id]
            entry["failure_count"] += 1

            error_info = cmd.get("error") or {}
            error_desc = error_info.get("errorDescription", "Unknown error")
            error_code = error_info.get("errorCode")
            error_domain = error_info.get("errorDomain")

            if error_code is not None:
                error_key = f"[{error_domain or 'Unknown'}:{error_code}] {error_desc}"
            else:
                error_key = error_desc

            entry["error_messages"][error_key] += 1
            entry["affected_devices"].add(
                cmd.get("clientManagementId", "unknown")
            )

        # Step 4: Build sorted, enriched response
        failures = []
        for pid, data in aggregated.items():
            resolved_name = profile_name_map.get(
                pid, f"Unknown Profile (ID {pid})"
            )

            if profile_name and profile_name.lower() not in resolved_name.lower():
                continue

            device_list = list(data["affected_devices"])

            failures.append({
                "profile_id": pid,
                "profile_name": resolved_name,
                "failure_count": data["failure_count"],
                "unique_device_count": len(device_list),
                "errors": [
                    {"message": msg, "count": count}
                    for msg, count in sorted(
                        data["error_messages"].items(),
                        key=lambda x: -x[1],
                    )
                ],
                "sample_device_uuids": device_list[:MAX_SAMPLE_DEVICES],
                "devices_truncated": len(device_list) > MAX_SAMPLE_DEVICES,
            })

        failures.sort(key=lambda x: -x["failure_count"])

        # Step 5: Format response
        response_data = {
            "total_errors_found": len(all_errors),
            "total_profiles_affected": len(failures),
            "pages_fetched": pages_fetched,
            "max_pages": max_pages,
            "pagination_complete": pagination_complete,
            "failures": failures,
        }

        message = (
            f"Found {len(all_errors)} InstallProfile errors across "
            f"{len(failures)} profile(s) ({pages_fetched} page(s) fetched)"
        )

        return format_response(response_data, message)

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting profile deployment failures")
        return format_error(e)
