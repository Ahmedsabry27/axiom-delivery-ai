# Agent Tools and Permissions

Agents reuse native, MCP, and integration tool catalogues. Tool and knowledge assignments are tenant scoped and version bound. Configuration never executes external tools.

Effective access is deny-first and combines platform permission, ownership, and object assignments. Runtime discovery and execution must additionally enforce tenant policy, agent grants, authenticated-user grants, tool requirements, risk policy, and approval decisions.

Mutating tools remain subject to the existing Approval and Action Center. Agent configuration cannot grant platform permissions or bypass approval.
