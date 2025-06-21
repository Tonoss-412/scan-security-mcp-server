import os
import git
import json
import shutil
from tree_sitter import Parser
from tree_sitter_languages import get_language
import re
import ast
import stat
import csv

PY_LANGUAGE = get_language('python')
JS_LANGUAGE = get_language('javascript')
TS_LANGUAGE = get_language('typescript')
parser = Parser()

LANGUAGE_MAP = {
    '.py': PY_LANGUAGE,
    '.js': JS_LANGUAGE,
    '.ts': TS_LANGUAGE,
}

def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)

def ast_literal_to_dict(node, code):
    # Parse Python dict AST node to Python dict (simple, only string keys/values, nested dicts)
    def get_text(n):
        return code[n.start_byte:n.end_byte]
    if node.type == 'dictionary':
        d = {}
        # children: '{', (pair, ...), '}'
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
    # Tìm node gán biến name = ... ở cấp module
    for node in walk(tree.root_node):
        if node.type == 'assignment':
            left = node.child_by_field_name('left')
            right = node.child_by_field_name('right')
            if left and right and code[left.start_byte:left.end_byte] == name:
                return right
    return None

def extract_python_tools(tree, code, file_path):
    tools = []
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

    for node in walk(tree.root_node):
        if node.type == "decorated_definition":
            decorators = [c for c in node.children if c.type == "decorator"]
            found = False
            deco_names = []
            deco_title = None
            deco_desc = None
            input_schema = None
            for deco in decorators:
                deco_str = get_text(deco).replace(" ", "")
                # Nhận diện mọi decorator có dạng @xxx, @xxx.yyy, @xxx(...), @xxx.yyy(...)
                if deco_str.startswith("@"):
                    found = True
                    # Lấy tên decorator (bỏ @, lấy đến dấu '(' nếu có)
                    if "(" in deco_str:
                        deco_name = deco_str[1:deco_str.find("(")]
                    else:
                        deco_name = deco_str[1:]
                    deco_names.append(deco_name)
                    # Giữ logic cũ cho .tool, .resource để parse input_schema nếu có
                    if ".tool(" in deco_str or ".resource(" in deco_str or deco_str.startswith("@tool("):
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
            # Nếu không có input_schema trong decorator, sinh từ signature + docstring
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
                "file": file_path,
                "decorator": deco_names
            }
            tools.append(tool_info)
        # 2. Tool(...) khởi tạo trực tiếp
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

def ast_js_object_to_dict(node, code):
    # Parse JS/TS object literal AST node to dict (simple, only string keys/values, nested objects)
    def get_text(n):
        return code[n.start_byte:n.end_byte]
    if node.type == 'object':
        d = {}
        for pair in node.named_children:
            if pair.type == 'pair':
                k_node = pair.child_by_field_name('key')
                v_node = pair.child_by_field_name('value')
                if k_node and v_node:
                    k = get_text(k_node).strip('"\'')
                    if v_node.type == 'string':
                        v = get_text(v_node).strip('"\'')
                    elif v_node.type == 'number':
                        try:
                            v = int(get_text(v_node))
                        except Exception:
                            v = get_text(v_node)
                    elif v_node.type == 'true':
                        v = True
                    elif v_node.type == 'false':
                        v = False
                    elif v_node.type == 'object':
                        v = ast_js_object_to_dict(v_node, code)
                    else:
                        v = get_text(v_node)
                    d[k] = v
        return d
    return None

def find_js_assignment(name, tree, code):
    # Tìm node gán biến name = ... ở cấp module
    for node in walk(tree.root_node):
        if node.type == 'lexical_declaration':
            for decl in node.named_children:
                if decl.type == 'variable_declarator':
                    id_node = decl.child_by_field_name('name')
                    val_node = decl.child_by_field_name('value')
                    if id_node and val_node and code[id_node.start_byte:id_node.end_byte] == name:
                        return val_node
    return None

def extract_js_tools(tree, code, file_path):
    tools = []
    def get_text(node):
        return code[node.start_byte:node.end_byte]
    def is_tool_object(obj_node):
        keys = set()
        for pair in obj_node.named_children:
            if pair.type == "pair":
                key = get_text(pair.child_by_field_name("key")).strip('"\'')
                keys.add(key)
        return "name" in keys and "description" in keys and "inputSchema" in keys
    def parse_tool_object(obj_node):
        name = ""
        desc = ""
        input_schema = {}
        for pair in obj_node.named_children:
            if pair.type == "pair":
                key = get_text(pair.child_by_field_name("key")).strip('"\'')
                val = pair.child_by_field_name("value")
                if key == "name":
                    name = get_text(val).strip('"\'')
                if key == "description":
                    desc = get_text(val).strip('"\'')
                if key == "inputSchema":
                    if val.type == "object":
                        input_schema = ast_js_object_to_dict(val, code)
                    else:
                        input_schema = get_text(val)
        return {
            "name": name,
            "description": desc,
            "inputSchema": input_schema,
            "file": file_path
        }
    # ĐẶC BIỆT: Quét callback của setRequestHandler(ListToolsRequestSchema, ...)
    for node in walk(tree.root_node):
        if node.type == "call_expression":
            callee = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")
            if callee and "setRequestHandler" in get_text(callee) and args:
                if args.named_children and len(args.named_children) >= 2:
                    first_arg = args.named_children[0]
                    if get_text(first_arg).strip() == "ListToolsRequestSchema":
                        cb = args.named_children[1]
                        # Duyệt mọi return_statement trong callback (function/arrow_function/async)
                        def find_return_statements(node):
                            for n in walk(node):
                                if n.type == "return_statement":
                                    yield n
                        # Nếu callback là function/arrow_function/async_function/async_arrow_function
                        if cb.type in ("function", "arrow_function", "function_declaration", "method_definition", "generator_function", "async_function", "async_arrow_function") or True:
                            for ret_node in find_return_statements(cb):
                                ret_val = ret_node.child_by_field_name("argument")
                                if ret_val and ret_val.type == "object":
                                    # Tìm trường tools
                                    for pair in ret_val.named_children:
                                        if pair.type == "pair":
                                            key = pair.child_by_field_name("key")
                                            val = pair.child_by_field_name("value")
                                            if key and get_text(key) == "tools" and val and val.type == "array":
                                                for elem in val.named_children:
                                                    if elem.type == "object" and is_tool_object(elem):
                                                        tools.append(parse_tool_object(elem))
    return tools

def parse_file(file_path, lang, file_path_relative):
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    parser.set_language(LANGUAGE_MAP[os.path.splitext(file_path)[1]])
    tree = parser.parse(code.encode())
    # Chỉ ghi tên file đã duyệt vào debug_ast.txt
    with open('debug_ast.txt', 'a', encoding='utf-8') as dbg:
        dbg.write(f"{file_path_relative}\n")
    if lang == "python":
        return extract_python_tools(tree, code, file_path_relative)
    elif lang in ["javascript", "typescript"]:
        return extract_js_tools(tree, code, file_path_relative)
    else:
        return []

def on_rm_error(func, path, exc_info):
    # Đổi quyền file rồi xóa lại
    os.chmod(path, stat.S_IWRITE)
    func(path)

def process_repo_to_result(repo_url, repo_name, results_dir):
    temp_dir = './temp_repo'
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, onerror=on_rm_error)
    print(f"Cloning {repo_url} ...")
    git.Repo.clone_from(repo_url, temp_dir)
    tools = []
    for root, _, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1]
            if ext in LANGUAGE_MAP:
                lang = 'python' if ext == '.py' else 'javascript' if ext == '.js' else 'typescript' if ext == '.ts' else None
                file_path_relative = os.path.relpath(file_path, temp_dir)
                tools.extend(parse_file(file_path, lang, file_path_relative))
    # Tạo thư mục results/{repo_name}
    repo_result_dir = os.path.join(results_dir, repo_name)
    os.makedirs(repo_result_dir, exist_ok=True)
    # Ghi tool_definitions.json
    with open(os.path.join(repo_result_dir, 'tool_definitions.json'), 'w', encoding='utf-8') as f:
        json.dump({'tools': tools}, f, indent=4)
    # Xóa temp_dir
    shutil.rmtree(temp_dir, onerror=on_rm_error)
    print(f"Done {repo_name}")

def main_from_csv(csv_file, results_dir='results'):
    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        repos = [(row['repository_name'], row['repository_url']) for row in reader]
    for repo_name, repo_url in repos:
        try:
            process_repo_to_result(repo_url, repo_name, results_dir)
        except Exception as e:
            print(f"Error processing {repo_name}: {e}")

if __name__ == "__main__":
    main_from_csv('recon_mcpserver/mcp_servers.csv', results_dir='results')