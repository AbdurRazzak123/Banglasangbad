INAL GitHub upload package

Repository structure:
.github/workflows/regenerate-news-details.yml  -> NEW workflow; keep existing update-news-sitemap.yml
Tools/generate_static_news.py                  -> replace/add this generator in Tools/
home.html                                      -> updated Home template

IMPORTANT:
- Do NOT delete .github/workflows/update-news-sitemap.yml
- Do NOT delete existing Asset, News, or Tools contents.
- Copy the files/folders in this package into the repository root, preserving paths.
- Details pages use four ad slots: Top, Middle top, Middle bottom, Bottom.
- Home page keeps its existing three ad slots.
- Middle top is placed directly below the Details headline.

