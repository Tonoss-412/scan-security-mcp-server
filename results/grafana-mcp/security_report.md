# MCP Security Vulnerability Report
**File:** `results\grafana-mcp\tool_definitions.json`
**Time:** `2025-06-21 04:15:48`


## Path Traversal & Arbitrary File Read
- **Tool:** `create_time_series_dashboard` (src\grafana_mcp\mcp_server.py)
    - ..
        ...ECT timestamp AS time, count() AS total ...`.      • Always include a time filter...