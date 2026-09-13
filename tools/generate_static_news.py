from pathlib import Path
import runpy
import os

ROOT = Path(__file__).resolve().parent.parent

os.chdir(ROOT)

runpy.run_path(
    str(ROOT / "generate_static_news.py"),
    run_name="__main__"
)
