# Connector adapter contract

Enterprise connectors implement the existing `EnterpriseConnector` contract for configuration validation, bounded connection testing, capability discovery, health, governed tool execution, and governed action execution. Jira is the only registered enterprise connector. MCP remains a separate, existing operational framework.

EP12 synchronization extensions still need typed schema discovery, preview, full/incremental page fetching, transformation, record validation, checkpoints, rate-limit handling, cancellation, and health signals. Outbound operations must remain behind AX-EP07.
