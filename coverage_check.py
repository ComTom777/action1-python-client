"""Diffs this client's implemented (method, path) pairs against Action1's real OpenAPI spec.

Run after adding/changing endpoints: ``python coverage_check.py``.
"""

import glob
import json
import re

SPEC_PATH = r"D:\Новая папка\action1\action1_openapi_spec.json"
SRC_GLOB = r"D:\Новая папка\action1\action1-python-client\src\action1_client\**\*.py"

spec = json.load(open(SPEC_PATH, encoding="utf-8"))

spec_ops = []
for path, methods in spec["paths"].items():
    norm = re.sub(r"\{[^}]+\}", "{}", path)
    for method, op in methods.items():
        if method.lower() in ("get", "post", "patch", "put", "delete"):
            spec_ops.append(
                {
                    "method": method.upper(),
                    "norm": norm,
                    "path": path,
                    "opId": op.get("operationId", ""),
                    "summary": op.get("summary", ""),
                }
            )

# A path can be a literal spanning several adjacent (implicitly-concatenated) f-strings,
# e.g. `f"/a/{x}"\n    f"/b/{y}"`, or a `path = ...`-assigned local variable reused across a
# few calls (packages.py's chunked-upload flow). Both are resolved before matching.
STR = r'f?"[^"]*"'
CONCAT = rf"(?:{STR}\s*)+"


def resolve(concat: str) -> str:
    return "".join(re.findall(r'"([^"]*)"', concat))


implemented = set()
implemented.add(("POST", "/oauth2/token"))  # handled by _http.py's _ensure_token, not a resource

for file_path in glob.glob(SRC_GLOB, recursive=True):
    src = open(file_path, encoding="utf-8").read()

    # (position, value) of every `path = ...` assignment, in source order, so each usage
    # resolves against the nearest *preceding* assignment rather than a file-wide last-wins
    # value (two functions in the same file can each bind their own local `path`).
    assignments = [
        (m.start(), resolve(m.group(1)))
        for m in re.finditer(rf"^\s*path = ({CONCAT})", src, re.MULTILINE)
    ]

    def resolve_var_at(pos: int) -> str:
        value = ""
        for start, val in assignments:
            if start > pos:
                break
            value = val
        return value

    def path_or_var(group: str, pos: int) -> str:
        return resolve_var_at(pos) if group == "path" else resolve(group)

    for m in re.finditer(
        rf'self\._request\(\s*\n?\s*"(GET|POST|PATCH|PUT|DELETE)",\s*\n?\s*({CONCAT}|path)', src
    ):
        implemented.add((m.group(1), path_or_var(m.group(2), m.start())))
    for m in re.finditer(rf"self\.paginate\(\s*({CONCAT})", src):
        implemented.add(("GET", resolve(m.group(1))))
    for m in re.finditer(rf"self\.get\(\s*({CONCAT})", src):
        implemented.add(("GET", resolve(m.group(1))))
    for m in re.finditer(rf"self\.post\(\s*\n?\s*({CONCAT})", src):
        implemented.add(("POST", resolve(m.group(1))))
    for m in re.finditer(rf"self\.patch\(\s*({CONCAT})", src):
        implemented.add(("PATCH", resolve(m.group(1))))
    for m in re.finditer(rf"self\.put\(\s*\n?\s*({CONCAT}|path)", src):
        implemented.add(("PUT", path_or_var(m.group(1), m.start())))
    for m in re.finditer(rf"self\.delete\(\s*({CONCAT})", src):
        implemented.add(("DELETE", resolve(m.group(1))))


def norm_impl(p: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", p)


implemented_norm = {(m, norm_impl(p)) for m, p in implemented}

print(f"Spec operations: {len(spec_ops)}")
print(f"Implemented (method,path) pairs found in source: {len(implemented_norm)}")
print()

missing = [op for op in spec_ops if (op["method"], op["norm"]) not in implemented_norm]
if missing:
    print("=== MISSING FROM CLIENT ===")
    for op in missing:
        print(f"{op['method']:6} {op['path']:65} {op['opId']:55} {op['summary']}")
    print()
print(f"Missing count: {len(missing)} / {len(spec_ops)}")
