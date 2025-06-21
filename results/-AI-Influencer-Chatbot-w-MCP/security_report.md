# MCP Security Vulnerability Report
**File:** `results\-AI-Influencer-Chatbot-w-MCP\tool_definitions.json`
**Time:** `2025-06-21 04:15:47`


## Path Traversal & Arbitrary File Read
- **Tool:** `temp_env_file` (tests\cli\test_cli.py)
    - .env
        ...Create a temporary .env file. tmp_path...
- **Tool:** `temp_env_file` (tests\cli\test_run.py)
    - .env
        ...Create a temporary .env file. tmp_path...