# MCP Security Vulnerability Report
**File:** `results\devops-mcp-servers\tool_definitions.json`
**Time:** `2025-06-21 04:15:48`


## Path Traversal & Arbitrary File Read
- **Tool:** `get_commit_diff` (servers\bitbucket_cloud\bitbucket_cloud_mcp.py)
    - ..
        ...mit hash or revision spec (e.g., 'master..feature')         context_lines: Number...

## Remote Code Execution
- **Tool:** `exec_kubectl` (servers\kubernetes\kubernetes_mcp.py)
    - Execute a raw kubectl command
        ...exec_kubectl Execute a raw kubectl command.          Args:         command: The ku...