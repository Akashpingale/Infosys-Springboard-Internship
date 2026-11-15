import re
import sys

PATTERNS = {
    "google": r"AIza[0-9A-Za-z_\-]{20,}",
    "groq": r"gsk_[0-9A-Za-z]{20,}",
    "tavily": r"tvly-[0-9A-Za-z_\-]{10,}",
    "openai": r"sk-[0-9A-Za-z_\-]{20,}",
    "bearer": r"(?i:bearer)\s+[0-9A-Za-z._~+/\-]{16,}",
    "private": "PRIVATE" + " KEY",
}
total = 0
for path in sys.argv[1:]:
    text = open(path, encoding="utf-8").read()
    for name, pattern in PATTERNS.items():
        hits = len(re.findall(pattern, text))
        total += hits
        if hits:
            print(path, name, hits)
print("total hits", total)
