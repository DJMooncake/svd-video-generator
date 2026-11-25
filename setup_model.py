from pathlib import Path
import hashlib

from huggingface_hub import snapshot_download

MODEL_ID = "stabilityai/stable-video-diffusion-img2vid-xt-1-1"
REVISION = "043843887ccd51926e3efed36270444a838e7861"
FILES = (
    "model_index.json",
    "feature_extractor/preprocessor_config.json",
    "image_encoder/config.json",
    "image_encoder/model.fp16.safetensors",
    "scheduler/scheduler_config.json",
    "unet/config.json",
    "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.fp16.safetensors",
)
WEIGHTS = {
    "image_encoder/model.fp16.safetensors": (
        1264217240, "ae616c24393dd1854372b0639e5541666f7521cbe219669255e865cb7f89466a"
    ),
    "unet/diffusion_pytorch_model.fp16.safetensors": (
        3049435836, "fcc7032525a903a6c284ccb3e8cb6f9d87597b71130d8b9820925085e2215d17"
    ),
    "vae/diffusion_pytorch_model.fp16.safetensors": (
        195531910, "af602cd0eb4ad6086ec94fbf1438dfb1be5ec9ac03fd0215640854e90d6463a3"
    ),
}


def missing_files(directory):
    directory = Path(directory)
    return [
        name for name in FILES
        if not (directory / name).is_file()
        or (name in WEIGHTS and (directory / name).stat().st_size != WEIGHTS[name][0])
    ]


def download_model(directory):
    directory = Path(directory)
    snapshot_download(
        repo_id=MODEL_ID, revision=REVISION, local_dir=directory,
        allow_patterns=list(FILES), max_workers=1,
    )
    missing = missing_files(directory)
    if missing:
        raise RuntimeError(f"Model download incomplete: {', '.join(missing)}")
    for name, (_, expected) in WEIGHTS.items():
        path = directory / name
        print(f"Verifying {name}...", flush=True)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise RuntimeError(
                f"Checksum mismatch: {path}. Remove that file and retry the download."
            )
