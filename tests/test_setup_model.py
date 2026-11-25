import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_model


class ModelSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(__file__).resolve().parent / "outputs" / f"model-test-{uuid4().hex[:8]}"
        self.directory.mkdir(parents=True)

    def test_download_restricts_files_and_detects_missing(self):
        with patch("setup_model.snapshot_download") as download:
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                setup_model.download_model(self.directory)
        self.assertEqual(download.call_args.kwargs["repo_id"], setup_model.MODEL_ID)
        self.assertEqual(download.call_args.kwargs["revision"], setup_model.REVISION)
        self.assertEqual(download.call_args.kwargs["allow_patterns"], list(setup_model.FILES))

    def test_download_verifies_checksum_and_rejects_corruption(self):
        sample = b"good"
        name = "unet/model.safetensors"
        path = self.directory / name
        path.parent.mkdir()
        path.write_bytes(sample)
        weights = {name: (len(sample), hashlib.sha256(sample).hexdigest())}
        with patch.object(setup_model, "FILES", (name,)), patch.object(setup_model, "WEIGHTS", weights), \
                patch("setup_model.snapshot_download"):
            setup_model.download_model(self.directory)
            path.write_bytes(b"evil")
            with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                setup_model.download_model(self.directory)

    def test_wrong_weight_size_is_missing(self):
        name = "weight.safetensors"
        (self.directory / name).write_bytes(b"short")
        with patch.object(setup_model, "FILES", (name,)), \
                patch.object(setup_model, "WEIGHTS", {name: (10, "unused")}):
            self.assertEqual(setup_model.missing_files(self.directory), [name])


if __name__ == "__main__":
    unittest.main()
