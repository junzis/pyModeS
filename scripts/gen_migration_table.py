"""Generate the renamed-keys markdown table for docs/migration.md.

Reads ``pymodes._v2_compat.V2_DEPRECATED_KEYS`` and writes a markdown
table between marker comments in ``docs/migration.md``::

    <!-- RENAMED KEYS START -->
    ...generated content...
    <!-- RENAMED KEYS END -->

Run manually whenever ``V2_DEPRECATED_KEYS`` changes. Not run in CI.

    uv run python scripts/gen_migration_table.py

Handles the empty-table case: if ``V2_DEPRECATED_KEYS`` is empty
(as of Plan 5 Task 1.5), the generator emits a header row plus a
single "no keys were renamed" note so the migration guide still
renders cleanly without a broken table.
"""

from __future__ import annotations

import re
from pathlib import Path

from pymodes._v2_compat import V2_DEPRECATED_KEYS

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = REPO_ROOT / "docs" / "migration.md"

START_MARKER = "<!-- RENAMED KEYS START -->"
END_MARKER = "<!-- RENAMED KEYS END -->"


def _build_table() -> str:
    if not V2_DEPRECATED_KEYS:
        return (
            "_No pyModeS 2.21.1 field names were renamed in v3. The field-"
            "name surface is identical across the two versions; only the "
            "invocation shape changed (function-per-field → single "
            "`decode()`). See the equivalence table above._"
        )
    lines = [
        "| pyModeS 2.x key | pymodes 3 key | Notes |",
        "|---|---|---|",
    ]
    for v2_key in sorted(V2_DEPRECATED_KEYS.keys()):
        v3_key = V2_DEPRECATED_KEYS[v2_key]
        if v3_key is None:
            lines.append(
                f"| `{v2_key}` | *(dropped)* | v3 intentionally omits this field |"
            )
        else:
            lines.append(f"| `{v2_key}` | `{v3_key}` | — |")
    return "\n".join(lines)


def main() -> None:
    if not MIGRATION_PATH.exists():
        raise SystemExit(f"migration file not found: {MIGRATION_PATH}")
    content = MIGRATION_PATH.read_text()

    if START_MARKER not in content or END_MARKER not in content:
        raise SystemExit(
            f"migration file missing markers; expected {START_MARKER} and {END_MARKER}"
        )

    table = _build_table()
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    replacement = f"{START_MARKER}\n{table}\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)
    MIGRATION_PATH.write_text(new_content)
    print(f"Updated {MIGRATION_PATH} with {len(V2_DEPRECATED_KEYS)} renamed keys")


if __name__ == "__main__":
    main()
