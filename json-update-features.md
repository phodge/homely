# Design: JSON Update Features (`json_set` and `json_append`)

## Problem

Managing JSON config files (e.g. `~/.claude/settings.json`) from a dotfiles repo
requires reading the file, modifying its structure, and writing it back. Done manually,
this is repetitive and error-prone — especially when Homely's automatic-undo requirement
means we must also track what we changed so we can reverse it when the user removes that
config.

## Solution

Two new public functions following Homely's existing Helper + Cleaner pattern:

- **`json_set(file_path, schema_path, new_value)`** — overwrite a single path in a JSON
  file with a new value, obliterating whatever was there before.
- **`json_append(file_path, schema_path, value, key=None, prepend=False)`** — insert a
  scalar or object into a JSON array, with set semantics (no duplicates) and optional
  key-based matching for objects.

Each function registers a Cleaner that knows exactly how to reverse its own change.

## Why Not `jsonpatch`?

`jsonpatch` (RFC 6902) was considered but rejected for this API because:

1. **`json_set`** already knows the exact path and values — there is nothing for a diff
   library to compute.
2. **`json_append`** needs *value/key* semantics for arrays, but RFC 6902 addresses array
   items by *index* (e.g. `/allow/2`). If another process inserts an item earlier in the
   array, an index-based undo patch would remove the wrong element.

`jsonpointer` (the path-navigation sub-library that `jsonpatch` depends on, RFC 6901)
*may* be useful for navigating nested paths. Alternatively, path navigation can be
implemented in ~10 lines: split on `/`, resolve each segment, handle `~0` (`~`) and `~1`
(`/`) escapes. The decision on whether to take the dependency is left to implementation.

---

## `json_set`

### User API

```python
from homely.jsonfile import json_set

# Overwrite /permissions with a new dict, replacing whatever was there.
json_set("~/.claude/settings.json", "/permissions", {
    "allow": ["Bash(git:*)"],
    "deny": [],
})
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `file_path` | `str` | Path to the JSON file. Supports `~` and env-var expansion. Created if absent. |
| `schema_path` | `str` | RFC 6901 JSON Pointer to the target location, e.g. `/permissions/allow`. |
| `new_value` | `Any` | The value to write. Any JSON-serialisable type. |

### Apply behaviour

1. Read and parse the file (empty object `{}` if file is absent).
2. Navigate to `schema_path`. Record `before` (the existing value, or `None`) and
   `was_absent` (whether the key existed at all).
3. Set the value at `schema_path` to `new_value`.
4. Write the file atomically via the existing `filereplacer()` utility.
5. Return a `CleanSetJson` cleaner carrying the recorded `before`/`was_absent` state.

`isdone()` returns `True` if the current value at `schema_path` already equals
`new_value` (deep equality).

### Cleaner storage

```json
{
  "file":       "~/.claude/settings.json",
  "schema_path": "/permissions",
  "before":     {"allow": [], "deny": []},
  "was_absent": false
}
```

### Undo behaviour (`CleanSetJson.makechanges`)

1. Read and parse the file.
2. Navigate to `schema_path` and read the current value.
3. If the current value equals `new_value` (what we set it to):
   - If `was_absent`: delete the key.
   - Else: restore `before`.
4. If the current value differs from `new_value`, a third party modified it. Skip the
   undo and emit a warning — do not clobber the third-party change.
5. Write atomically.

`isneeded()` returns `True` if the current value at `schema_path` equals `new_value`.

---

## `json_append`

### User API

```python
from homely.jsonfile import json_append

# Append a scalar; no-op if already present.
json_append("~/.claude/settings.json", "/permissions/allow", "Bash(npm:*)")

# Prepend instead of append.
json_append("~/.claude/settings.json", "/permissions/allow", "Bash(npm:*)", prepend=True)

# Object item — use "name" key for duplicate detection.
# If an entry with name="my-server" already exists, overwrite it.
json_append("~/.claude/mcpServers", "/servers", {"name": "my-server", "url": "..."}, key="name")
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `file_path` | `str` | Path to the JSON file. Supports `~` and env-var expansion. Created if absent. |
| `schema_path` | `str` | RFC 6901 JSON Pointer to a list within the file, e.g. `/permissions/allow`. |
| `value` | `scalar \| dict` | The item to insert. |
| `key` | `str \| None` | Object key to use for duplicate detection and replacement. Only valid when `value` is a dict. When `None`, equality of the whole value is used. |
| `prepend` | `bool` | If `True`, insert at index 0; otherwise append to end. Default `False`. |

### Apply behaviour

1. Read and parse the file. The target `schema_path` must resolve to a list (or the path
   must be absent, in which case an empty list is created).
2. **Duplicate detection:**
   - If `key` is set: search the list for an existing item where `item[key] == value[key]`.
     - If found: record `replaced_value = existing_item`, then overwrite it in-place.
     - If not found: insert as a fresh item (append or prepend per `prepend`).
   - If `key` is `None`: search for an item equal to `value`.
     - If found: no-op (already present). `isdone()` returns `True`.
     - If not found: insert as a fresh item.
3. Write atomically.
4. Return a `CleanAppendJson` cleaner.

`isdone()` returns `True` if the target list already contains the value (or an item
matching on `key`).

### Cleaner storage

Fresh insert (no key, scalar):
```json
{
  "file":          "~/.claude/settings.json",
  "schema_path":   "/permissions/allow",
  "value":         "Bash(npm:*)",
  "key":           null,
  "replaced_value": null
}
```

Object replace via key:
```json
{
  "file":           "~/.claude/settings.json",
  "schema_path":    "/servers",
  "value":          {"name": "my-server", "url": "https://new.example.com"},
  "key":            "name",
  "replaced_value": {"name": "my-server", "url": "https://old.example.com"}
}
```

### Undo behaviour (`CleanAppendJson.makechanges`)

1. Read and parse the file; navigate to `schema_path`.
2. **If `replaced_value` is not `None`** (we overwrote an existing item):
   - Locate the current item matching on `key`.
   - If its full value equals `value` (what we wrote), restore `replaced_value` in-place.
   - If it was modified by a third party, skip and warn.
3. **If `replaced_value` is `None`** (we freshly inserted an item):
   - If `key` is set: remove the item where `item[key] == value[key]`, but only if its
     full value still equals `value`. If modified by a third party, skip and warn.
   - If `key` is `None`: remove the first item equal to `value`. If not found, no-op.
4. Write atomically.

`isneeded()` returns `True` if:
- `replaced_value` is not `None` and the list contains an item matching on `key` whose
  value equals `value` (i.e. we need to restore the original).
- `replaced_value` is `None` and the list contains `value` (i.e. we inserted it and it's
  still there).

---

## File Layout

```
homely/
  jsonfile.py          # json_set(), json_append(), helpers, cleaners, path navigation

test/unit/homely/
  test_jsonfile.py     # unit tests (see below)
```

No new dependencies are strictly required. `jsonpointer` may be added if its path
navigation is preferred over a bespoke implementation.

---

## Test Coverage (`test_jsonfile.py`)

### `json_set` tests

| Test | Scenario |
|---|---|
| `test_set_new_key` | File exists, key absent — key is created, undo removes it |
| `test_set_existing_key` | File exists, key present — value replaced, undo restores original |
| `test_set_creates_file` | File absent — file is created, undo removes the file |
| `test_set_nested_path` | Path like `/a/b/c` — intermediate dicts created as needed |
| `test_set_isdone` | Value already correct — `isdone()` returns `True`, `makechanges()` is skipped |
| `test_set_undo_skips_third_party_change` | Value was changed externally — undo skips and warns |
| `test_set_invalid_json` | File contains invalid JSON — error raised, file not modified |

### `json_append` tests

| Test | Scenario |
|---|---|
| `test_append_scalar_fresh` | Item not in list — appended, undo removes it |
| `test_append_scalar_duplicate` | Item already in list — `isdone()` True, no change |
| `test_prepend_scalar` | `prepend=True` — item inserted at index 0 |
| `test_append_object_no_key` | Object without `key` — equality-based dedup |
| `test_append_object_with_key_fresh` | Object with `key`, no match — appended |
| `test_append_object_with_key_replace` | Object with `key`, match found — replaced, undo restores original |
| `test_append_creates_list` | `schema_path` absent — empty list created then item appended |
| `test_append_creates_file` | File absent — file + list created, undo removes file |
| `test_append_undo_skips_third_party_change` | Item modified externally — undo skips and warns |
| `test_append_isdone_after_apply` | After `makechanges()`, `isdone()` returns `True` |

---

## Open Questions

1. **Path creation depth**: Should `json_set("/a/b/c", value)` create intermediate keys
   `a` and `b` if absent? Proposed: yes, for usability. Each intermediate creation is
   recorded so undo can remove them if they were absent before.

2. **`jsonpointer` dependency**: Take the lightweight dep for robust RFC 6901 path
   handling, or implement the ~10-line subset we need ourselves?

3. **Warning mechanism**: When undo skips due to a third-party change, should it use
   Python `warnings.warn`, print to stderr, or hook into Homely's existing reporting?
   Needs alignment with how other Cleaners surface non-fatal issues.
