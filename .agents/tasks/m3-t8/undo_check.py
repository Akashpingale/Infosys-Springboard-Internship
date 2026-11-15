import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
path = ROOT / "tests" / "test_m3_schemas.py"
data = path.read_bytes()
eol = b"\r\n" if b"\r\n" in data else b"\n"
new = eol.join([
    b'    dumped = run.model_dump(mode="json", exclude={"result"})',
    b'    assert {key: dumped[key] for key in original if key != "result"} == {key: value for key, value in original.items() if key != "result"}',
    b'    assert set(dumped) - set(original) == {"constraints"}',
    b'    assert dumped["constraints"] is None',
])
old = b'    assert run.model_dump(mode="json", exclude={"result"}) == {key: value for key, value in original.items() if key != "result"}'
assert data.count(new) == 1
undone = data.replace(new, old)
print("current", hashlib.sha256(data).hexdigest().upper())
print("undone ", hashlib.sha256(undone).hexdigest().upper())
print("before ", hashlib.sha256((ROOT / ".agents/tasks/m3-t8/test_m3_schemas.before.py.txt").read_bytes()).hexdigest().upper())
print("undone == before:", undone == (ROOT / ".agents/tasks/m3-t8/test_m3_schemas.before.py.txt").read_bytes())
