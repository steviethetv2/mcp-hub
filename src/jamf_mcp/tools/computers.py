# Copyright 2026, Jamf Software LLC
"""Computer management tools for Jamf Pro.

This module provides tools for retrieving and updating macOS computer
inventory information.
"""

import logging
from typing import Any, Optional, Union

from ..client import JamfAPIError
from ._common import format_error, format_response, get_client_safe
from ._registry import jamf_tool

logger = logging.getLogger(__name__)


def _build_fields(field_mapping: dict[str, Any]) -> dict[str, Any]:
    """Build a dict from field mapping, excluding None values.

    Args:
        field_mapping: Dict of API field names to values

    Returns:
        Dict containing only non-None values
    """
    return {key: value for key, value in field_mapping.items() if value is not None}


def _build_extension_attributes(extension_attributes: list[dict]) -> list[dict]:
    """Format extension attributes for the Jamf API.

    Args:
        extension_attributes: List of dicts with 'id' and 'value' keys

    Returns:
        List formatted for Jamf API with 'definitionId' and 'values'
    """
    return [
        {"definitionId": str(ea["id"]), "values": [str(ea["value"])]}
        for ea in extension_attributes
    ]


def _build_concise_computer_result(
    computer_id: int, update_data: dict, api_result: Any
) -> dict:
    """Build a concise result dict from update response.

    Args:
        computer_id: The computer ID that was updated
        update_data: The data that was sent in the update
        api_result: The raw API response

    Returns:
        Concise result dict with key fields only
    """
    result = {
        "id": computer_id,
        "updated_fields": list(update_data.keys()),
    }
    if isinstance(api_result, dict) and "general" in api_result:
        result["name"] = api_result["general"].get("name")
        result["serialNumber"] = api_result["general"].get("serialNumber")
    return result


# Valid section values for the computers-inventory endpoint. The Jamf Pro API
# requires these to be passed as repeated `section` query parameters; if no
# section is provided the API returns only GENERAL, which omits operating
# system, hardware, user/location, and other commonly needed data.
VALID_COMPUTER_SECTIONS = {
    "GENERAL",
    "DISK_ENCRYPTION",
    "PURCHASING",
    "APPLICATIONS",
    "STORAGE",
    "USER_AND_LOCATION",
    "CONFIGURATION_PROFILES",
    "PRINTERS",
    "SERVICES",
    "HARDWARE",
    "LOCAL_USER_ACCOUNTS",
    "CERTIFICATES",
    "ATTACHMENTS",
    "PLUGINS",
    "PACKAGE_RECEIPTS",
    "FONTS",
    "SECURITY",
    "OPERATING_SYSTEM",
    "LICENSED_SOFTWARE",
    "IBEACONS",
    "SOFTWARE_UPDATES",
    "EXTENSION_ATTRIBUTES",
    "CONTENT_CACHING",
    "GROUP_MEMBERSHIPS",
}

# Default sections to return when none are explicitly requested. This covers
# the data needed for the majority of inventory reporting use cases (OS
# version, last check-in, hardware, assigned user/email, group membership,
# extension attributes) without bloating responses with bulky sections like
# APPLICATIONS, FONTS, PLUGINS, or PACKAGE_RECEIPTS.
DEFAULT_COMPUTER_SECTIONS = [
    "GENERAL",
    "HARDWARE",
    "OPERATING_SYSTEM",
    "USER_AND_LOCATION",
    "DISK_ENCRYPTION",
    "SECURITY",
    "STORAGE",
    "EXTENSION_ATTRIBUTES",
    "GROUP_MEMBERSHIPS",
    "PURCHASING",
    "SOFTWARE_UPDATES",
    "CONTENT_CACHING",
]


def _resolve_sections(sections: Optional[list[str]]) -> list[str]:
    """Validate caller-supplied sections or return the default set.

    Accepts the special token "ALL" (case-insensitive, alone or in a list)
    as a request for every supported section.

    Args:
        sections: Sections requested by the caller, or None for defaults

    Returns:
        A validated list of section names safe to pass to the Jamf API

    Raises:
        ValueError: If any provided section name is not recognized
    """
    if not sections:
        return list(DEFAULT_COMPUTER_SECTIONS)

    normalized = [s.strip().upper() for s in sections if s and s.strip()]
    if not normalized:
        return list(DEFAULT_COMPUTER_SECTIONS)

    if "ALL" in normalized:
        return sorted(VALID_COMPUTER_SECTIONS)

    invalid = [s for s in normalized if s not in VALID_COMPUTER_SECTIONS]
    if invalid:
        raise ValueError(
            "Invalid computer section(s): "
            f"{', '.join(invalid)}. "
            f"Valid sections: {', '.join(sorted(VALID_COMPUTER_SECTIONS))}, ALL"
        )

    # Preserve caller order while removing duplicates.
    seen: set[str] = set()
    result: list[str] = []
    for value in normalized:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


@jamf_tool
async def jamf_get_computer(
    computer_id: Optional[int] = None,
    serial_number: Optional[str] = None,
    name: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
    sections: Optional[list[str]] = None,
) -> str:
    """Get computer information from Jamf Pro.

    Retrieves detailed inventory information for macOS computers managed by Jamf Pro.
    You can search by ID, serial number, or name. If no identifier is provided,
    returns a paginated list of all computers.

    The Jamf Pro `/api/v1/computers-inventory` endpoint returns only the GENERAL
    section by default, which omits OS version, hardware, user/location, disk
    encryption, security, extension attributes, and group memberships. This tool
    requests an expanded default set so reporting use cases (e.g., "find Macs on
    outdated macOS in group X with assigned email and last check-in") work
    without additional configuration. Pass `sections` to override.

    Args:
        computer_id: Jamf Pro computer ID to retrieve specific device
        serial_number: Computer serial number to search for exact match
        name: Computer name to search for (supports partial matches with wildcards)
        page: Page number for pagination (0-indexed, default: 0)
        page_size: Number of results per page (default: 100, max: 2000)
        sections: Inventory sections to include when listing computers. Pass a
            list of section names (e.g., ["GENERAL", "OPERATING_SYSTEM",
            "HARDWARE"]) or ["ALL"] for every available section. When omitted,
            a curated default set is requested. Ignored for single-computer
            lookups by `computer_id`, which always return all sections via the
            `/api/v1/computers-inventory-detail/{id}` endpoint. Valid values:
            GENERAL, DISK_ENCRYPTION,
            PURCHASING, APPLICATIONS, STORAGE, USER_AND_LOCATION,
            CONFIGURATION_PROFILES, PRINTERS, SERVICES, HARDWARE,
            LOCAL_USER_ACCOUNTS, CERTIFICATES, ATTACHMENTS, PLUGINS,
            PACKAGE_RECEIPTS, FONTS, SECURITY, OPERATING_SYSTEM,
            LICENSED_SOFTWARE, IBEACONS, SOFTWARE_UPDATES, EXTENSION_ATTRIBUTES,
            CONTENT_CACHING, GROUP_MEMBERSHIPS.

    Returns:
        JSON containing computer details or list of computers with inventory data
        including hardware, software, and management information.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        resolved_sections = _resolve_sections(sections)

        if computer_id:
            result = await client.v1_get(
                f"computers-inventory-detail/{computer_id}"
            )
            return format_response(result, f"Retrieved computer ID {computer_id}")

        filters = []
        if serial_number:
            filters.append(f'hardware.serialNumber=="{serial_number}"')
        if name:
            filters.append(f'general.name=="{name}*"')

        # httpx serializes list values as repeated query params, which is the
        # format the Jamf Pro API expects (e.g., ?section=GENERAL&section=HARDWARE).
        params: dict = {
            "page": page,
            "page-size": page_size,
            "section": resolved_sections,
        }
        if filters:
            params["filter"] = " and ".join(filters)

        result = await client.v1_get("computers-inventory", params=params)
        count = result.get("totalCount", len(result.get("results", [])))
        return format_response(result, f"Retrieved {count} computers")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error getting computer info")
        return format_error(e)


@jamf_tool
async def jamf_update_computer(
    computer_id: int,
    name: Optional[str] = None,
    asset_tag: Optional[str] = None,
    username: Optional[str] = None,
    realname: Optional[str] = None,
    email: Optional[str] = None,
    department_id: Optional[Union[str, int]] = None,
    building_id: Optional[Union[str, int]] = None,
    room: Optional[str] = None,
    position: Optional[str] = None,
    phone: Optional[str] = None,
    extension_attributes: Optional[list[dict]] = None,
) -> str:
    """Update computer information in Jamf Pro.

    Updates inventory fields for a specific computer. Only provided fields will be
    updated; omitted fields remain unchanged. Useful for updating asset information,
    user assignments, and custom extension attribute values.

    Args:
        computer_id: Jamf Pro computer ID to update (required)
        name: New computer name
        asset_tag: Asset tag value for inventory tracking
        username: Assigned user's username
        realname: Assigned user's full/display name
        email: Assigned user's email address
        department_id: Department ID (use jamf_get_departments to find valid IDs).
            Accepts integer or string, e.g., 1 or "1"
        building_id: Building ID (use jamf_get_buildings to find valid IDs).
            Accepts integer or string, e.g., 28 or "28"
        room: Room number or name (free-form text, no validation)
        position: User's job position or title (free-form text)
        phone: Contact phone number (free-form text)
        extension_attributes: List of extension attribute updates, each with:
            - id: Extension attribute definition ID (integer)
            - value: New value to set (string)

    Returns:
        JSON with update confirmation and the updated computer record.
    """
    client, error = get_client_safe()
    if error:
        return error

    try:
        update_data = {}

        general = _build_fields({"name": name, "assetTag": asset_tag})
        if general:
            update_data["general"] = general

        user_and_location = _build_fields({
            "username": username,
            "realname": realname,
            "email": email,
            "departmentId": str(department_id) if department_id is not None else None,
            "buildingId": str(building_id) if building_id is not None else None,
            "room": room,
            "position": position,
            "phone": phone,
        })
        if user_and_location:
            update_data["userAndLocation"] = user_and_location

        if extension_attributes:
            update_data["extensionAttributes"] = _build_extension_attributes(
                extension_attributes
            )

        if not update_data:
            return format_error(ValueError("No update fields provided"))

        result = await client.v1_patch(
            f"computers-inventory-detail/{computer_id}", update_data
        )
        concise_result = _build_concise_computer_result(computer_id, update_data, result)
        return format_response(concise_result, f"Updated computer ID {computer_id}")

    except JamfAPIError as e:
        return format_error(e)
    except Exception as e:
        logger.exception("Error updating computer info")
        return format_error(e)
