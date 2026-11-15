import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATTERNS = (
    ("google", r"(?<![0-9A-Za-z])AIza[0-9A-Za-z_\-]{30,}"),
    ("gemini", r"(?<![0-9A-Za-z])AQ\.[0-9A-Za-z_\-]{20,}"),
    ("tavily", r"(?<![0-9A-Za-z])tvly-[0-9A-Za-z_\-]{10,}"),
    ("groq", r"(?<![0-9A-Za-z])gsk_[0-9A-Za-z]{20,}"),
    ("secret key", r"(?<![0-9A-Za-z])sk-(?=[0-9A-Za-z_\-]*\d)[0-9A-Za-z_\-]{20,}"),
    ("bearer", r"\b(?i:bearer)\s+(?=[0-9A-Za-z._~+/\-]*\d)[0-9A-Za-z._~+/\-]{16,}=*"),
    ("private key", "-----BEGIN [A-Z ]*" + "KEY-----"),
)
COMPILED = [(name, re.compile(pattern)) for name, pattern in PATTERNS]


def skipped(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return (base == ".env" or (base.startswith(".env.") and base != ".env.example")) or base.endswith(".db")


listed = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
names = sorted({name for name in listed.decode("utf-8").split("\0") if name})
scanned = binary = hits = 0
excluded = [name for name in names if skipped(name)]
for name in names:
    path = ROOT / name
    if skipped(name) or not path.is_file():
        continue
    data = path.read_bytes()
    if b"\0" in data[:4096]:
        binary += 1
        continue
    text = data.decode("utf-8", "ignore")
    scanned += 1
    for label, pattern in COMPILED:
        count = len(pattern.findall(text))
        if count:
            hits += count
            print(f"{name}: {label} x{count}")
print(f"files listed {len(names)}, scanned {scanned}, binary skipped {binary}, excluded by name {len(excluded)}")
print("excluded:", ", ".join(excluded) or "none")
print(f"total hits {hits}")
