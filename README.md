# 🛠️ MCPServer Security Workflow

## ✅ Step 1: Recon
- **Script:** `\recon_mcpserver\recon.py`  
- **Output:** `\recon_mcpserver\recon.py`
(remind set environment variable GITHUB_TOKEN)
---

## ✅ Step 2: Clone Repository
- **Script:** `\clone.py`  
- **Output:** `\repo`

---

## ✅ Step 3: Extract Tool Definitions
- **Script:** `\extract_mcp_tools_all.py`  
- **Output:** `\results\<repo>\tool_definitions.json`

---

## ✅ Step 4: Check for Vulnerabilities
- **Script:** `\check_tool_definitions_all.py`  
- **Output:** `\results\<repo>\security_report.md`
(remind install gemini cli, login and set the environment variable)
---

# 🧪 Test with 1 URL (/test by 1 url)
## 🔹 Extract MCP Tools
- **Script:** `extract_mcp_tools_by_url.py`  
- **Output:** `mcp_config.json`

## 🔹 Check Vulnerabilities
- **Script:** `check_tool_definitions_by_mcp_config.json.py`  
- **Output:** `security_report.md`
