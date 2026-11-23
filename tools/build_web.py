"""Build the browser version with pygbag (Python + pygame-ce compiled to WebAssembly).

    python -m tools.build_web            build into build/web (a static site: index.html + the game)
    python -m tools.build_web --serve    build, then serve it at http://127.0.0.1:8000 to test
                                         (not localhost: pygbag treats localhost as its own dev server)

Only the game itself is packaged (main.py and game/): the tests, tools, docs and .venv stay
behind. build/web can be uploaded as-is to any static host (Cloudflare Pages, GitHub Pages), and
build/web.zip is the same site zipped for itch.io.

tools/web/brain-room.tmpl adapts pygbag's page template to show the game once it starts.
The page includes search and link-preview metadata. The favicon, wordmark and link-preview
image are drawn by tools/brand.py. The build also writes robots.txt and sitemap.xml.
"""

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://brain-room.com/"
STAGE = ROOT / "build" / "brain-room"            # pygbag names the package after this folder
OUT = ROOT / "build" / "web"
WEB = ROOT / "tools" / "web"


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    shutil.copy2(ROOT / "main.py", STAGE / "main.py")
    shutil.copytree(ROOT / "game", STAGE / "game", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def build():
    subprocess.run([sys.executable, "-m", "pygbag", "--build", "--archive", "--title", "BRAIN ROOM",
                    "--width", "1280", "--height", "720", "--ume_block", "0",       # no "click to start"
                    "--template", str(WEB / "brain-room.tmpl"),
                    "--icon", str(WEB / "favicon.png"), str(STAGE)], check=True, cwd=ROOT)
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(STAGE / "build" / "web", OUT)
    search_files()
    shutil.make_archive(str(ROOT / "build" / "web"), "zip", OUT)
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"built {OUT.relative_to(ROOT)} ({size / 1e6:.1f} MB) and build/web.zip")


def search_files():
    """What search engines and link previews read (robots.txt, a sitemap, the preview image), and the logo."""
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}sitemap.xml\n")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{SITE}</loc><lastmod>{datetime.date.today().isoformat()}</lastmod></url>\n"
        "</urlset>\n")
    for filename in ("og-image.png", "wordmark.png", "leaderboard.css", "leaderboard.js"):
        shutil.copy2(WEB / filename, OUT / filename)


if __name__ == "__main__":
    stage()
    build()
    if "--serve" in sys.argv:
        subprocess.run([sys.executable, "-m", "http.server", "8000", "--bind", "127.0.0.1", "--directory", str(OUT)], check=False)
