import datetime
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://brain-room.com/"
STAGE = ROOT / "build" / "brain-room"
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
                    "--width", "1280", "--height", "720", "--ume_block", "0",
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
