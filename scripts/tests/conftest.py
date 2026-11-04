"""The scripts import each other as top-level modules (``from _common import ...``), as ``uv run scripts/x.py`` does."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
