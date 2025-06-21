# MCP Security Vulnerability Report
**File:** `results\salesforce-mcp\tool_definitions.json`
**Time:** `2025-06-21 04:15:51`


## Path Traversal & Arbitrary File Read
- **Tool:** `manage_salesforce_debug_logs` (server.py)
    - ..
        ...e debug log content for log ID 07L000000..."      Args:         operation: Operati...