# Copyright 2026, Jamf Software LLC
"""Jamf Pro MCP Server.

Main entry point for the Model Context Protocol server that enables LLMs to
interact with Jamf Pro's API for device management operations.

This server provides tools for:
- Managing computers and mobile devices
- Working with users and groups (smart and static)
- Accessing policies, configuration profiles, and scripts
- Managing extension attributes, categories, buildings, and departments
- Creating API roles and integrations for programmatic access
- (Optional) Jamf Protect security alerts, computers, and analytics

The server starts with zero credentials required. Setup tools are always
available to help users configure products. Product-specific tools return
helpful error messages when their product is not configured.
"""

import logging
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from . import __version__
from .auth import JamfAuthError
from .client import JamfClient
from .protect_client import ProtectClient
from .prompts import register_prompts
from .tools import register_all_tools, set_client, set_security_client
from .tools._common import set_protect_client
from .security_auth import JamfSecurityAuth, JamfSecurityAuthError
from .security_client import JamfSecurityClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("jamf-mcp")


def get_configuration_status() -> dict:
    """Get configuration status for all products.

    Returns:
        Dict with status for each product:
        - pro_configured: bool
        - protect_configured: bool
        - security_configured: bool
    """
    pro_url = os.environ.get("JAMF_PRO_URL")
    pro_client_id = os.environ.get("JAMF_PRO_CLIENT_ID")
    pro_secret = os.environ.get("JAMF_PRO_CLIENT_SECRET")

    protect_url = os.environ.get("JAMF_PROTECT_URL")
    protect_client_id = os.environ.get("JAMF_PROTECT_CLIENT_ID")
    protect_password = os.environ.get("JAMF_PROTECT_PASSWORD")

    return {
        "pro_configured": bool(pro_url and pro_client_id and pro_secret),
        "protect_configured": bool(protect_url and protect_client_id and protect_password),
        "security_configured": JamfSecurityAuth.is_configured(),
    }


def _init_pro_client() -> JamfClient | None:
    """Initialize Jamf Pro client if configured."""
    try:
        client = JamfClient.from_env()
        set_client(client)
        # Logged once per lifespan startup. If token-refresh log lines in
        # auth.py ever show an instance id that doesn't match the one printed
        # here (or if this line itself appears more than once without a real
        # pod restart in between), that proves something is re-creating the
        # client mid-process rather than the token TTL just being short.
        logger.info(
            "Jamf Pro client initialized for %s (auth instance %s)",
            client.base_url,
            client.auth._instance_id,
        )
        return client
    except JamfAuthError as e:
        logger.warning("Failed to initialize Jamf Pro client: %s", str(e))
    except Exception as e:
        logger.warning("Unexpected error initializing Jamf Pro client: %s", str(e))
    logger.warning("Jamf Pro tools will not be available")
    return None


def _init_protect_client() -> ProtectClient | None:
    """Initialize Jamf Protect client if configured."""
    try:
        client = ProtectClient.from_env()
        if client:
            set_protect_client(client)
            logger.info("Jamf Protect client initialized for %s", client.base_url)
            return client
    except Exception as e:
        logger.warning("Failed to initialize Jamf Protect client: %s", str(e))
        logger.warning("Jamf Protect tools will not be available")
    return None


def _init_security_client() -> JamfSecurityClient | None:
    """Initialize Jamf Security Cloud client if configured."""
    try:
        client = JamfSecurityClient.from_env()
        set_security_client(client)
        logger.info("Jamf Security Cloud client initialized for %s", client.base_url)
        return client
    except JamfSecurityAuthError as e:
        logger.warning("Jamf Security Cloud client not initialized: %s", str(e))
    except Exception as e:
        logger.warning("Unexpected error initializing Jamf Security Cloud client: %s", str(e))
    logger.warning("RISK API tools will not be available")
    return None


def _log_startup_mode(products_configured: int) -> None:
    """Log the server startup mode."""
    if products_configured == 0:
        logger.info("Starting in onboarding mode - no products configured")
        logger.info("Use jamf_get_setup_status() and jamf_configure_help() to get started")
    else:
        logger.info("%d of 3 products configured", products_configured)


@asynccontextmanager
async def jamf_lifespan(server: FastMCP):
    """Lifespan context manager for the Jamf MCP server.

    Handles initialization and cleanup of the Jamf Pro and optional Protect clients
    and Jamf Security Cloud client. All products are optional - the server will
    start even with zero credentials configured.
    """
    config_status = get_configuration_status()
    products_configured = sum(config_status.values())

    # Initialize clients based on configuration
    client = _init_pro_client() if config_status["pro_configured"] else None
    if not config_status["pro_configured"]:
        logger.info("Jamf Pro not configured (set JAMF_PRO_* env vars to enable)")

    protect_client = _init_protect_client() if config_status["protect_configured"] else None
    if not config_status["protect_configured"]:
        logger.info("Jamf Protect not configured (set JAMF_PROTECT_* env vars to enable)")

    security_client = _init_security_client() if config_status["security_configured"] else None
    if not config_status["security_configured"]:
        logger.info("Jamf Security Cloud not configured (set JAMF_SECURITY_* env vars to enable)")

    _log_startup_mode(products_configured)
    logger.info("Starting Jamf MCP Server v%s", __version__)

    try:
        yield
    finally:
        if client:
            await client.close()
        if protect_client:
            await protect_client.close()
        if security_client:
            await security_client.close()
        logger.info("Server shutdown complete")


# Create MCP server instance with lifespan
mcp = FastMCP(
    "jamf-mcp",
    instructions="""Jamf MCP Server - Interact with Jamf Pro, Protect, and Security Cloud.

This server starts with zero credentials required. Use these tools to get started:
- jamf_get_setup_status: Check which products are configured
- jamf_configure_help: Get step-by-step setup instructions

AVAILABLE PRODUCTS:

1. Jamf Pro (37 tools) - Device management for macOS, iOS/iPadOS, tvOS
   - Computers, mobile devices, users
   - Groups (smart and static), policies, profiles
   - Scripts, extension attributes, categories
   - API roles and integrations

2. Jamf Protect (6 tools) - Endpoint security
   - Security alerts, enrolled computers, analytics

3. Jamf Security Cloud (2 tools) - Risk management via RISK API
   - Device risk status and overrides

IMPORTANT RULES:
- When a product isn't configured, its tools will return setup instructions
- When the user's request is ambiguous about device type (computer, mobile_device,
  or user), ask them to clarify before calling any tool
- This applies to: extension attributes, smart/static groups, prestage enrollments

All tools return JSON responses with 'success', 'message', and 'data' fields.
Use pagination parameters (page, page_size) for large result sets.""",
    lifespan=jamf_lifespan,
)

import argparse

def main():
    """Entry point for the Jamf MCP Server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Jamf MCP Server")
    parser.add_argument(
        "--tool-filter",
        choices=["api", "complex", "all"],
        help="Filter tools by type (overrides JAMF_TOOL_FILTER env var)",
    )
    parser.add_argument(
        "--products",
        nargs="+",
        help="Filter tools by product (e.g. pro protect). Overrides JAMF_PRODUCTS env var.",
    )
    # Parse known args to avoid conflicts if mcp.run() parses args too (though FastMCP usually handles its own CLI via run())
    # actually mcp.run() might use click or argparse.
    # To be safe, let's just use os.environ if args are not passed, or handled manually.
    # FastMCP run() usually takes control.
    # If we run with `python -m src.jamf_mcp.server`, we are calling this main.
    
    args, unknown = parser.parse_known_args()
    
    # Determine filter: CLI arg > Env var > Default (None = all)
    tool_filter = args.tool_filter or os.environ.get("JAMF_TOOL_FILTER")
    
    # Determine products: CLI arg > Env var > Default (None = all)
    products = args.products
    if not products and os.environ.get("JAMF_PRODUCTS"):
        products = os.environ.get("JAMF_PRODUCTS").split(",")
        # clean whitespace
        products = [p.strip() for p in products if p.strip()]

    logger.info("Initializing Jamf MCP Server v%s", __version__)
    
    if tool_filter:
        logger.info("Appying tool filter: %s", tool_filter)
        
    if products:
        logger.info("Applying product filter: %s", products)
    
    register_all_tools(mcp, tool_filter=tool_filter, allowed_products=products)
    register_prompts(mcp)
    
    mcp.run()


if __name__ == "__main__":
    main()
