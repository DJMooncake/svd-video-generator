import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

ROOT = Path(__file__).resolve().parent
COMPONENTS = Path(os.environ.get("SVD_MODEL_DIR", ROOT / "model"))
UNET = COMPONENTS / "unet"
OUTPUT = ROOT / "outputs"

if sys.stdout is None or sys.stderr is None:
    log = (ROOT / "app.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def generate(image_path, output_dir, frames=25, steps=25, fps=6, seed=42, progress=None):
    import imageio.v2 as imageio
    import numpy as np
    import torch
    from diffusers import StableVideoDiffusionPipeline, UNetSpatioTemporalConditionModel
    from PIL import Image, ImageOps

    if not torch.cuda.is_available():
        raise RuntimeError("An NVIDIA GPU with CUDA is required for this setup.")
    if not 2 <= frames <= 25 or not 1 <= steps <= 100 or not 1 <= fps <= 30:
        raise ValueError("Frames must be 2â€“25, steps 1â€“100, and FPS 1â€“30.")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be between 0 and 4294967295.")
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    def report(message):
        if progress:
            progress(message)

    report("Loading model (this may take a few minutes)...")
    unet = UNetSpatioTemporalConditionModel.from_pretrained(
        str(UNET), torch_dtype=torch.float16, variant="fp16", local_files_only=True
    )
    pipe = StableVideoDiffusionPipeline.from_pretrained(
        str(COMPONENTS), unet=unet, torch_dtype=torch.float16,
        variant="fp16", local_files_only=True,
    )
    pipe.unet.enable_forward_chunking(chunk_size=1, dim=0)
    pipe.to("cuda")
    pipe.set_progress_bar_config(disable=True)

    with Image.open(image_path) as source:
        image = ImageOps.fit(
            ImageOps.exif_transpose(source).convert("RGB"),
            (1024, 576),
            method=Image.Resampling.LANCZOS,
        )

    def step_callback(_pipe, step, _timestep, tensors):
        report(f"Generating: step {step + 1} of {steps}...")
        return tensors

    with torch.inference_mode():
        result = pipe(
            image, num_frames=frames, num_inference_steps=steps, fps=fps,
            motion_bucket_id=127, noise_aug_strength=0.02, decode_chunk_size=1,
            generator=torch.Generator(device="cpu").manual_seed(seed),
            callback_on_step_end=step_callback,
        ).frames[0]
    report("Saving video...")
    filename = f"svd-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.mp4"
    destination = output_dir / filename
    imageio.mimsave(
        str(destination), [np.asarray(frame) for frame in result],
        fps=fps, codec="libx264", pixelformat="yuv420p",
    )
    return destination
