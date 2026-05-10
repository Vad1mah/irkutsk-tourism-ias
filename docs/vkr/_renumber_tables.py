"""Renumber tables 7, 11..18 -> 1..9 (contiguous).

Replaces only in 'Таблица N', 'таблице N', 'таблицу N', 'таблицы N', 'таблиц N',
not arbitrary numeric occurrences.
"""
from pathlib import Path
import re

FILE = Path(r"c:/Users/Admin/Desktop/Diplom/docs/vkr/OTCHET_PO_PRAKTIKE.md")

mapping = {7: 1, 11: 2, 12: 3, 13: 4, 14: 5, 15: 6, 16: 7, 17: 8, 18: 9}

text = FILE.read_text(encoding="utf-8")

WORD_PATTERN = r"(?P<prefix>(?:Таблиц[аеуы]|таблиц[аеуы]|табл\.))\s+(?P<num>\d+)"

def repl(m: re.Match[str]) -> str:
    n = int(m.group("num"))
    new = mapping.get(n, n)
    return f"{m.group('prefix')} {new}"

new_text = re.sub(WORD_PATTERN, repl, text)
FILE.write_text(new_text, encoding="utf-8")
print("Tables renumbered.")
