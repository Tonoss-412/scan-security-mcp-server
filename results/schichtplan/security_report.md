# MCP Security Vulnerability Report
**File:** `results\schichtplan\tool_definitions.json`
**Time:** `2025-06-21 04:15:51`


## Path Traversal & Arbitrary File Read
- **Tool:** `import_holidays` (src\backend\routes\holiday_import.py)
    - ..
        ...description"             },             ...         ],         "is_closed": true...
- **Tool:** `get_log_content` (src\backend\routes\settings.py)
    - Get content of a specific log file filename
        ...Get content of a specific log file filename...