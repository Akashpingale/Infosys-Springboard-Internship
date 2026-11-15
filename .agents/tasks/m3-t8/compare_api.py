import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
base = json.loads((HERE / "baseline-api.json").read_text(encoding="utf-8"))
post = json.loads((HERE / "post-api.json").read_text(encoding="utf-8"))
ADDED = {"run_detail": {"constraints"}, "meta": {"strategy", "chat"}}


def diff(name, before, after):
    added = ADDED.get(name, set())
    if name == "run_list":
        before_rows, after_rows = before["runs"], after["runs"]
        assert len(before_rows) == len(after_rows)
        for b, a in zip(before_rows, after_rows):
            assert set(a) - set(b) == {"has_strategy"} and set(b) <= set(a), (set(a), set(b))
            assert {k: a[k] for k in b} == b
            assert a["has_strategy"] is False
        return "identical apart from has_strategy=false"
    if isinstance(before, dict) and isinstance(after, dict):
        assert set(after) - set(before) == added and set(before) <= set(after), (name, set(after) ^ set(before))
        assert {k: after[k] for k in before} == before, name
        return f"identical apart from added {sorted(added)}: {[after[k] for k in sorted(added)] if name != 'meta' else 'see below'}"
    assert before == after, name
    return "identical"


for name in ("post_runs", "run_detail", "run_list", "meta"):
    for key in sorted(set(base[name]) | set(post[name])):
        if key not in ("body", "top_level_keys", "row_keys"):
            assert base[name].get(key) == post[name].get(key), (name, key)
    print(name, "wrapper fields other than body/key lists identical:",
          sorted(k for k in base[name] if k not in ("body", "top_level_keys", "row_keys")))
    print(name, "body ->", diff(name, base[name]["body"], post[name]["body"]))
print("meta.strategy =", json.dumps(post["meta"]["body"]["strategy"]))
print("meta.chat =", json.dumps(post["meta"]["body"]["chat"]))
print("checks before:", {k: v for k, v in base["checks"].items() if k not in ("openapi_paths", "openapi_schemas")})
print("checks after :", {k: v for k, v in post["checks"].items() if k not in ("openapi_paths", "openapi_schemas")})
print("new paths:", sorted(set(post["checks"]["openapi_paths"]) - set(base["checks"]["openapi_paths"])),
      "removed:", sorted(set(base["checks"]["openapi_paths"]) - set(post["checks"]["openapi_paths"])))
print("new schemas:", sorted(set(post["checks"]["openapi_schemas"]) - set(base["checks"]["openapi_schemas"])),
      "removed:", sorted(set(base["checks"]["openapi_schemas"]) - set(post["checks"]["openapi_schemas"])))

bo = json.loads((HERE / "baseline-openapi.json").read_text(encoding="utf-8"))
po = json.loads((HERE / "post-openapi.json").read_text(encoding="utf-8"))
for path, ops in bo["paths"].items():
    if path == "/api/runs":
        for method, op in ops.items():
            if method == "post":
                assert po["paths"][path][method]["responses"] == op["responses"], "POST /api/runs responses"
                continue
            assert po["paths"][path][method] == op, (path, method)
    else:
        assert po["paths"][path] == ops, path
print("existing operations unchanged (POST /api/runs responses unchanged; its description changed only)")
changed = []
for schema, body in bo["components"]["schemas"].items():
    after = po["components"]["schemas"][schema]
    if after == body:
        continue
    added = sorted(set(after.get("properties", {})) - set(body.get("properties", {})))
    for prop, value in body.get("properties", {}).items():
        assert after["properties"][prop] == value or (schema, prop) == ("RunRequest", "include_strategy") or (
            schema, prop) == ("RunRequest", "constraints"), (schema, prop)
    assert after.get("required", []) == body.get("required", []), schema
    changed.append((schema, added, [p for p in body.get("properties", {}) if after["properties"][p] != body["properties"][p]]))
print("changed schemas (added props, changed existing props):", changed)
