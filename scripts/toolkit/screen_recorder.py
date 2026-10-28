import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def record_screen():
    root = Path(__file__).resolve().parent.parent.parent
    evidence_dir = root / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_mp4 = evidence_dir / f"ulm_evidence_{timestamp}.mp4"
    out_gif = evidence_dir / f"ulm_evidence_{timestamp}.gif"

    print("=" * 65)
    print(" 🔴 VESPERA ULM: LIVE DESKTOP RECORDING IN PROGRESS")
    print("=" * 65)
    print(f" Target Video: {out_mp4.name}")
    print()
    print(" >>> Switch to your browser, terminal, or app and do your demo! <<<")
    print(" >>> When finished, come back to this window and PRESS 'q' <<<")
    print("=" * 65)
    print()

    # Launch FFmpeg capturing full desktop at 30 fps via gdigrab
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-i", "desktop",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out_mp4)
    ]

    try:
        proc = subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[*] Recording interrupted by user.")

    if out_mp4.exists() and out_mp4.stat().st_size > 1000:
        print("\n" + "=" * 65)
        print(f" [✓] Video captured successfully! ({out_mp4.stat().st_size:,} bytes)")
        print(" [*] Generating high-definition looping GIF for Reddit & GitHub...")
        print("=" * 65)

        gif_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(out_mp4),
            "-vf", "fps=15,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(out_gif)
        ]

        subprocess.run(gif_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if out_gif.exists():
            print(f" [✓] Animated GIF created: {out_gif.name} ({out_gif.stat().st_size:,} bytes)")

        print("\n✨ ALL EVIDENCE READY! Opening folder in Windows Explorer...")
        if sys.platform == "win32":
            os.startfile(str(evidence_dir))
    else:
        print("\n[!] Recording ended or file was empty.")

if __name__ == "__main__":
    record_screen()
