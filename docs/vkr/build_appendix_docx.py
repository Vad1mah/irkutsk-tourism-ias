"""Build Приложение_А_ТЭО.docx from Приложение_А_ТЭО.md using the same
academic styles as the main report (TNR 14pt, justify, line-spacing 1.5,
indent 1.27 cm, margins 3/1/2/2 cm).

Reuses build_docx.build() with overridden source/output paths.
"""
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_docx as bd

bd.MD_SOURCE = SCRIPT_DIR / "Приложение_А_ТЭО.md"
bd.DOCX_OUTPUT = SCRIPT_DIR / "Приложение_А_ТЭО.docx"

if __name__ == "__main__":
    bd.build()
