import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import generate


class GenerationValidationTests(unittest.TestCase):
    @patch("torch.cuda.is_available", return_value=True)
    def test_invalid_settings_are_rejected(self, _cuda):
        for settings in ((1, 25, 6, 42), (25, 0, 6, 42), (25, 25, 31, 42), (25, 25, 6, -1)):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                generate("unused.png", "unused", *settings)

    @patch("torch.cuda.is_available", return_value=True)
    def test_missing_image_is_reported(self, _cuda):
        with self.assertRaises(FileNotFoundError):
            generate("this-image-does-not-exist.png", "unused")

    @patch("torch.cuda.is_available", return_value=False)
    def test_missing_gpu_is_reported(self, _cuda):
        with self.assertRaisesRegex(RuntimeError, "NVIDIA GPU"):
            generate("unused.png", "unused")


if __name__ == "__main__":
    unittest.main()
