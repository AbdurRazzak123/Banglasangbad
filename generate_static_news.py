# Compatibility launcher: GitHub Actions uses tools/generate_static_news.py
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent / 'tools' / 'generate_static_news.py'), run_name='__main__')
