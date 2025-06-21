# MCP Security Vulnerability Report
**File:** `results\claude-container\tool_definitions.json`
**Time:** `2025-06-21 04:15:48`


## Remote Code Execution
- **Tool:** `test_run_interactive_container` (tests\core\test_container_runner.py)
    - subprocess
        ...Test running interactive container with subprocess....