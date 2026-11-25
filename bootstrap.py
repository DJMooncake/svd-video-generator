"""Download the pinned PyTorch wheel with resume and integrity verification."""
import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WHEEL = "torch-2.1.2+cu121-cp311-cp311-win_amd64.whl"
URL = "https://download-r2.pytorch.org/whl/cu121/torch-2.1.2%2Bcu121-cp311-cp311-win_amd64.whl"
SIZE = 2473957547
SHA256 = "c92e9c559a82466fc5989f648807d2c0215bcce09b97ad7a20d038b686783229"


def download(path, url=URL, size=SIZE, sha256=SHA256, attempts=8):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(attempts):
        offset = path.stat().st_size if path.exists() else 0
        if offset > size:
            raise RuntimeError(f"Download is larger than expected: {path}. Remove it and retry.")
        if offset == size:
            break
        request = urllib.request.Request(url)
        if offset:
            request.add_header("Range", f"bytes={offset}-")
        print(f"Downloading PyTorch: {offset / 1e6:.0f} / {size / 1e6:.0f} MB", flush=True)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if offset and (
                    response.status != 206
                    or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")
                ):
                    raise RuntimeError("The server did not honor the resume request; partial file was preserved.")
                with path.open("ab") as output:
                    downloaded = offset
                    next_report = offset + 32 * 1024 * 1024
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        if downloaded >= next_report:
                            print(f"Downloaded {downloaded / 1e6:.0f} / {size / 1e6:.0f} MB", flush=True)
                            next_report = downloaded + 32 * 1024 * 1024
            if path.stat().st_size != size:
                raise OSError("Download ended before the expected size.")
            break
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == attempts - 1:
                raise
            print(f"Download failed ({error}); resuming shortly...", flush=True)
        except (OSError, urllib.error.URLError) as error:
            if attempt == attempts - 1:
                raise
            print(f"Download interrupted ({error}); resuming shortly...", flush=True)
        time.sleep(5)
    print("Verifying PyTorch wheel SHA-256...", flush=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if path.stat().st_size != size or digest.hexdigest() != sha256:
        raise RuntimeError(f"PyTorch wheel failed verification: {path}. Remove it and retry.")
    print("PyTorch wheel verified.", flush=True)


if __name__ == "__main__":
    download(ROOT / ".downloads" / WHEEL)
