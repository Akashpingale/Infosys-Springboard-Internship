import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATTERNS = {
    "google AIza": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "gemini AQ.": re.compile(r"(?<![0-9A-Za-z])AQ\.[0-9A-Za-z_\-]{20,}"),
    "groq gsk_": re.compile(r"gsk_[0-9A-Za-z]{16,}"),
    "tavily tvly-": re.compile(r"tvly-[0-9A-Za-z_\-]{10,}"),
    "sk-": re.compile(r"(?<![0-9A-Za-z])sk-[0-9A-Za-z_\-]{20,}"),
    "bearer": re.compile(r"(?i)\bbearer\s+[0-9A-Za-z._~+/\-]{20,}=*"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def env_file(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return base.startswith(".env") and base != ".env.example"


raw = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
names = sorted({n for n in raw.decode("utf-8").split("\0") if n})
scanned = binary = skipped = hits = 0
for name in names:
    if env_file(name) or name.endswith(".db"):
        skipped += 1
        continue
    path = ROOT / name
    if not path.is_file():
        continue
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        binary += 1
        continue
    scanned += 1
    text = data.decode("utf-8", "replace")
    for number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                hits += 1
                value = match.group(0)
                print(f"HIT {name}:{number} {label} (length {len(value)}, starts {value[:6]!r})")
print(f"listed {len(names)}, scanned {scanned}, binary {binary}, skipped by name {skipped}, hits {hits}")
