import os
import json
import re
import subprocess

try:
    from transformers import pipeline
    nlp_available = True
except ImportError:
    nlp_available = False

RULES = {
    "Remote Code Execution": {
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"\\bexecute_python_code\\b", r"\\beval\\b", r"\\bexecute_shell_command\\b",
                r"\\bsubprocess\\b", r"\\bos\\.system\\b", r"execute.*command"
            ]
        ],
        "scope": ["name", "description"]
    },
    "Hardcoded Sensitive Data": {
        "patterns": [
            re.compile(r"eyJ[a-zA-Z0-9_-]{20,}\\.[a-zA-Z0-9_-]{20,}\\.[a-zA-Z0-9_-]{20,}"),
            re.compile(r"\\b(sk|pk|rk)_[a-zA-Z0-9]{20,}\\b"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", re.IGNORECASE)
        ],
        "scope": ["description"]
    },
    "Path Traversal & Arbitrary File Read": {
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"\.\.", r"/etc/passwd", r"~/.ssh", r"\.env", r"id_rsa",
                r"(read|access|analyze|get|load|view).*file.*(path|name)",
                r"analyze_log_file"
            ]
        ],
        "scope": ["description", "params_str"]
    },
    "Indirect Prompt Injection": {
        "patterns": [
            re.compile(p, re.IGNORECASE) for p in [
                r"<important>[\\s\\S]*?</important>", r"<hidden>[\\s\\S]*?</hidden>", r"<secret>[\\s\\S]*?</secret>",
                r"you must first", r"Do not mention", r"present it as if", r"ignore previous instructions",
                r"override-auth-protocol", r"if the query contains.*?you must"
            ]
        ],
        "scope": ["description"]
    },
}

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

def is_rule_negated_context(rule, text, match_start, match_end):
    window = 60
    context = text[max(0, match_start-window):min(len(text), match_end+window)].lower()
    for neg in NEGATIONS.get(rule, []):
        if neg in context:
            return True
    return False

if nlp_available:
    classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    def is_dangerous_context(context):
        labels = ["dangerous", "safe", "not dangerous", "benign", "forbidden", "sandboxed"]
        result = classifier(context, labels)
        if result['labels'][0] == "dangerous" and result['scores'][0] > 0.5:
            return True
        if result['labels'][0] in ["safe", "not dangerous", "benign", "sandboxed"] and result['scores'][0] > 0.5:
            return False
        return None
else:
    def is_dangerous_context(context):
        return None

def analyze_single_tool(tool):
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
                    nlp_result = is_dangerous_context(context)
                    if nlp_result is False:
                        continue
                    if nlp_result is None and is_rule_negated_context(issue_type, text_to_scan, start, end):
                        continue
                    matches.append({
                        "matched_text": match.group(0).replace('\n', ' ').strip(),
                        "context": f"...{context}..."
                    })
        else:
            for param in param_names_list:
                if param.lower() in rule["patterns"]:
                    matches.append({
                        "matched_text": param,
                        "context": "(tham số đáng ngờ)"
                    })
        if matches:
            found_issues[issue_type] = matches
    if found_issues:
        return {"tool_name": tool_name, "issues": found_issues, "file": tool.get("file", ""), "description": description}
    return None

def ask_gemini(prompt):
    gemini_path = r"C:\\Users\\User\\AppData\\Roaming\\npm\\gemini.cmd"
    try:
        result = subprocess.run(
            [gemini_path],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print("Gemini CLI timeout!")
        return "[TIMEOUT]"
    except Exception as e:
        print(f"Gemini CLI error: {e}")
        return f"[ERROR: {e}]"

def to_markdown_tool_entry(tool_name, file_path, description):
    desc_one_line = description.replace('\n', ' · ').replace('\r', '')
    return f"    - **{tool_name.upper()}**\n        *`{file_path}`*\n                *{desc_one_line}*"

def to_markdown_gemini_entry(tool_name, file_path, status, gemini_desc):
    desc_one_line = gemini_desc.replace('\n', ' · ').replace('\r', '')
    return f"    - **{tool_name.upper()}**\n        *`{file_path}`*\n        - Status: `{status}`\n                *{desc_one_line}*"

def scan_tools_rules_nlp_and_gemini(config_path, output_path):
    with open(config_path, "r", encoding="utf-8") as f:
        tools = json.load(f)
    # 1. RULES/NLP: gom lỗi theo issue_type
    issues_by_type = {}  # {issue_type: [ {tool_name, file, description, context, matched_text} ]}
    for tool in tools:
        rule_result = analyze_single_tool(tool)
        if rule_result:
            for issue_type, matches in rule_result["issues"].items():
                for match in matches:
                    entry = {
                        "tool_name": tool.get("name", ""),
                        "file": tool.get("file", ""),
                        "description": tool.get("description", "")[:120] + ("..." if len(tool.get("description", "")) > 120 else ""),
                        "context": match["context"],
                        "matched_text": match["matched_text"]
                    }
                    issues_by_type.setdefault(issue_type, []).append(entry)
    # 2. Ghi section Result by rules
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("*Result by rules:*\n\n")
        for issue_type, entries in issues_by_type.items():
            f.write(f"- {issue_type}\n")
            for entry in entries:
                f.write(to_markdown_tool_entry(entry['tool_name'], entry['file'], entry['description']) + "\n")
        if not issues_by_type:
            f.write("- No issues detected by rules.\n")
        f.write("\n")
    # 3. Cross-check by gemini
    with open(output_path, "a", encoding="utf-8") as f:
        f.write("*Cross-check by gemini:*\n\n")
        for issue_type, entries in issues_by_type.items():
            f.write(f"- {issue_type}\n")
            for entry in entries:
                prompt = f"The following tool was flagged as a possible {issue_type} by an automated security scanner.\nPlease answer YES or NO: Is this a real security risk? Explain briefly.\n\nDescription/context:\n{entry['context']}\n"
                print(f"\n===== GEMINI PROMPT for {issue_type} ({entry['tool_name']}) =====\n")
                print(prompt)
                gemini_answer = ask_gemini(prompt)
                print("\n===== GEMINI RESULT =====\n")
                print(gemini_answer)
                status = "YES" if gemini_answer.strip().upper().startswith("YES") else ("NO" if gemini_answer.strip().upper().startswith("NO") else "?")
                f.write(to_markdown_gemini_entry(entry['tool_name'], entry['file'], status, gemini_answer) + "\n")
        if not issues_by_type:
            f.write("- No issues to cross-check.\n")

if __name__ == "__main__":
    RESULTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
    for repo_name in os.listdir(RESULTS_ROOT):
        repo_dir = os.path.join(RESULTS_ROOT, repo_name)
        if not os.path.isdir(repo_dir):
            continue
        tool_def_path = os.path.join(repo_dir, 'tool_definitions.json')
        if not os.path.isfile(tool_def_path):
            continue
        print(f"[CHECK] {repo_name}")
        output_path = os.path.join(repo_dir, 'security_report.md')
        scan_tools_rules_nlp_and_gemini(tool_def_path, output_path)
        print(f"[DONE] {repo_name} -> {output_path}") 
