# MCP Security Vulnerability Report
**File:** `results\dashmetrics-mcp\tool_definitions.json`
**Time:** `2025-06-21 04:15:48`


## Path Traversal & Arbitrary File Read
- **Tool:** `TypeAlias` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...Predicate: TypeAlias = Callable[..., bool]          It's invalid when used...
- **Tool:** `TypeGuard` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...Such a function should use ``TypeGuard[...]`` as its         return type to alert...
    - ..
        ...narrowed to ``str``                     ...                 else:...
    - ..
        ...rowed to ``float``.                     ...          Strict type narrowing is not...
- **Tool:** `TypeIs` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...d.  Such a function should use ``TypeIs[...]`` as its         return type to alert...
- **Tool:** `TypeForm` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...[T](typ: TypeForm[T], value: Any) -> T: ...              reveal_type(cast(int, "x"...
- **Tool:** `LiteralString` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...def query(sql: LiteralString) -> ...:               ...            query("S...
    - ..
        ...l: LiteralString) -> ...:               ...            query("SELECT * FROM table"...
- **Tool:** `Self` (venv\Lib\site-packages\typing_extensions.py)
    - ..
        ...data: bytes) -> Self:                   ...                   return self...
- **Tool:** `disabled` (venv\Lib\site-packages\attr\validators.py)
    - ..
        ...ing validators within its context.      .. warning::          This context manager...
    - ..
        ...ontext manager is not thread-safe!      .. versionadded:: 21.3.0...
- **Tool:** `in_scope` (venv\Lib\site-packages\jsonschema\validators.py)
    - ..
        ...r the duration of the context.          .. deprecated:: v4.0.0          scope...
- **Tool:** `project_name` (venv\Lib\site-packages\pip\_internal\resolution\resolvelib\base.py)
    - ..
        ...hich case ``name`` would contain the ``[...]`` part, while this         refers to...
- **Tool:** `name` (venv\Lib\site-packages\pip\_internal\resolution\resolvelib\base.py)
    - ..
        ...project_name`` would not contain the ``[...]`` part....
- **Tool:** `project_name` (venv\Lib\site-packages\pip\_internal\resolution\resolvelib\base.py)
    - ..
        ...hich case ``name`` would contain the ``[...]`` part, while this         refers to...
- **Tool:** `name` (venv\Lib\site-packages\pip\_internal\resolution\resolvelib\base.py)
    - ..
        ...project_name`` would not contain the ``[...]`` part....
- **Tool:** `TypeAlias` (venv\Lib\site-packages\pip\_vendor\typing_extensions.py)
    - ..
        ...Predicate: TypeAlias = Callable[..., bool]          It's invalid when used...
- **Tool:** `TypeGuard` (venv\Lib\site-packages\pip\_vendor\typing_extensions.py)
    - ..
        ...Such a function should use ``TypeGuard[...]`` as its         return type to alert...
    - ..
        ...narrowed to ``str``                     ...                 else:...
    - ..
        ...rowed to ``float``.                     ...          Strict type narrowing is not...
- **Tool:** `TypeIs` (venv\Lib\site-packages\pip\_vendor\typing_extensions.py)
    - ..
        ...d.  Such a function should use ``TypeIs[...]`` as its         return type to alert...
- **Tool:** `LiteralString` (venv\Lib\site-packages\pip\_vendor\typing_extensions.py)
    - ..
        ...def query(sql: LiteralString) -> ...:               ...            query("S...
    - ..
        ...l: LiteralString) -> ...:               ...            query("SELECT * FROM table"...
- **Tool:** `Self` (venv\Lib\site-packages\pip\_vendor\typing_extensions.py)
    - ..
        ...data: bytes) -> Self:                   ...                   return self...
- **Tool:** `_validate_resource_path` (venv\Lib\site-packages\pip\_vendor\pkg_resources\__init__.py)
    - ..
        ...(warned)         False         >>> vrp('../foo/bar.txt')         >>> bool(warned)...
    - ..
        ...rned)         True         >>> vrp('foo/../../bar.txt')         >>> bool(warned)...
    - ..
        ...d)         True         >>> vrp('foo/../../bar.txt')         >>> bool(warned)...
    - ..
        ...>> warned.clear()         >>> vrp('foo/f../bar.txt')         >>> bool(warned)...
    - ..
        ...ceback (most recent call last):         ...         ValueError: Use of .. or absol...
    - ..
        ......         ValueError: Use of .. or absolute path in a resource path \ i...
    - ..
        ...ceback (most recent call last):         ...         ValueError: Use of .. or absol...
    - ..
        ......         ValueError: Use of .. or absolute path in a resource path \ i...
    - ..
        ...ceback (most recent call last):         ...         AttributeError: ...          p...
    - ..
        ...t):         ...         AttributeError: ...          path...
- **Tool:** `subprocess_runner` (venv\Lib\site-packages\pip\_vendor\pyproject_hooks\_impl.py)
    - ..
        ...runner <Subprocess Runners>`.          .. code-block:: python              hook_c...
    - ..
        ...hook_caller = BuildBackendHookCaller(...)             with hook_caller.subproce...
    - ..
        ...iet_subprocess_runner):                 ...          runner...
- **Tool:** `guess_lexer` (venv\Lib\site-packages\pip\_vendor\rich\syntax.py)
    - ..
        ...ll be chosen based on the file extension..          Args:              path (AnySt...
- **Tool:** `url` (venv\Lib\site-packages\pip\_vendor\urllib3\util\url.py)
    - ..
        ...:password', 'host.com', 80,             ... '/path', 'query', 'fragment').url...

## Remote Code Execution
- **Tool:** `subprocess_runner` (venv\Lib\site-packages\pip\_vendor\pyproject_hooks\_impl.py)
    - subprocess
        ...ly overriding the default         :ref:`subprocess runner <Subprocess Runners>`....
    - Subprocess
        ...efault         :ref:`subprocess runner <Subprocess Runners>`.          .. code-block:: pyt...