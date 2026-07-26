#!/usr/bin/env python3
"""Mux the recorded video with the narration, each MP3 placed at its scene start."""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()

times = json.loads((HERE / "scene_times.json").read_text())
trim = times["trim"]
total = times["end"] - trim

video = next((HERE / "video").glob("*.webm"))
out = HERE / "KAVACH_demo_cinematic.mp4"

inputs = ["-ss", f"{trim:.3f}", "-i", str(video)]
filters = []
labels = []
for i, scene in enumerate(times["scenes"]):
    mp3 = HERE / "audio" / f"{scene['id']}.mp3"
    inputs += ["-i", str(mp3)]
    delay_ms = max(0, int((scene["start"] - trim) * 1000))
    filters.append(f"[{i + 1}:a]adelay={delay_ms}:all=1[a{i}]")
    labels.append(f"[a{i}]")

filters.append(
    "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[voice]"
)
filter_complex = ";".join(filters)

cmd = [
    FF, "-y", *inputs,
    "-filter_complex", filter_complex,
    "-map", "0:v", "-map", "[voice]",
    "-t", f"{total:.3f}",
    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "160k",
    "-movflags", "+faststart",
    str(out),
]
print("running ffmpeg…")
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-3000:])
    raise SystemExit(1)
probe = subprocess.run([FF, "-i", str(out)], capture_output=True, text=True).stderr
for line in probe.splitlines():
    if "Duration" in line or "Video:" in line or "Audio:" in line:
        print(line.strip())
print("done:", out, f"({out.stat().st_size / 1e6:.1f} MB)")
