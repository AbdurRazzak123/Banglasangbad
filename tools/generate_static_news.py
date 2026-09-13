# Compatibility wrapper.
# The main generator is located at the repository root.

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "generate_static_news.py"

runpy.run_path(str(GENERATOR), run_name="__main__")
