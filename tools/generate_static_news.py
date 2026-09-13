# Compatibility wrapper: the canonical generator now lives at repository root.
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1] / 'generate_static_news.py'), run_name='__main__')
