# MCP Security Vulnerability Report
**File:** `results\ipfs_embeddings_py\tool_definitions.json`
**Time:** `2025-06-21 04:15:49`


## Path Traversal & Arbitrary File Read
- **Tool:** `event` (ipfs_embeddings_py\llama_index\core\callbacks\base.py)
    - ..
        ...d={key, val}) as event:                 ...                 event.on_end(payload={...
- **Tool:** `event` (ipfs_embeddings_py\llama_index\legacy\callbacks\base.py)
    - ..
        ...d={key, val}) as event:                 ...                 event.on_end(payload={...
- **Tool:** `from_credentials` (ipfs_embeddings_py\llama_index\legacy\embeddings\bedrock.py)
    - ..
        ...cally          Example:                 .. code-block:: python...
- **Tool:** `from_es_connection` (ipfs_embeddings_py\llama_index\legacy\embeddings\elasticsearch.py)
    - ..
        ...ng class.          Example:             .. code-block:: python                  fr...
- **Tool:** `from_credentials` (ipfs_embeddings_py\llama_index\legacy\embeddings\elasticsearch.py)
    - ..
        ...password.          Example:             .. code-block:: python                  fr...
- **Tool:** `activate_lm_format_enforcer` (ipfs_embeddings_py\llama_index\legacy\prompts\lmformatenforcer_utils.py)
    - ..
        ...rmat_enforcer_fn):         llm.complete(...)...
- **Tool:** `schema` (ipfs_embeddings_py\marshmallow\fields.py)
    - ..
        ...The nested Schema object.          .. versionchanged:: 1.0.0             Rena...
- **Tool:** `from_dict` (ipfs_embeddings_py\marshmallow\schema.py)
    - ..
        ...given a dictionary of fields.          .. code-block:: python              from m...
    - ..
        ...the ``repr`` for the class.          .. versionadded:: 3.0.0          cls...