import os
import re
import ast
import git
import json
import stat
import shutil
import subprocess

# --- Tree-sitter setup đơn giản như extract_mcp_tools_all.py ---
from tree_sitter import Parser
from tree_sitter_languages import get_language

PY_LANGUAGE = get_language('python')
parser = Parser()
LANGUAGE_MAP = {'.py': PY_LANGUAGE}

# --- AST Utilities ---
def walk_ast(node):
    yield node
    for child in node.children:
        yield from walk_ast(child)

def ast_literal_to_dict(node, code):
    def get_text(n):
        return code[n.start_byte:n.end_byte]
    if node.type == 'dictionary':
        d = {}
        for pair in node.named_children:
            if pair.type == 'pair':
                k_node = pair.child_by_field_name('key')
                v_node = pair.child_by_field_name('value')
                if k_node and v_node:
                    k = get_text(k_node).strip('"\'')
                    if v_node.type == 'string':
                        v = get_text(v_node).strip('"\'')
                    elif v_node.type == 'integer':
                        v = int(get_text(v_node))
                    elif v_node.type == 'true':
                        v = True
                    elif v_node.type == 'false':
                        v = False
                    elif v_node.type == 'dictionary':
                        v = ast_literal_to_dict(v_node, code)
                    else:
                        v = get_text(v_node)
                    d[k] = v
        return d
    return None

def find_assignment(name, tree, code):
    for node in walk_ast(tree.root_node):
        if node.type == 'assignment':
            left = node.child_by_field_name('left')
            right = node.child_by_field_name('right')
            if left and right and code[left.start_byte:left.end_byte] == name:
                return right
    return None

# --- Tool Extraction với Tree-sitter (copy từ extract_mcp_tools_all.py) ---
def extract_python_tools(tree, code, file_path):
    def get_text(node):
        return code[node.start_byte:node.end_byte]
    def pytype_to_jsonschema(ptype):
        if not ptype:
            return "string"
        ptype = ptype.lower()
        if ptype in ("str", "string"): return "string"
        if ptype in ("int", "integer"): return "integer"
        if ptype in ("float", "number"): return "number"
        if ptype in ("bool", "boolean"): return "boolean"
        return "string"
    def parse_google_args(docstring):
        args = {}
        if not docstring:
            return args
        m = re.search(r"Args?:\s*(.*?)(^\S|\Z)", docstring, re.DOTALL | re.MULTILINE)
        if not m:
            return args
        argblock = m.group(1)
        for line in argblock.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            m2 = re.match(r"(\w+)\s*\(([^)]*)\)\s*:\s*(.*)", line)
            if m2:
                name, typ, desc = m2.groups()
                typ = typ.replace(", optional", "").strip()
                required = "optional" not in line.lower()
                args[name] = {"type": typ, "desc": desc, "required": required}
            else:
                m3 = re.match(r"(\w+)\s*:\s*(.*)", line)
                if m3:
                    name, desc = m3.groups()
                    args[name] = {"type": None, "desc": desc, "required": True}
        return args
    tools = []
    for node in walk_ast(tree.root_node):
        if node.type == "decorated_definition":
            decorators = [c for c in node.children if c.type == "decorator"]
            found = False
            deco_title = None
            deco_desc = None
            input_schema = None
            for deco in decorators:
                deco_str = get_text(deco).replace(" ", "")
                if ".tool(" in deco_str or ".resource(" in deco_str or deco_str.startswith("@tool("):
                    found = True
                    for arg in deco.children:
                        if arg.type == "argument_list":
                            for kwarg in arg.named_children:
                                if kwarg.type == "keyword_argument":
                                    key = kwarg.child_by_field_name("name")
                                    if key and get_text(key) == "input_schema":
                                        val = kwarg.child_by_field_name("value")
                                        if val.type == "dictionary":
                                            input_schema = ast_literal_to_dict(val, code)
                                        elif val.type == "identifier":
                                            assign_node = find_assignment(get_text(val), tree, code)
                                            if assign_node and assign_node.type == "dictionary":
                                                input_schema = ast_literal_to_dict(assign_node, code)
                                        elif val.type == "string":
                                            import json as _json
                                            try:
                                                input_schema = _json.loads(get_text(val))
                                            except Exception:
                                                input_schema = get_text(val)
                    if "(" in deco_str and ")" in deco_str:
                        inside = deco_str[deco_str.find("(")+1:deco_str.rfind(")")]
                        if "title=" in inside:
                            deco_title = inside.split("title=")[1].split(",")[0].strip("'\"")
                        if "description=" in inside:
                            deco_desc = inside.split("description=")[1].split(",")[0].strip("'\"")
            if not found:
                continue
            func_node = next((c for c in node.children if c.type == "function_definition"), None)
            if not func_node:
                continue
            name = None
            for child in func_node.children:
                if child.type == "identifier":
                    name = get_text(child)
                    break
            docstring = ""
            suite = [c for c in func_node.children if c.type == "block"]
            if suite:
                first_stmt = suite[0].children[0] if suite[0].children else None
                if first_stmt and first_stmt.type == "expression_statement":
                    expr = first_stmt.children[0] if first_stmt.children else None
                    if expr and expr.type == "string":
                        docstring = get_text(expr).strip('"\'')
            if input_schema is None:
                input_schema = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                doc_args = parse_google_args(docstring)
                parameters = [c for c in func_node.children if c.type == "parameters"]
                if parameters:
                    for param in parameters[0].children:
                        if param.type == "identifier":
                            pname = get_text(param)
                            if pname != "self":
                                ptype = doc_args.get(pname, {}).get("type")
                                desc = doc_args.get(pname, {}).get("desc")
                                required = doc_args.get(pname, {}).get("required", True)
                                input_schema["properties"][pname] = {"type": pytype_to_jsonschema(ptype)}
                                if desc:
                                    input_schema["properties"][pname]["description"] = desc
                                if required:
                                    input_schema["required"].append(pname)
                        elif param.type == "typed_parameter":
                            id_node = param.child_by_field_name("name")
                            type_node = param.child_by_field_name("type")
                            default_node = param.child_by_field_name("default")
                            if id_node:
                                pname = get_text(id_node)
                                ptype = get_text(type_node) if type_node else doc_args.get(pname, {}).get("type")
                                desc = doc_args.get(pname, {}).get("desc")
                                required = doc_args.get(pname, {}).get("required", default_node is None)
                                js_type = pytype_to_jsonschema(ptype)
                                if pname != "self":
                                    input_schema["properties"][pname] = {"type": js_type}
                                    if desc:
                                        input_schema["properties"][pname]["description"] = desc
                                    if default_node is not None:
                                        try:
                                            input_schema["properties"][pname]["default"] = ast.literal_eval(get_text(default_node))
                                        except Exception:
                                            input_schema["properties"][pname]["default"] = get_text(default_node)
                                    if required:
                                        input_schema["required"].append(pname)
                if "required" in input_schema and not input_schema["required"]:
                    input_schema.pop("required")
            if not input_schema["properties"] and docstring:
                doc_args = parse_google_args(docstring)
                for pname, info in doc_args.items():
                    input_schema["properties"][pname] = {"type": pytype_to_jsonschema(info.get("type"))}
                    if info.get("desc"):
                        input_schema["properties"][pname]["description"] = info["desc"]
                    if info.get("required", True):
                        if "required" not in input_schema:
                            input_schema["required"] = []
                        input_schema["required"].append(pname)
                if "required" in input_schema and not input_schema["required"]:
                    input_schema.pop("required")
            tool_info = {
                "name": deco_title or name,
                "description": deco_desc or docstring,
                "inputSchema": input_schema,
                "file": file_path
            }
            tools.append(tool_info)
        if node.type == "call":
            func = node.child_by_field_name("function")
            if func and get_text(func) == "Tool":
                kwargs = {get_text(c.child_by_field_name("name")): get_text(c.child_by_field_name("value")).strip('"\'')
                         for c in node.children if c.type == "keyword_argument"}
                if "name" in kwargs and "description" in kwargs:
                    tool_info = {
                        "name": kwargs.get("name"),
                        "description": kwargs.get("description"),
                        "inputSchema": kwargs.get("input_schema", {}),
                        "file": file_path
                    }
                    tools.append(tool_info)
    return tools

def parse_file(file_path, lang, file_path_relative):
    """Parse a file and extract tool definitions if it's Python."""
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    parser.set_language(LANGUAGE_MAP[os.path.splitext(file_path)[1]])
    tree = parser.parse(code.encode())
    if lang == "python":
        return extract_python_tools(tree, code, file_path_relative)
    return []

# --- Repo Handling ---
def on_rm_error(func, path, exc_info):
    """Handle permission error when deleting files."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def process_repo(repo_url, temp_dir):
    """
    Clone a repo, extract all Python tools, run semgrep, and return tool info list.
    """
    print(f"Đang xử lý {repo_url}...")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, onerror=on_rm_error)
    git.Repo.clone_from(repo_url, temp_dir)
    tools = []
    for root, _, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1]
            if ext in ['.py']:  # Chỉ xử lý file Python
                lang = 'python'
                file_path_relative = os.path.relpath(file_path, temp_dir)
                found_tools = parse_file(file_path, lang, file_path_relative)
                if found_tools:
                    tools.extend(found_tools)
    return [{'repo': repo_url, **tool} for tool in tools]

def process_local_repo(local_path):
    """
    Process a local repository directory.
    """
    # Chuẩn hóa đường dẫn
    local_path = os.path.abspath(os.path.expanduser(local_path))
    
    if not os.path.exists(local_path):
        print(f"Lỗi: Thư mục không tồn tại: {local_path}")
        return []
    
    if not os.path.isdir(local_path):
        print(f"Lỗi: Đường dẫn không phải thư mục: {local_path}")
        return []
    
    print(f"Đang xử lý thư mục local: {local_path}...")
    tools = []
    
    try:
        for root, dirs, files in os.walk(local_path):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1]
                if ext in ['.py']:  # Chỉ xử lý file Python
                    try:
                        lang = 'python'
                        file_path_relative = os.path.relpath(file_path, local_path)
                        found_tools = parse_file(file_path, lang, file_path_relative)
                        if found_tools:
                            tools.extend(found_tools)
                    except Exception as e:
                        print(f"Lỗi khi xử lý file {file_path}: {e}")
                        continue
    except Exception as e:
        print(f"Lỗi khi duyệt thư mục {local_path}: {e}")
        return []
    
    return [{'repo': f'local:{local_path}', **tool} for tool in tools]

# --- Main Entrypoint ---
def main(repo_urls=None, local_paths=None):
    """
    Main entry: process all repos, extract tools, write config.
    """
    all_tools = []
    
    # Process repo URLs
    if repo_urls:
        for repo_url in repo_urls:
            try:
                temp_dir = './temp_repo'
                all_tools.extend(process_repo(repo_url, temp_dir))
            except Exception as e:
                print(f"Lỗi khi xử lý repo {repo_url}: {e}")
                continue
    
    # Process local paths
    if local_paths:
        for local_path in local_paths:
            try:
                all_tools.extend(process_local_repo(local_path))
            except Exception as e:
                print(f"Lỗi khi xử lý local path {local_path}: {e}")
                continue
    
    with open('tools.json', 'w', encoding='utf-8') as f:
        json.dump({'tools': all_tools}, f, indent=4)
    print(f"Extract tools success to tools.json - Tìm thấy {len(all_tools)} tools")

if __name__ == "__main__":
    print("Extract MCP Tools")
    print("1. Extract from repo URL")
    print("2. Extract from local directory")
    
    choice = input("Chọn option (1 hoặc 2): ").strip()
    
    if choice == "1":
        input_str = input("Nhập repo mcp server url:")
        repos = [url.strip() for url in input_str.split(',') if url.strip()]
        main(repo_urls=repos)
    elif choice == "2":
        input_str = input("Nhập đường dẫn thư mục local (có thể nhiều đường dẫn cách nhau bởi dấu phẩy):")
        local_paths = [path.strip() for path in input_str.split(',') if path.strip()]
        main(local_paths=local_paths)
    else:
        print("Lựa chọn không hợp lệ!")
