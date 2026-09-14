from pathlib import Path
import re

p = Path("generate_static_news.py")
s = p.read_text(encoding="utf-8")

# Google Sheet order:
# A ID, B Category, C Headline, D Details, E Image-1, F Date,
# G Video, H Image-2, I Image-3, J Keyword.
old = """        'image2': cell(row, 6),
        'image3': cell(row, 7),
        'video': cell(row, 8),"""
new = """        'video': cell(row, 6),
        'image2': cell(row, 7),
        'image3': cell(row, 8),"""
if old in s:
    s = s.replace(old, new)

# Keep existing design/template logic, but make the generated media folder
# deterministic and compatible with the requested ID-1/2/3 naming.
s = s.replace("MEDIA = ROOT / 'news-media'", "MEDIA = ROOT / 'assets' / 'news'")
s = s.replace("MEDIA.mkdir(exist_ok=True)", "MEDIA.mkdir(parents=True, exist_ok=True)")

# Existing generator's Drive downloader uses a hash filename. Replace only
# the filename expression so the same image becomes ID-1.ext, ID-2.ext, etc.
s = s.replace(
    "target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + '.jpg')",
    "target = MEDIA / (name_prefix + '.jpg')"
)
s = s.replace(
    "target = MEDIA / (name_prefix + '-' + hashlib.sha1(fid.encode()).hexdigest()[:16] + ext)",
    "target = MEDIA / (name_prefix + ext)"
)

# The generator's detail pages reference news-media/. Point them at assets/news/.
s = s.replace("'news-media/' + target.name", "'assets/news/' + target.name")

# Fix category links to canonical detail pages. The generator currently builds
# detail pages inside /news/, so root category pages need ../news/ only when
# the link originates from a detail page; root category pages use news/.
# Leave the generator's existing static-link logic intact.

p.write_text(s, encoding="utf-8")
print("Generator compatibility patch applied.")
