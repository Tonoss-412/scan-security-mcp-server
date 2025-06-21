import json
import re
import datetime
import os

try:
    from transformers import pipeline
    nlp_available = True
except ImportError:
    nlp_available = False

# ==============================================================================
# BỘ QUY TẮC PHÂN TÍCH BẢO MẬT MCP (PHIÊN BẢN CẢI TIẾN)
# ==============================================================================
# Mỗi quy tắc bao gồm:
# - description: Mô tả về loại lỗ hổng.
# - severity: Mức độ nghiêm trọng (High, Medium, Low).
# - recommendation: Khuyến nghị để khắc phục.
# - patterns: Danh sách các mẫu regex đã được biên dịch để phát hiện.
# - scope: Phạm vi áp dụng quy tắc ('name', 'description', 'params').
# ==============================================================================

RULES = {
    "Remote Code Execution": {
        "description": "Tool có khả năng cho phép thực thi mã hoặc lệnh hệ thống một cách trực tiếp, có thể dẫn đến RCE.",
        "severity": "High",
        "recommendation": "Tuyệt đối không sử dụng các tool cho phép thực thi code không được kiểm soát. Nếu cần, hãy đảm bảo môi trường thực thi được sandbox hoàn toàn và mọi input đều được lọc kỹ lưỡng.",
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"\bexecute_python_code\b", r"\beval\b", r"\bexecute_shell_command\b", 
                r"\bsubprocess\b", r"\bos\.system\b", r"execute.*command"
            ]
        ],
        "scope": ["name", "description"]
    },
    "Hardcoded Sensitive Data": {
        "description": "Mô tả của tool chứa các chuỗi trông giống như secret (API key, JWT, UUID) bị hardcode. Đây là một rủi ro bảo mật nghiêm trọng.",
        "severity": "High",
        "recommendation": "Tuyệt đối không hardcode secret trong mô tả tool. Sử dụng placeholder như 'YOUR_API_KEY' và hướng dẫn người dùng cách cung cấp secret một cách an toàn.",
        "patterns": [
            # JWT Token
            re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}"),
            # Common API Key prefixes (Stripe, etc.)
            re.compile(r"\b(sk|pk|rk)_[a-zA-Z0-9]{20,}\b"),
            # AWS Access Key ID
            re.compile(r"AKIA[0-9A-Z]{16}"),
            # UUID (commonly used for session IDs)
            re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", re.IGNORECASE)
        ],
        "scope": ["description"] # Chỉ quét mô tả
    },
    "Path Traversal & Arbitrary File Read": {
        "description": "Tool có thể cho phép đọc các file tùy ý trên hệ thống, có nguy cơ dẫn đến lỗ hổng Path Traversal. Kẻ tấn công có thể truy cập các file nhạy cảm ngoài thư mục dự kiến.",
        "severity": "Medium",
        "recommendation": "Luôn xác thực và làm sạch (sanitize) mọi đường dẫn file từ người dùng. Giới hạn quyền truy cập file của tool trong một thư mục được chỉ định (sandbox).",
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"\.\.",  # Path Traversal
                r"\/etc\/passwd", r"~\/\.ssh", r"\.env", r"id_rsa",
                r"(read|access|analyze|get|load|view).*file.*(path|name)", # Đọc file kết hợp với tham số đường dẫn
                r"analyze_log_file"
            ]
        ],
        "scope": ["description", "params_str"] # params_str là chuỗi ghép từ các tên tham số
    },
    "Indirect Prompt Injection": {
        "description": "Mô tả của tool chứa các chỉ thị ẩn hoặc hướng dẫn có thể bị kẻ tấn công lợi dụng để thao túng hành vi của mô hình ngôn ngữ, vượt qua các giới hạn an toàn.",
        "severity": "Medium",
        "recommendation": "Loại bỏ các chỉ thị về hành vi của mô hình ra khỏi mô tả tool. Các chỉ thị này nên được đặt trong system prompt hoặc các lớp bảo vệ (guardrails) riêng.",
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"<important>[\s\S]*?</important>", r"<hidden>[\s\S]*?</hidden>", r"<secret>[\s\S]*?</secret>",
                r"you must first", r"Do not mention", r"present it as if", r"ignore previous instructions",
                r"override-auth-protocol", r"if the query contains.*?you must"
            ]
        ],
        "scope": ["description"]
    },
}

# Định nghĩa phủ định/an toàn cho từng rule
NEGATIONS = {
    "Remote Code Execution": [
        "sandbox", "no code execution", "cannot run code", "read-only", "forbidden", "not allowed", "test only", "mock", "simulate",
        "no shell", "no subprocess", "no eval", "no system", "no command", "no script", "no exec", "no os.system", "no shell access", "no arbitrary code", "no arbitrary command"
    ],
    "Hardcoded Sensitive Data": [
        "example", "placeholder", "mock", "fake", "sample", "demo", "not real", "dummy", "sandbox", "simulate", "test",
        "YOUR_API_KEY", "YOUR_TOKEN", "YOUR_SECRET", "example token", "sample key"
    ],
    "Path Traversal & Arbitrary File Read": [
        "sanitize", "validate", "no arbitrary file", "no path traversal", "cannot read system file", "cannot access /etc/passwd",
        "cannot access parent directory", "no .. allowed", "no file read", "read-only", "sandbox", "no external file"
    ],
    "Indirect Prompt Injection": [
        "no prompt injection", "guarded", "filtered", "no user prompt", "no system prompt", "no override", "no instruction injection", "no prompt manipulation", "no prompt override"
    ]
}

NLP_LABELS = {
    "Remote Code Execution": ["dangerous", "executes code", "runs shell command", "safe", "sandboxed", "does not execute code"],
    "Path Traversal & Arbitrary File Read": ["reads arbitrary file", "path traversal", "safe", "cannot read arbitrary file", "no path traversal"],
    "Indirect Prompt Injection": ["vulnerable to prompt injection", "safe", "not vulnerable", "guarded"]
}

def is_rule_negated_context(rule, text, match_start, match_end):
    window = 60
    context = text[max(0, match_start-window):min(len(text), match_end+window)].lower()
    for neg in NEGATIONS.get(rule, []):
        if neg in context:
            return True
    return False

# Nếu transformers có sẵn, dùng zero-shot-classification để phân tích ngữ cảnh
if nlp_available:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    def is_dangerous_context(context):
        labels = ["dangerous", "safe", "not dangerous", "benign", "forbidden", "sandboxed"]
        result = classifier(context, labels)
        # Nếu nhãn "dangerous" có score cao nhất và >0.5 thì coi là nguy hiểm
        if result['labels'][0] == "dangerous" and result['scores'][0] > 0.5:
            return True
        # Nếu "safe" hoặc "not dangerous" cao nhất thì không nguy hiểm
        if result['labels'][0] in ["safe", "not dangerous", "benign", "sandboxed"] and result['scores'][0] > 0.5:
            return False
        # Nếu không rõ, fallback về rule-based
        return None
else:
    def is_dangerous_context(context):
        return None

# Nếu transformers có sẵn, dùng zero-shot-classification để phân tích ngữ cảnh sensitive data
if nlp_available:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    def is_sensitive_data_exposed_context(context):
        labels = [
            "exposes sensitive data", "returns secret", "returns password", "returns api key", "returns token",
            "returns credentials", "returns confidential", "returns sensitive information", "safe", "does not expose", "does not return sensitive data"
        ]
        result = classifier(context, labels)
        # Nếu nhãn expose/return sensitive data có score cao nhất và >0.5 thì cảnh báo
        if result['labels'][0].startswith("exposes") or result['labels'][0].startswith("returns"):
            if result['scores'][0] > 0.5:
                return True
        # Nếu "safe" hoặc "does not expose" cao nhất thì không nguy hiểm
        if result['labels'][0] in ["safe", "does not expose", "does not return sensitive data"] and result['scores'][0] > 0.5:
            return False
        return None
else:
    def is_sensitive_data_exposed_context(context):
        return None

def analyze_single_tool(tool):
    """Phân tích một tool duy nhất dựa trên bộ quy tắc."""
    tool_name = tool.get("name", "Unnamed Tool")
    description = tool.get("description", "")
    input_schema = tool.get("inputSchema", {})
    properties = input_schema.get("properties", {})
    param_names_list = list(properties.keys())
    param_names_str = " ".join(param_names_list)
    found_issues = {}

    for issue_type, rule in RULES.items():
        matches = []
        if rule["scope"] != ["params_list"]:
            text_to_scan = ""
            if "name" in rule["scope"]:
                text_to_scan += f"{tool_name} "
            if "description" in rule["scope"]:
                text_to_scan += f"{description} "
            if "params_str" in rule["scope"]:
                text_to_scan += f"{param_names_str} "
            for pattern in rule["patterns"]:
                for match in pattern.finditer(text_to_scan):
                    start, end = match.span()
                    context_start = max(0, start - 40)
                    context_end = min(len(text_to_scan), end + 40)
                    context = text_to_scan[context_start:context_end].replace('\n', ' ').strip()
                    # NLP check cho mọi rule
                    nlp_result = is_dangerous_context(context)
                    if nlp_result is False:
                        continue  # Ngữ cảnh an toàn, bỏ qua
                    if nlp_result is None and is_rule_negated_context(issue_type, text_to_scan, start, end):
                        continue  # Rule-based phủ định
                    matches.append({
                        "matched_text": match.group(0).replace('\n', ' ').strip(),
                        "context": f"...{context}..."
                    })
        else: # rule["scope"] == ["params_list"]
            for param in param_names_list:
                if param.lower() in rule["patterns"]:
                    matches.append({
                        "matched_text": param,
                        "context": "(tham số đáng ngờ)"
                    })
        if matches:
            found_issues[issue_type] = matches

    if found_issues:
        return {"tool_name": tool_name, "issues": found_issues, "file": tool.get("file", "")}
    return None

def group_by_vuln_type(all_issues):
    grouped = {}
    for tool in all_issues:
        for vuln, details in tool["issues"].items():
            if vuln not in grouped:
                grouped[vuln] = []
            grouped[vuln].append({"tool_name": tool["tool_name"], "details": details, "file": tool.get("file", "")})
    return grouped

def generate_minimal_report(grouped_results, config_file_path):
    lines = [
        f"# MCP Security Vulnerability Report",
        f"**File:** `{config_file_path}`",
        f"**Time:** `{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        ""
    ]
    if not grouped_results:
        lines.append("✅ No vulnerabilities detected.")
        return "\n".join(lines)
    for vuln, tools in grouped_results.items():
        lines.append(f"\n## {vuln}")
        for tool in tools:
            file_str = f" ({tool['file']})" if tool.get('file') else " (no file info)"
            lines.append(f"- **Tool:** `{tool['tool_name']}`{file_str}")
            for finding in tool["details"]:
                lines.append(f"    - {finding['matched_text']}")
                if finding["context"]:
                    lines.append(f"        {finding['context']}")
    return "\n".join(lines)

def main(config_file_path, report_file_path, scan_msg=None):
    """Hàm chính để chạy scan và tạo báo cáo."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW_BOLD = '\033[1;33m'
    RESET = '\033[0m'
    try:
        with open(config_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        if scan_msg:
            print(f"{YELLOW_BOLD}{scan_msg} - No tool definition{RESET}")
        else:
            print(f"{YELLOW_BOLD}No tool definition{RESET}")
        return
    except json.JSONDecodeError:
        if scan_msg:
            print(f"{YELLOW_BOLD}{scan_msg} - No tool definition{RESET}")
        else:
            print(f"{YELLOW_BOLD}No tool definition{RESET}")
        return

    tools = data.get("tools", [])
    if not tools:
        if scan_msg:
            print(f"{YELLOW_BOLD}{scan_msg} - No tool definition{RESET}")
        else:
            print(f"{YELLOW_BOLD}No tool definition{RESET}")
        return

    all_issues = []
    for tool in tools:
        result = analyze_single_tool(tool)
        if result:
            all_issues.append(result)
    
    grouped = group_by_vuln_type(all_issues)
    report = generate_minimal_report(grouped, config_file_path)
    
    try:
        with open(report_file_path, 'w', encoding='utf-8') as file:
            file.write(report)
    except IOError as e:
        print(f"Lỗi khi ghi báo cáo ra file: {e}")

    # In trạng thái màu
    if scan_msg:
        if grouped:
            print(f"{RED}{scan_msg} - Vulnerabilities found{RESET}")
        else:
            print(f"{GREEN}{scan_msg} - No vulnerabilities{RESET}")

def scan_all_results(results_root="results"):
    repo_dirs = [d for d in os.listdir(results_root) if os.path.isdir(os.path.join(results_root, d))]
    total = len(repo_dirs)
    for idx, repo_dir in enumerate(repo_dirs, 1):
        repo_path = os.path.join(results_root, repo_dir)
        config_file_path = os.path.join(repo_path, "tool_definitions.json")
        report_file_path = os.path.join(repo_path, "security_report.md")
        if not os.path.exists(config_file_path):
            continue
        scan_msg = f"Scanning {idx}/{total}: {repo_dir}"
        main(config_file_path, report_file_path, scan_msg=scan_msg)

if __name__ == "__main__":
    scan_all_results("results")