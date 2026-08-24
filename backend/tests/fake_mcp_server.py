"""Standards-compliant fake provider used by Sprint 13 integration tests."""

from mcp.server.fastmcp import FastMCP

fake_mcp = FastMCP("Sprint13 Fake MCP", json_response=True)


@fake_mcp.tool()
def search_customer(email: str, limit: int = 10) -> dict:
    """Search a customer record by email."""
    return {"customer": {"email": email, "status": "active"}, "limit": limit}


@fake_mcp.resource("customer://policy")
def policy() -> str:
    return "Customer data may only be used for an approved business purpose."


@fake_mcp.resource("customer://{customer_id}")
def customer(customer_id: str) -> str:
    return f"Customer {customer_id}"


@fake_mcp.prompt()
def support_summary(customer_id: str) -> str:
    return f"Summarize support history for {customer_id}"
