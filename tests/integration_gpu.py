"""Optional real-GPU test; keeps its input image and video in tests/outputs."""
import sys
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import VideoGeneratorV2

output = Path(__file__).resolve().parent / "outputs"
output.mkdir(exist_ok=True)
image_path = output / f"gpu-input-{uuid4().hex[:8]}.png"
image = Image.new("RGB", (1024, 576), "#355b89")
ImageDraw.Draw(image).ellipse((300, 100, 700, 500), fill="#e1ba67")
image.save(image_path)

root = tk.Tk()
root.withdraw()
app = VideoGeneratorV2(root)
app.image.set(str(image_path))
app.output.set(str(output))
app.frames.set("2")
app.steps.set("1")
errors = []
with patch("app.messagebox.showerror", side_effect=lambda *a, **k: errors.append(a)):
    app.start()
    deadline = time.monotonic() + 600
    observed_live = False
    while app.running and time.monotonic() < deadline:
        root.update()
        observed_live |= "Loading model" in app.log.get("1.0", "end")
        time.sleep(0.05)
    root.update()
    if app.running:
        raise RuntimeError("Generation timed out.")
    if errors:
        raise RuntimeError(f"Generation or playback failed: {errors}")
    assert observed_live, "No live loading status"
    assert "Generating: step 1 of 1" in app.log.get("1.0", "end")
    assert app.playing and app.current_frame is not None
    assert Path(app.video_path).is_file()
    print(f"PASS: {app.video_path}")
    app.close()
