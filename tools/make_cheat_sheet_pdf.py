"""
Render tools/cheat_sheet.html to Strokes Edge Website HTML/downloads/strokes-gained-cheat-sheet.pdf
with headless Chrome (needs Chrome and internet for the Google Fonts). Safe to re-run.
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(os.path.dirname(HERE), "Strokes Edge Website HTML")
CHROME = os.environ.get("CHROME_PATH", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SRC = os.path.join(HERE, "cheat_sheet.html")
OUT_DIR = os.path.join(SITE, "downloads")
OUT = os.path.join(OUT_DIR, "strokes-gained-cheat-sheet.pdf")

os.makedirs(OUT_DIR, exist_ok=True)
subprocess.run([CHROME, "--headless=new", "--no-pdf-header-footer", "--virtual-time-budget=8000",
                "--print-to-pdf=" + OUT, "file:///" + SRC.replace("\\", "/")],
               check=True, capture_output=True, timeout=120)
print("wrote", OUT, os.path.getsize(OUT), "bytes")
