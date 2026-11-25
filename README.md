# SVD Video Generator

A Windows image-to-video desktop app with a video player, live log and dark mode.
Powered by Stability AI. Version 3 is a distributable version of the original
app; it uses the same generation model and settings as version 2.

## Requirements

- Windows 10/11, 64-bit, Python 3.11 including Tkinter and the `py` launcher.
- An NVIDIA CUDA GPU: tested with an RTX 3060 12 GB. Other GPUs are untested.
  Generation can take a long time. Close GPU-heavy apps if memory is low.
- Internet for initial setup, a Hugging Face account, and at least 15 GB free
  disk space for dependencies, model files, and download cache.

## Setup

1. Download or clone this repository. Open its folder and run `start.bat`.
   It creates `.venv` and downloads PyTorch and the Python dependencies. The
   first launch may take some time. The large PyTorch download resumes if
   interrupted and is verified against the official SHA-256. If installation
   fails, read the console error and run `start.bat` again.
2. Visit the [SVD 1.1 model page](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1),
   review its terms and request access while signed in. Approval is controlled
   by the model provider; the app does not accept the license for you.
3. In a terminal opened in the repository folder, run:

   ```powershell
   .\.venv\Scripts\hf.exe auth login
   ```

   Authenticate with your own Hugging Face token that has access to the model.
   Never paste the token into an issue, log or source file.
4. In the app, click **Download model...**. The first download is about 4.5 GB.
   It uses the official, gated model repository, can resume incomplete downloads,
   and checks the SHA-256 of the three weight files. Setup errors appear in the
   live log. If access is denied, check that the license was accepted and the
   CLI login uses the same account.
5. Select an image and click **Generate video**. Finished MP4s play in the app
   and are saved in `outputs` by default. `Open video...` plays an existing MP4.

After setup, generation runs locally without an internet connection. Images are
center-cropped to 1024 x 576. SVD may produce camera motion rather than the
subject motion you want; motion quality is not guaranteed. A full 25-frame,
25-step video can take a long time. Test settings with fewer steps are faster
but may produce low-quality video.

## License and model terms

Application source code is [MIT licensed](LICENSE). The model is **not** MIT
licensed: it is subject to the [Stability AI Community License](https://stability.ai/license)
and [model page terms](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt-1-1).
Model access and permitted use can be restricted, including commercial use.
Review the terms yourself. This repository does not contain model weights.

## Tests

After setup, run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Tests create small videos under `tests\outputs`; these are not deleted by tests.
With the model installed and GPU available, an optional real-generation smoke
test is `.venv\Scripts\python.exe tests\integration_gpu.py`. It creates a
two-frame, one-step video to verify the pipeline, not generation quality.
