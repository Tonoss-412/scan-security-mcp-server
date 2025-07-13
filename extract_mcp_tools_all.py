import os
import re
import json
from tree_sitter import Parser
from tree_sitter_languages import get_language

PY_LANGUAGE = get_language('python')
parser = Parser()
LANGUAGE_MAP = {'.py': PY_LANGUAGE}

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'repo')
RESULTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')

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
    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()
    parser.set_language(LANGUAGE_MAP[os.path.splitext(file_path)[1]])
    tree = parser.parse(code.encode())
    if lang == "python":
        return extract_python_tools(tree, code, file_path_relative)
    return []

def process_repo_dir(repo_dir, repo_name):
    tools = []
    for root, _, files in os.walk(repo_dir):
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in LANGUAGE_MAP:
                lang = 'python'
                file_path = os.path.join(root, file)
                file_path_relative = os.path.relpath(file_path, repo_dir)
                found_tools = parse_file(file_path, lang, file_path_relative)
                if found_tools:
                    tools.extend(found_tools)
    return tools

def main():
    if not os.path.exists(RESULTS_ROOT):
        os.makedirs(RESULTS_ROOT)
    for repo_name in os.listdir(REPO_ROOT):
        repo_path = os.path.join(REPO_ROOT, repo_name)
        if not os.path.isdir(repo_path):
            continue
        print(f"[PROCESS] {repo_name}")
        tools = process_repo_dir(repo_path, repo_name)
        result_dir = os.path.join(RESULTS_ROOT, repo_name)
        os.makedirs(result_dir, exist_ok=True)
        out_path = os.path.join(result_dir, 'tool_definitions.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(tools, f, indent=2, ensure_ascii=False)
        print(f"[DONE] {repo_name}: {len(tools)} tool(s) -> {out_path}")

if __name__ == "__main__":
    main() 
