"""Renumber references in OTCHET_PO_PRAKTIKE.md to sequential order of first appearance."""
import re
import pathlib

p = pathlib.Path("OTCHET_PO_PRAKTIKE.md")
content = p.read_text("utf-8")

lines = content.split("\n")

ref_list_start = None
for i, line in enumerate(lines):
    if line.strip().startswith("# \u0421\u041f\u0418\u0421\u041e\u041a \u0418\u0421\u041f\u041e\u041b\u042c\u0417\u041e\u0412\u0410\u041d\u041d\u042b\u0425 \u0418\u0421\u0422\u041e\u0427\u041d\u0418\u041a\u041e\u0412"):
        ref_list_start = i
        break

body = "\n".join(lines[:ref_list_start])
ref_section = "\n".join(lines[ref_list_start:])

# 1. Find order of first appearance in body
seen = []
for m in re.finditer(r'\[(\d+)\]', body):
    num = int(m.group(1))
    if num not in seen:
        seen.append(num)

print(f"References in order of appearance: {seen}")
print(f"Total unique refs cited: {len(seen)}")

# 2. Build old->new mapping
old_to_new = {}
for new_num, old_num in enumerate(seen, 1):
    old_to_new[old_num] = new_num

print(f"\nMapping (old -> new):")
for old, new in sorted(old_to_new.items()):
    print(f"  [{old}] -> [{new}]")

# 3. Parse reference list items
ref_items = {}
current_num = None
current_text = []
for line in lines[ref_list_start+1:]:
    m = re.match(r'^(\d+)\.\s+(.*)$', line.strip())
    if m:
        if current_num is not None:
            ref_items[current_num] = "\n".join(current_text)
        current_num = int(m.group(1))
        current_text = [m.group(2)]
    elif current_num is not None and line.strip():
        current_text.append(line)
    elif current_num is not None and not line.strip():
        ref_items[current_num] = "\n".join(current_text)
        current_num = None
        current_text = []

if current_num is not None:
    ref_items[current_num] = "\n".join(current_text)

print(f"\nParsed {len(ref_items)} reference items from list")

# Check for refs in list but not cited
uncited = set(ref_items.keys()) - set(seen)
if uncited:
    print(f"WARNING: Uncited references: {sorted(uncited)}")
    for u in uncited:
        seen.append(u)
        old_to_new[u] = len(seen)

# 4. Replace in body: [old] -> [new] using temp placeholders
new_body = body
for old_num in sorted(old_to_new.keys(), reverse=True):
    new_num = old_to_new[old_num]
    new_body = new_body.replace(f"[{old_num}]", f"[__REF_{new_num}__]")

for new_num in range(1, len(seen) + 1):
    new_body = new_body.replace(f"[__REF_{new_num}__]", f"[{new_num}]")

# 5. Rebuild reference list in new order
new_ref_lines = [lines[ref_list_start], ""]
for new_num, old_num in enumerate(seen, 1):
    if old_num in ref_items:
        new_ref_lines.append(f"{new_num}. {ref_items[old_num]}")
        new_ref_lines.append("")
    else:
        print(f"WARNING: Reference [{old_num}] cited but not in list!")

new_content = new_body + "\n" + "\n".join(new_ref_lines)
p.write_text(new_content, "utf-8")

print(f"\nDone! Renumbered {len(old_to_new)} references.")
print(f"New file: {len(new_content)} chars")
