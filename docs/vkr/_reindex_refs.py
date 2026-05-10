"""Reindex bibliography references in OTCHET_PO_PRAKTIKE.md.

Strategy:
1. Find all [N] and [N, M] in the body text (before bibliography heading).
2. Build first-appearance order of unique source numbers.
3. Map old number -> new (first-appearance) number for cited sources.
4. For uncited sources (e.g. Recharts, React, Rosstat, PostgreSQL, SQLAlchemy),
   keep them at the end of the new list with sequential trailing numbers.
5. Apply the map to the body text.
6. Reorder bibliography list per the new numbering.

Run: python docs/vkr/_reindex_refs.py
"""
from __future__ import annotations

import re
from pathlib import Path

FILE = Path(r"c:/Users/Admin/Desktop/Diplom/docs/vkr/OTCHET_PO_PRAKTIKE.md")
BIB_HEADING = "# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"
APPENDIX_HEADING = "# ПРИЛОЖЕНИЯ"

REF_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def main() -> None:
    text = FILE.read_text(encoding="utf-8")
    bib_start = text.find(BIB_HEADING)
    if bib_start < 0:
        raise SystemExit("bibliography heading not found")
    appx_start = text.find(APPENDIX_HEADING)
    if appx_start < 0:
        raise SystemExit("appendix heading not found")

    body = text[:bib_start]
    bib_block = text[bib_start:appx_start]
    appendix = text[appx_start:]

    first_seen: dict[int, int] = {}
    for m in REF_RE.finditer(body):
        for raw in m.group(1).split(","):
            num = int(raw.strip())
            if num not in first_seen:
                first_seen[num] = m.start()

    cited_old = sorted(first_seen, key=first_seen.get)

    bib_lines = bib_block.splitlines()
    bib_entries: dict[int, list[str]] = {}
    current_num: int | None = None
    current_lines: list[str] = []
    bib_header_lines: list[str] = []
    in_entries = False
    entry_re = re.compile(r"^(\d+)\.\s")
    for line in bib_lines:
        if line.startswith("#") or (not in_entries and not entry_re.match(line)):
            bib_header_lines.append(line)
            continue
        m = entry_re.match(line)
        if m:
            if current_num is not None:
                bib_entries[current_num] = current_lines
            current_num = int(m.group(1))
            current_lines = [line]
            in_entries = True
        else:
            current_lines.append(line)
    if current_num is not None:
        bib_entries[current_num] = current_lines

    all_old_nums = sorted(bib_entries)
    cited_set = set(cited_old)
    uncited_in_order = [n for n in all_old_nums if n not in cited_set]

    new_order = cited_old + uncited_in_order
    old_to_new: dict[int, int] = {old: i + 1 for i, old in enumerate(new_order)}

    print("Mapping (old -> new):")
    for old, new in sorted(old_to_new.items()):
        if old != new:
            print(f"  [{old}] -> [{new}]")

    def replace_in_match(m: re.Match[str]) -> str:
        nums = [int(x.strip()) for x in m.group(1).split(",")]
        renumbered = [str(old_to_new[n]) for n in nums]
        return "[" + ", ".join(renumbered) + "]"

    new_body = REF_RE.sub(replace_in_match, body)

    new_bib_entries: list[str] = []
    for old in new_order:
        new_num = old_to_new[old]
        original_lines = bib_entries[old]
        first = original_lines[0]
        first = re.sub(r"^\d+\.\s", f"{new_num}. ", first)
        new_bib_entries.append(first)
        new_bib_entries.extend(original_lines[1:])

    new_bib_block = "\n".join(bib_header_lines + new_bib_entries) + "\n"
    new_text = new_body + new_bib_block + appendix

    FILE.write_text(new_text, encoding="utf-8")
    print(f"Reindexed: {len(cited_old)} cited, {len(uncited_in_order)} uncited (kept at end).")


if __name__ == "__main__":
    main()
