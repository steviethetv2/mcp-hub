# Available Tools

Complete reference for all MCP tools organized by Jamf product.

## Table of Contents

- [Setup Tools](#setup-tools) (always available)
- [Jamf Pro](#jamf-pro)
  - [Device Management](#device-management)
  - [Groups](#groups)
  - [Configuration & Policies](#configuration--policies)
  - [App Deployment](#app-deployment)
  - [Inventory & Organization](#inventory--organization)
  - [API Administration](#api-administration)
- [Jamf Protect](#jamf-protect)
  - [Alerts](#alerts)
  - [Computers](#computers)
  - [Analytics](#analytics)
- [Jamf Security Cloud](#jamf-security-cloud)
  - [Risk Management](#risk-management)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)

---

# Setup Tools

These tools are **always available**, even with no credentials configured. Use them to check configuration status and get setup instructions.

| Tool | Description |
|------|-------------|
| `jamf_get_setup_status` | Check which products are configured and how many tools are available |
| `jamf_configure_help` | Get step-by-step setup instructions for any product |

**When to use:**
- First time starting the server
- Checking which products are configured
- Getting setup instructions for a new product
- Troubleshooting configuration issues

**Example usage:**
```
"What's the setup status?" -> jamf_get_setup_status()
"How do I configure Jamf Protect?" -> jamf_configure_help(product="jamf_protect")
"Show me all setup instructions" -> jamf_configure_help(product="all")
```

---

# Jamf Pro

Core device management tools for macOS, iOS/iPadOS, and tvOS devices.

## Device Management

| Tool | Description |
|------|-------------|
| `jamf_get_computer` | Get computer info by ID, serial number, or name. Supports a `sections` argument (e.g., `["GENERAL", "OPERATING_SYSTEM", "HARDWARE"]` or `["ALL"]`) to control which inventory subsections are returned for the list path; single-computer lookups always return all sections. |
| `jamf_update_computer` | Update computer inventory fields and extension attributes |
| `jamf_get_mobile_device` | Get mobile device info by ID, serial number, or name |
| `jamf_update_mobile_device` | Update mobile device inventory fields |
| `jamf_get_user` | Get user info by ID, username, or email |
| `jamf_update_user` | Update user record fields |

## Groups

| Tool | Description |
|------|-------------|
| `jamf_get_smart_groups` | List smart groups or get details with criteria |
| `jamf_create_smart_group` | Create a new smart group with criteria |
| `jamf_get_static_groups` | List static groups or get members |
| `jamf_create_static_group` | Create a new static group with members |

## Configuration & Policies

| Tool | Description |
|------|-------------|
| `jamf_get_policies` | Get policies with optional filtering |
| `jamf_get_computer_configuration_profiles` | Get macOS configuration profiles |
| `jamf_get_mobile_device_configuration_profiles` | Get iOS/iPadOS configuration profiles |
| `jamf_get_prestages` | Get computer or mobile device prestage enrollments |

## App Deployment

| Tool | Description |
|------|-------------|
| `jamf_get_app_installer_titles` | Get available apps from Jamf App Catalog |
| `jamf_get_app_installer_deployments` | Get App Installer deployment configurations |
| `jamf_create_app_installer_deployment` | Create a new App Installer deployment |
| `jamf_get_app_installers` | Get App Installers with deployment status |
| `jamf_get_mac_apps` | Get Mac App Store / VPP app deployments |
| `jamf_get_mobile_device_apps` | Get iOS/iPadOS app deployments |
| `jamf_get_ebooks` | Get eBook deployments |
| `jamf_get_restricted_software` | Get restricted software configurations |
| `jamf_get_patch_policies` | Get patch management policies |

## Inventory & Organization

| Tool | Description |
|------|-------------|
| `jamf_get_scripts` | Get scripts used in policies |
| `jamf_get_extension_attributes` | Get extension attribute definitions |
| `jamf_create_extension_attribute` | Create new extension attributes |
| `jamf_get_categories` | Get categories for organizing objects |
| `jamf_create_category` | Create a new category |
| `jamf_get_buildings` | Get building locations |
| `jamf_get_departments` | Get departments |
| `jamf_get_printers` | Get printers or printer details by ID |
| `jamf_create_printer` | Create a new printer |
| `jamf_update_printer` | Update an existing printer by ID |


## API Administration

| Tool | Description |
|------|-------------|
| `jamf_get_api_role_privileges` | Get available privileges for API roles |
| `jamf_get_api_roles` | List API roles or get specific role details |
| `jamf_create_api_role` | Create a new API role with privileges |
| `jamf_get_api_integrations` | List API integrations |
| `jamf_create_api_integration` | Create a new API integration (client) |
| `jamf_create_api_client_credentials` | Generate OAuth credentials for an integration |
| `jamf_create_computer_update_api_client` | Create API role + client for computer updates |

## MDM & DDM Commands

| Tool | Description |
|------|-------------|
| `jamf_get_mdm_commands` | List MDM commands tenant-wide. Filter by client management UUID, command name, and status (Pending, Acknowledged, NotNow, Error). |
| `jamf_get_computer_management_history` | Get pending, completed, and failed MDM commands for a single computer (Jamf Pro ID). |
| `jamf_get_mobile_device_management_history` | Get pending, completed, and failed MDM commands for a single mobile device (Jamf Pro ID). |
| `jamf_get_managed_software_update_plans` | List DDM-driven Managed Software Update plans and their per-device status. |

## Reports

Composite tools that aggregate data from multiple API endpoints into a single summary.

| Tool | Description |
|------|-------------|
| `jamf_get_profile_deployment_failures` | Aggregated report of configuration profile deployment failures. Auto-paginates InstallProfile errors and enriches with profile names. Sorted by failure count. |

---

# Jamf Protect

Endpoint security tools for threat detection and response. Requires [Jamf Protect configuration](INSTALLATION.md#jamf-protect-optional).

## Alerts

| Tool | Description |
|------|-------------|
| `jamf_protect_get_alert` | Get details of a specific security alert by UUID |
| `jamf_protect_list_alerts` | List security alerts with filtering options |

## Computers

| Tool | Description |
|------|-------------|
| `jamf_protect_get_computer` | Get Protect-enrolled computer details by UUID |
| `jamf_protect_list_computers` | List computers enrolled in Jamf Protect |

## Analytics

| Tool | Description |
|------|-------------|
| `jamf_protect_get_analytic` | Get details of a specific analytic (detection rule) |
| `jamf_protect_list_analytics` | List all analytics (detection rules) |

---

# Jamf Security Cloud

Device risk management via the RISK API. Requires [Security Cloud configuration](INSTALLATION.md#jamf-security-cloud-optional).

## Risk Management

| Tool | Description |
|------|-------------|
| `jamf_get_risk_devices` | Get device risk status |
| `jamf_override_device_risk` | Override risk level for specific devices |

---

# Usage Examples

| Task | Example Prompt |
|------|---------------|
| Find devices | "Find all computers in the Engineering department" |
| Look up by serial | "Get the computer with serial number C02XG2JGJG5H" |
| Update inventory | "Set asset tag 'ENG-001' on computer ID 42" |
| Create smart group | "Create a smart group for macOS 14+ devices" |
| Create static group | "Create a static group 'Executives' with computer IDs 10, 15, 22" |
| View policies | "Show all policies in the Security category" |
| List alerts | "Show me recent Jamf Protect alerts" |
| Check risk | "What devices have elevated risk scores?" |

---

# API Reference

This server uses multiple Jamf APIs:

| Product | API | Endpoint Pattern |
|---------|-----|------------------|
| **Jamf Pro** | Classic | `/JSSResource/...` |
| **Jamf Pro** | v1 | `/api/v1/...` |
| **Jamf Pro** | v2 | `/api/v2/...` |
| **Jamf Pro** | v3 | `/api/v3/...` |
| **Jamf Protect** | GraphQL | `/graphql` |
| **Security Cloud** | RISK API | `/v1/risk/...` |

For complete API documentation:
- [Jamf Pro API](https://developer.jamf.com/)
- [Jamf Protect API](https://learn.jamf.com/en-US/bundle/jamf-protect-documentation/page/Jamf_Protect_API.html)
- [Jamf Security API](https://developer.jamf.com/jamf-security)
