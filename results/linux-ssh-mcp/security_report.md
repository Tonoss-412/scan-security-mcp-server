# MCP Security Vulnerability Report
**File:** `results\linux-ssh-mcp\tool_definitions.json`
**Time:** `2025-06-21 04:15:49`


## Remote Code Execution
- **Tool:** `execute_linux_command` (server.py)
    - execute_linux_command
        ...execute_linux_command      Executes a shell command on the sp...
    - Executes a shell command
        ...execute_linux_command      Executes a shell command on the specified Linux VM and returns i...
    - execute_linux_command
        ...word or private_key_path.     Example: `execute_linux_command("ls -l", host="192.168.1.100", username...

## Path Traversal & Arbitrary File Read
- **Tool:** `read_file_content` (server.py)
    - ~/.ssh
        ...00", username="user", private_key_path="~/.ssh/mykey")`...
    - read_file_content("/etc/os-release", host="192.168.1.100", username="user", private_key_path
        ...ied file on the Linux VM.     Example: `read_file_content("/etc/os-release", host="192.168.1.100", username="user", private_key_path="~/.ssh/mykey")`...