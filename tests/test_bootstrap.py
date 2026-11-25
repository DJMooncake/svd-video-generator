import hashlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap


class Response(io.BytesIO):
    def __init__(self, data, status, content_range=""):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Range": content_range}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(__file__).resolve().parent / "outputs" / f"wheel-test-{uuid4().hex}.bin"
        self.path.parent.mkdir(exist_ok=True)

    def test_resume_and_verify(self):
        self.path.write_bytes(b"abc")
        with patch("bootstrap.urllib.request.urlopen", return_value=Response(b"def", 206, "bytes 3-5/6")) as open_url:
            bootstrap.download(self.path, url="https://example.com/wheel", size=6,
                               sha256=hashlib.sha256(b"abcdef").hexdigest())
        self.assertEqual(open_url.call_args.args[0].get_header("Range"), "bytes=3-")
        self.assertEqual(self.path.read_bytes(), b"abcdef")

    def test_refuses_server_that_ignores_range(self):
        self.path.write_bytes(b"abc")
        with patch("bootstrap.urllib.request.urlopen", return_value=Response(b"abcdef", 200)):
            with self.assertRaisesRegex(RuntimeError, "resume request"):
                bootstrap.download(self.path, url="https://example.com/wheel", size=6, sha256="unused")
        self.assertEqual(self.path.read_bytes(), b"abc")

    def test_rejects_bad_checksum(self):
        self.path.write_bytes(b"abcdef")
        with self.assertRaisesRegex(RuntimeError, "verification"):
            bootstrap.download(self.path, size=6, sha256="wrong")


if __name__ == "__main__":
    unittest.main()
