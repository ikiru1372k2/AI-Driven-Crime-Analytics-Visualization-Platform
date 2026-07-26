#!/usr/bin/env python3
"""Generate per-scene narration MP3s with edge-tts and measure their durations."""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()


def duration_of(path: Path) -> float:
    out = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        raise RuntimeError(f"could not probe {path}")
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


async def main() -> None:
    cfg = json.loads((HERE / "scenes.json").read_text())
    audio_dir = HERE / "audio"
    audio_dir.mkdir(exist_ok=True)
    durations = {}
    for scene in cfg["scenes"]:
        out = audio_dir / f"{scene['id']}.mp3"
        tts = edge_tts.Communicate(scene["text"], voice=cfg["voice"], rate=cfg["rate"])
        await tts.save(str(out))
        durations[scene["id"]] = round(duration_of(out), 2)
        print(f"{scene['id']}: {durations[scene['id']]:6.2f}s  (min visual {scene['min_secs']}s)")
    (HERE / "durations.json").write_text(json.dumps(durations, indent=2))
    total = sum(max(durations[s["id"]] + 0.5, s["min_secs"]) for s in cfg["scenes"])
    print(f"\nprojected video length: {total:.1f}s")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
