# MCP Security Vulnerability Report
**File:** `results\fantastic-funicular\tool_definitions.json`
**Time:** `2025-06-21 04:15:48`


## Remote Code Execution
- **Tool:** `test_subprocess_server_persistence` (tests\integration\test_mcp_config_persistence.py)
    - subprocess
        ...subprocess_server_persistence Test that subprocess MCP servers are saved to config....
- **Tool:** `test_add_subprocess_server` (tests\unit\test_gui_components.py)
    - subprocess
        ...test_add_subprocess_server Test adding subprocess server....
- **Tool:** `test_add_subprocess_server` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...est_add_subprocess_server Test adding a subprocess MCP server....
- **Tool:** `subprocess_client` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...subprocess_client Create MCP subprocess client for testing....
- **Tool:** `test_connect_success` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...test_connect_success Test successful subprocess connection....
- **Tool:** `test_execute_tool` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...st_execute_tool Test tool execution via subprocess....
- **Tool:** `test_disconnect` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...test_disconnect Test subprocess disconnection....
- **Tool:** `test_health_check` (tests\unit\test_mcp_manager.py)
    - subprocess
        ...test_health_check Test subprocess health check....