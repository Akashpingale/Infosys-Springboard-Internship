import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE / "compare_api.py").read_text(encoding="utf-8")
source = source.replace('"post-api.json"', '"final-api.json"').replace('"post-openapi.json"', '"final-openapi.json"')
exec(compile(source, "compare_api.py(final)", "exec"), {"__file__": str(HERE / "compare_api.py"), "__name__": "__main__"})

base = json.loads((HERE / "baseline-api.json").read_text(encoding="utf-8"))
final = json.loads((HERE / "final-api.json").read_text(encoding="utf-8"))
print("detail.constraints =", json.dumps(final["run_detail"]["body"].get("constraints")))
print("stages before == after:", base["run_detail"]["body"]["stages"] == final["run_detail"]["body"]["stages"])
print("result before == after:", base["run_detail"]["body"]["result"] == final["run_detail"]["body"]["result"])
print("post_runs before/after:", base["post_runs"], "|", final["post_runs"])
print("meta keys before:", base["meta"]["top_level_keys"])
print("meta keys after :", final["meta"]["top_level_keys"])
print("meta.stages unchanged:", base["meta"]["body"]["stages"] == final["meta"]["body"]["stages"])
print("final == coder post capture:",
      json.loads((HERE / "post-api.json").read_text(encoding="utf-8")) | {"label": "x"} == final | {"label": "x"})
