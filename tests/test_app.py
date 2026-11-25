import sys
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import imageio.v2 as imageio
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import VideoGeneratorV2


class VersionTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_dir = Path(__file__).resolve().parent / "outputs"
        cls.output_dir.mkdir(exist_ok=True)
        cls.video = cls.output_dir / f"v2-playback-test-{uuid4().hex[:8]}.mp4"
        imageio.mimsave(
            str(cls.video),
            [np.full((64, 64, 3), color, dtype=np.uint8) for color in (20, 200)],
            fps=10, codec="libx264", pixelformat="yuv420p"
        )

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = VideoGeneratorV2(self.root)
        self.root.update()

    def tearDown(self):
        self.app.close()

    def test_video_plays_loops_and_pauses(self):
        self.app.open_video(self.video)
        self.assertTrue(self.app.playing)
        first = np.asarray(self.app.current_frame).mean()
        self.root.after_cancel(self.app.after_id)
        self.app.show_next_frame()
        second = np.asarray(self.app.current_frame).mean()
        self.root.after_cancel(self.app.after_id)
        self.app.show_next_frame()
        looped = np.asarray(self.app.current_frame).mean()
        self.assertGreater(second - first, 100)
        self.assertAlmostEqual(first, looped, delta=3)
        self.app.toggle_play()
        self.assertFalse(self.app.playing)
        self.app.toggle_play()
        self.assertTrue(self.app.playing)

    def test_theme_and_live_generation_messages(self):
        self.app.dark.set(False)
        self.app.apply_theme()
        self.assertEqual(self.root.cget("bg"), "#eef0f3")
        self.app.dark.set(True)
        self.app.apply_theme()
        self.assertEqual(self.root.cget("bg"), "#1c1d20")

        self.app.image.set(str(self.video))
        self.app.output.set(str(self.output_dir))

        def fake_generate(*args, progress):
            print("Loading pipeline components...")
            progress("Generating: step 1 of 25...")
            return self.video

        with patch("app.missing_files", return_value=[]), patch("app.generate", side_effect=fake_generate):
            self.app.start()
            deadline = time.monotonic() + 10
            while self.app.running and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.02)
            self.root.update()
        self.assertFalse(self.app.running)
        log = self.app.log.get("1.0", "end")
        self.assertIn("Loading pipeline components", log)
        self.assertIn("Generating: step 1 of 25", log)
        self.assertIn("Saved:", log)
        self.assertTrue(self.app.playing)
        self.assertEqual(self.app.video_path, str(self.video))

    def test_playback_error_is_reported(self):
        with patch("app.messagebox.showerror") as error:
            self.app.open_video(self.output_dir / "missing-video.mp4")
        self.assertFalse(self.app.playing)
        self.assertIn("Could not open video", self.app.log.get("1.0", "end"))
        error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
