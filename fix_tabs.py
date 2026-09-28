"""Fix tab/space indentation in apply_m21.py."""

from pathlib import Path

src = Path("apply_m21.py")
if not src.exists():
    print("ERROR: apply_m21.py not found")
    raise SystemExit(1)

text = src.read_text(encoding="utf-8")

# Replace all tabs with 4 spaces
fixed = text.replace("\t", "    ")

# Fix the specific broken line if it exists
fixed = fixed.replace(
    "    return 1    append_pyproject()",
    "            return 1\n\n    append_pyproject()",
)
fixed = fixed.replace(
    "    return 1\tappend_pyproject()",
    "            return 1\n\n    append_pyproject()",
)

src.write_text(fixed, encoding="utf-8")
print("OK: tabs replaced with 4 spaces")
print("Lines:", len(fixed.splitlines()))

# Try to compile
try:
    compile(fixed, str(src), "exec")
    print("OK: apply_m21.py compiles")
except SyntaxError as e:
    print(f"SYNTAX ERROR at line {e.lineno}: {e.msg}")
    print(f"  Context: {e.text}")