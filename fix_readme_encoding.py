from pathlib import Path
from shutil import copy2
from ftfy import fix_text

path = Path("README.md")
backup = Path("README_backup.md")

# Create backup only if one doesn't already exist
if not backup.exists():
    copy2(path, backup)
    print(f"Backup created: {backup}")
else:
    print(f"Backup already exists: {backup}")

# Read raw bytes
raw = path.read_bytes()

# Try likely encodings
encodings = [
    "utf-8-sig",
    "cp1252",
    "latin-1",
]

text = None
used_encoding = None

for encoding in encodings:
    try:
        text = raw.decode(encoding)
        used_encoding = encoding
        break
    except UnicodeDecodeError:
        continue

if text is None:
    raise RuntimeError("Could not decode README.md")

print(f"Decoded using: {used_encoding}")

# Repair broken text such as:
# Ø§Ù„...  -> Arabic
# â†’      -> →
fixed = fix_text(text)

# Save as clean UTF-8
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(fixed)

print("README.md repaired and saved as UTF-8.")
print("Original backup: README_backup.md")