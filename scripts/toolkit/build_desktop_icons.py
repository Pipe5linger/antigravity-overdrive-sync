import os
import sys
import subprocess
import shutil
from pathlib import Path
from PIL import Image

def build_all_desktop_icons():
    root = Path(__file__).resolve().parent.parent.parent
    svg_dir = root / "frontend" / "icons"
    out_ico_dir = root / "desktop_icons"
    frontend_ico_dir = root / "frontend" / "icons" / "desktop_ico"

    out_ico_dir.mkdir(parents=True, exist_ok=True)
    frontend_ico_dir.mkdir(parents=True, exist_ok=True)

    chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome_path.exists():
        chrome_path = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

    if not chrome_path.exists():
        print(f"[ERROR] Neither Chrome nor Edge found.")
        sys.exit(1)

    svg_files = list(svg_dir.glob("*.svg"))
    print(f"[*] Found {len(svg_files)} SVG icons in {svg_dir}")

    tmp_dir = root / "scratch" / "icon_build_temp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]

    for svg_path in svg_files:
        stem = svg_path.stem
        print(f"[*] Processing {stem}...")

        svg_content = svg_path.read_text(encoding="utf-8")
        html_wrapper = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 512px;
    height: 512px;
    background: rgba(0, 0, 0, 0);
    overflow: hidden;
  }}
  svg {{
    width: 512px;
    height: 512px;
    display: block;
  }}
</style>
</head>
<body>
{svg_content}
</body>
</html>"""

        temp_html = tmp_dir / f"{stem}.html"
        temp_png = tmp_dir / f"{stem}.png"
        temp_html.write_text(html_wrapper, encoding="utf-8")

        # Headless screenshot via Chrome
        cmd = [
            str(chrome_path),
            "--headless=new",
            "--disable-gpu",
            "--default-background-color=00000000",
            f"--screenshot={str(temp_png)}",
            "--window-size=512,512",
            f"file:///{str(temp_html).replace(chr(92), '/')}"
        ]

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not temp_png.exists():
            print(f"[!] Warning: Failed to render {stem}.png, return code: {res.returncode}")
            continue

        # Open rendered PNG in PIL
        img = Image.open(temp_png)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Save high-res PNG into output dirs
        png_out_1 = out_ico_dir / f"{stem}_512x512.png"
        png_out_2 = frontend_ico_dir / f"{stem}_512x512.png"
        img.save(png_out_1, "PNG")
        shutil.copy2(png_out_1, png_out_2)

        # Save multi-layer Windows .ico
        ico_out_1 = out_ico_dir / f"{stem}.ico"
        ico_out_2 = frontend_ico_dir / f"{stem}.ico"
        img.save(ico_out_1, format="ICO", sizes=ico_sizes)
        shutil.copy2(ico_out_1, ico_out_2)

        print(f"[+] Successfully generated: {ico_out_1.name} (sizes: 16px -> 256px)")

    # Clean up temp
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\n[DONE] All icons compiled to .ico in:")
    print(f"       -> {out_ico_dir}")
    print(f"       -> {frontend_ico_dir}")

if __name__ == "__main__":
    build_all_desktop_icons()
