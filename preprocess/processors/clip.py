"""
CLIP embedding processor. Uses all GPUs via self-calling subprocess for CUDA isolation.
Prefetches images via ThreadPoolExecutor so GPUs stay saturated.

ONLY processes the given batch entries. Does NOT rebuild FAISS.

Usage:
    uv run python preprocess/processors/clip.py main --entries_json=... --dataset_dir=datasets/pexels
    uv run python preprocess/processors/clip.py gpu_worker --list_path=/tmp/samples.json --gpu_id=0
"""

import os
import json

import numpy as np
import fire

from preprocess.processors.base import Processor, run_gpu_subprocess, distribute_across_gpus
from preprocess.video_utils import sample_dir


CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_DIM = 512       # CLIP embedding dimensionality (openai/clip-vit-base-patch32)
FORWARD_BATCH = 64   # images per GPU forward pass (not samples — each sample has 3 images)
PREFETCH_CHUNK = 32  # samples per prefetch chunk (progress updates every chunk)


# ========================================================================
# Math — private to clip
# ========================================================================

def mean_pairwise_cosine_distance(embeddings):
    """
    Mean pairwise cosine distance between L2-normalized embeddings. Pure function.

    (N, D) float32 -> scalar float

    >>> mean_pairwise_cosine_distance(np.eye(3, dtype=np.float32))
    1.0
    >>> mean_pairwise_cosine_distance(np.ones((3, 512), dtype=np.float32))
    0.0
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normed = embeddings / np.maximum(norms, 1e-8)
    sims = normed @ normed.T
    mask = ~np.eye(len(embeddings), dtype=bool)
    return round(float(1.0 - sims[mask].mean()), 6)


# ========================================================================
# GPU worker — runs in subprocess for CUDA isolation
# ========================================================================

def _load_image(path):
    """Load image from disk. Returns PIL Image or None on missing/corrupt file."""
    if not path or not os.path.exists(path):
        return None
    from PIL import Image
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        print(f"    WARN: Failed to load image {path}: {e}", flush=True)
        return None


def _batched_clip_forward(model, clip_processor, images, device, forward_batch):
    """
    Run CLIP vision encoder on a list of PIL images in batched forward passes.
    Pure function (given model state).

    Args:
        model: CLIPModel on device
        clip_processor: CLIPProcessor for image preprocessing
        images: list of PIL Images (no Nones — caller must filter)
        device: torch device string
        forward_batch: max images per forward pass

    Returns:
        (N, CLIP_DIM) float16 numpy array of L2-normalized embeddings

    >>> _batched_clip_forward(None, None, [], "cpu", 64).shape
    (0, 512)
    """
    if not images:
        return np.empty((0, CLIP_DIM), dtype=np.float16)

    import torch
    all_features = []

    for i in range(0, len(images), forward_batch):
        batch_imgs = images[i:i + forward_batch]
        inputs = clip_processor(images=batch_imgs, return_tensors="pt", padding=True)
        pixel_values = inputs["pixel_values"].to(device)

        with torch.no_grad():
            vision_out = model.vision_model(pixel_values=pixel_values)
            features = model.visual_projection(vision_out.pooler_output)
            features = features / features.norm(dim=-1, keepdim=True)

        all_features.append(features.cpu().numpy().astype(np.float16))

    return np.concatenate(all_features, axis=0)


def _gpu_worker_fn(args):
    """
    Process a slice of samples on one GPU. Called via torch.multiprocessing.Pool.

    Batches all valid images through CLIP in forward_batch-sized GPU passes
    (not one image at a time). Prefetches in small chunks for visible progress.
    """
    gpu_id, samples, model_name, forward_batch = args
    device = f"cuda:{gpu_id}"

    from preprocess.processors.base import make_gpu_logger
    log = make_gpu_logger(gpu_id)

    from transformers import CLIPModel, CLIPProcessor
    from concurrent.futures import ThreadPoolExecutor

    log(f"Loading CLIP model...")
    model = CLIPModel.from_pretrained(model_name).to(device).eval()
    clip_processor = CLIPProcessor.from_pretrained(model_name)
    log(f"Model loaded. Processing {len(samples)} samples...")

    prefetch = ThreadPoolExecutor(max_workers=8)
    frame_files = ["clip_first.npy", "clip_embedding.npy", "clip_last.npy"]
    thumb_files = ["thumb_first.jpg", "thumb_middle.jpg", "thumb_last.jpg"]
    done = 0

    for chunk_start in range(0, len(samples), PREFETCH_CHUNK):
        chunk = samples[chunk_start:chunk_start + PREFETCH_CHUNK]

        # Prefetch images for this chunk (3 per sample)
        all_paths = []
        for s in chunk:
            sd = s["sample_dir"]
            all_paths.extend(os.path.join(sd, t) for t in thumb_files)

        futures = [prefetch.submit(_load_image, p) for p in all_paths]
        all_images = [f.result() for f in futures]

        # Collect valid images for batched CLIP forward pass
        valid_images = []
        valid_indices = []  # (sample_idx_in_chunk, frame_idx)
        for j in range(len(chunk)):
            for frame_idx in range(3):
                img = all_images[j * 3 + frame_idx]
                if img is not None:
                    valid_images.append(img)
                    valid_indices.append((j, frame_idx))

        # Batched GPU inference (64 images per forward pass, not 1)
        if valid_images:
            all_embs = _batched_clip_forward(
                model, clip_processor, valid_images, device, forward_batch
            )
        else:
            all_embs = np.empty((0, CLIP_DIM), dtype=np.float16)

        # Map embeddings back to (sample, frame) pairs
        emb_map = {}
        for k, (si, fi) in enumerate(valid_indices):
            emb_map[(si, fi)] = all_embs[k]

        # Save per-sample artifacts (skip zero-vector fallbacks from failed images)
        for j, s in enumerate(chunk):
            sd = s["sample_dir"]
            valid_embeddings = []
            for frame_idx in range(3):
                if (j, frame_idx) in emb_map:
                    emb = emb_map[(j, frame_idx)]
                    np.save(os.path.join(sd, frame_files[frame_idx]), emb)
                    valid_embeddings.append(emb)

            if valid_embeddings:
                stacked = np.stack([e.astype(np.float32) for e in valid_embeddings])
                clip_std = mean_pairwise_cosine_distance(stacked)
                with open(os.path.join(sd, "clip_std.json"), "w") as f:
                    json.dump({"clip_std": clip_std}, f)

        done += len(chunk)
        log(f"{done}/{len(samples)} samples ({done * 100 // len(samples)}%)")


def gpu_worker(list_path, model=CLIP_MODEL, forward_batch=FORWARD_BATCH):
    """
    Subprocess entry point for CUDA-isolated GPU work.
    Distributes across all available GPUs via torch.multiprocessing.Pool.

    Args:
        list_path: JSON file with [{video_name, sample_dir}, ...]
        model: HuggingFace CLIP model name
        forward_batch: max images per GPU forward pass
    """
    with open(list_path) as f:
        samples = json.load(f)

    distribute_across_gpus(
        label="CLIP",
        samples=samples,
        worker_fn=_gpu_worker_fn,
        make_chunk_args=lambda gpu_id, chunk: (gpu_id, chunk, model, forward_batch),
    )


# ========================================================================
# Processor class
# ========================================================================

class ClipProcessor(Processor):
    name = "clip"
    human_name = "CLIP Embeddings"
    depends_on = ["ingest"]

    artifacts = [
        {"filename": "clip_embedding.npy", "label": "CLIP Embedding (middle)", "description": "512-dim float16 L2-normalized embedding of thumb_middle.jpg. Model: openai/clip-vit-base-patch32.", "type": "data"},
        {"filename": "clip_first.npy", "label": "CLIP Embedding (first)", "description": "512-dim float16 embedding of thumb_first.jpg.", "type": "data"},
        {"filename": "clip_last.npy", "label": "CLIP Embedding (last)", "description": "512-dim float16 embedding of thumb_last.jpg.", "type": "data"},
        {"filename": "clip_std.json", "label": "CLIP Diversity", "description": "JSON: {clip_std: float}. Mean pairwise cosine distance of 3 frame embeddings.", "type": "data"},
    ]

    fields = {
        "clip_std": {"label": "CLIP Diversity", "description": "Mean pairwise cosine distance between CLIP (openai/clip-vit-base-patch32, 512-dim) embeddings of thumb_first/middle/last.jpg.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "clip_std.json", "target": "video_stats.json"},
        {"type": "vector_index", "source": "clip_embedding.npy", "prefix": "clip", "dim": CLIP_DIM},
    ]

    def process(self, entries, dataset_dir, workers=32):
        """Run CLIP as subprocess for CUDA isolation. Self-calls gpu_worker via Fire."""
        run_gpu_subprocess(entries, dataset_dir, __file__, self.human_name)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": ClipProcessor.cli_main, "gpu_worker": gpu_worker})
