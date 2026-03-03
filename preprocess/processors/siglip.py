"""
SigLIP embedding processor. Uses all GPUs via self-calling subprocess for CUDA isolation.
Prefetches images via ThreadPoolExecutor so GPUs stay saturated.

SigLIP (Sigmoid Loss for Language-Image Pre-training) is a contrastive vision-language
model from Google, successor to CLIP. Uses SoViT-400m architecture with 1152-dim
embeddings. Higher quality than CLIP ViT-B/32 (512-dim) — trained on WebLI dataset
with sigmoid contrastive loss.

ONLY processes the given batch entries. Does NOT rebuild FAISS.

Usage:
    uv run python preprocess/processors/siglip.py main --entries_json=... --dataset_dir=datasets/pexels
    uv run python preprocess/processors/siglip.py gpu_worker --list_path=/tmp/samples.json
"""

import os
import json

import numpy as np
import fire

from preprocess.processors.base import Processor, run_gpu_subprocess, distribute_across_gpus, mean_pairwise_cosine_distance
from preprocess.video_utils import save_json_atomic, save_npy_atomic


SIGLIP_MODEL = "google/siglip-so400m-patch14-384"
SIGLIP_DIM = 1152     # SigLIP SO400M embedding dimensionality
FORWARD_BATCH = 32    # images per GPU forward pass (larger model than CLIP, smaller batch)
PREFETCH_CHUNK = 32   # samples per prefetch chunk (progress updates every chunk)


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


def _batched_siglip_forward(model, image_processor, images, device, forward_batch):
    """
    Run SigLIP vision encoder on a list of PIL images in batched forward passes.
    Pure function (given model state).

    Args:
        model: SiglipModel on device
        image_processor: SiglipImageProcessor for image preprocessing
        images: list of PIL Images (no Nones — caller must filter)
        device: torch device string
        forward_batch: max images per forward pass

    Returns:
        (N, SIGLIP_DIM) float16 numpy array of L2-normalized embeddings

    >>> _batched_siglip_forward(None, None, [], "cpu", 32).shape
    (0, 1152)
    """
    if not images:
        return np.empty((0, SIGLIP_DIM), dtype=np.float16)

    import torch
    all_features = []

    for i in range(0, len(images), forward_batch):
        batch_imgs = images[i:i + forward_batch]
        inputs = image_processor(images=batch_imgs, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(device)

        with torch.no_grad():
            vision_out = model.vision_model(pixel_values=pixel_values)
            features = vision_out.pooler_output  # (B, 1152)
            features = features / features.norm(dim=-1, keepdim=True)

        all_features.append(features.cpu().numpy().astype(np.float16))

    return np.concatenate(all_features, axis=0)


def _gpu_worker_fn(args):
    """
    Process a slice of samples on one GPU. Called via torch.multiprocessing.Pool.

    Batches all valid images through SigLIP in forward_batch-sized GPU passes
    (not one image at a time). Prefetches in small chunks for visible progress.
    """
    gpu_id, samples, model_name, forward_batch = args
    device = f"cuda:{gpu_id}"

    from preprocess.processors.base import make_gpu_logger
    log = make_gpu_logger(gpu_id)

    from transformers import SiglipModel, SiglipImageProcessor
    from concurrent.futures import ThreadPoolExecutor

    log(f"Loading SigLIP model...")
    model = SiglipModel.from_pretrained(model_name).to(device).eval()
    image_processor = SiglipImageProcessor.from_pretrained(model_name)
    log(f"Model loaded. Processing {len(samples)} samples...")

    prefetch = ThreadPoolExecutor(max_workers=8)
    frame_files = ["siglip_first.npy", "siglip_embedding.npy", "siglip_last.npy"]
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

        # Collect valid images for batched SigLIP forward pass
        valid_images = []
        valid_indices = []  # (sample_idx_in_chunk, frame_idx)
        for j in range(len(chunk)):
            for frame_idx in range(3):
                img = all_images[j * 3 + frame_idx]
                if img is not None:
                    valid_images.append(img)
                    valid_indices.append((j, frame_idx))

        # Batched GPU inference
        if valid_images:
            all_embs = _batched_siglip_forward(
                model, image_processor, valid_images, device, forward_batch
            )
        else:
            all_embs = np.empty((0, SIGLIP_DIM), dtype=np.float16)

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
                    save_npy_atomic(emb, os.path.join(sd, frame_files[frame_idx]))
                    valid_embeddings.append(emb)

            if valid_embeddings:
                stacked = np.stack([e.astype(np.float32) for e in valid_embeddings])
                siglip_std = mean_pairwise_cosine_distance(stacked)
                save_json_atomic({"siglip_std": siglip_std}, os.path.join(sd, "siglip_std.json"))

        done += len(chunk)
        log(f"{done}/{len(samples)} samples ({done * 100 // len(samples)}%)")


def gpu_worker(list_path, model=SIGLIP_MODEL, forward_batch=FORWARD_BATCH):
    """
    Subprocess entry point for CUDA-isolated GPU work.
    Distributes across all available GPUs via torch.multiprocessing.Pool.

    Args:
        list_path: JSON file with [{video_name, sample_dir}, ...]
        model: HuggingFace SigLIP model name
        forward_batch: max images per GPU forward pass
    """
    with open(list_path) as f:
        samples = json.load(f)

    distribute_across_gpus(
        label="SigLIP",
        samples=samples,
        worker_fn=_gpu_worker_fn,
        make_chunk_args=lambda gpu_id, chunk: (gpu_id, chunk, model, forward_batch),
    )


# ========================================================================
# Text encoder — lazy-loaded singleton for query-time encoding
# ========================================================================

_text_model = None
_text_tokenizer = None


def _ensure_text_encoder():
    """Load SigLIP text encoder on first use (lazy singleton)."""
    global _text_model, _text_tokenizer
    if _text_model is None:
        from transformers import SiglipModel, SiglipTokenizer
        from rp import select_torch_device
        from server.status import set_status
        device = select_torch_device(reserve=True)
        msg = f"Loading SigLIP text encoder on {device}..."
        set_status(msg)
        print(msg)
        _text_model = SiglipModel.from_pretrained(SIGLIP_MODEL).to(device).eval()
        _text_tokenizer = SiglipTokenizer.from_pretrained(SIGLIP_MODEL)
        set_status("SigLIP text encoder ready.")
        print("SigLIP text encoder ready.")


# ========================================================================
# Processor class
# ========================================================================

class SiglipProcessor(Processor):
    name = "siglip"
    human_name = "SigLIP Embeddings"
    depends_on = ["ingest"]

    embedding_space = {
        "prefix": "siglip",
        "dim": SIGLIP_DIM,
        "model": SIGLIP_MODEL,
        "description": "SigLIP SO400M/14 cosine similarity",
        "score_field": {
            "key": "siglip_score",
            "label": "SigLIP Score",
            "description": "Cosine similarity between the text embedding of the search query and the SigLIP image embedding of the video's middle frame. SigLIP (google/siglip-so400m-patch14-384, 1152-dim) is a higher-quality successor to CLIP. Higher = more visually similar to query text.",
            "dtype": "float",
            "dynamic": True,
            "range": [0, 1],
        },
    }

    @staticmethod
    def encode_text(query):
        """
        Encode a text query into SigLIP embedding space. Lazy-loads model on first call.

        Returns (1152,) float32 ndarray, L2-normalized.

        str -> (1152,) float32

        >>> isinstance(SiglipProcessor.encode_text("sunset over ocean"), np.ndarray)  # doctest: +SKIP
        True
        """
        import torch
        _ensure_text_encoder()
        device = next(_text_model.parameters()).device
        inputs = _text_tokenizer(
            [query], return_tensors="pt", padding="max_length", truncation=True, max_length=64
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            text_out = _text_model.text_model(**inputs)
            text_features = text_out.pooler_output  # (1, 1152)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features.cpu().numpy().astype(np.float32).flatten()

    artifacts = [
        {"filename": "siglip_embedding.npy", "label": "SigLIP Embedding (middle)", "description": "1152-dim float16 L2-normalized embedding of thumb_middle.jpg. Model: google/siglip-so400m-patch14-384.", "type": "data"},
        {"filename": "siglip_first.npy", "label": "SigLIP Embedding (first)", "description": "1152-dim float16 embedding of thumb_first.jpg.", "type": "data"},
        {"filename": "siglip_last.npy", "label": "SigLIP Embedding (last)", "description": "1152-dim float16 embedding of thumb_last.jpg.", "type": "data"},
        {"filename": "siglip_std.json", "label": "SigLIP Diversity", "description": "JSON: {siglip_std: float}. Mean pairwise cosine distance of 3 frame embeddings.", "type": "data"},
    ]

    fields = {
        "siglip_std": {"label": "SigLIP Diversity", "description": "Mean pairwise cosine distance between SigLIP (google/siglip-so400m-patch14-384, 1152-dim) embeddings of thumb_first/middle/last.jpg.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "siglip_std.json", "target": "video_stats.json"},
        {"type": "vector_index", "source": "siglip_embedding.npy", "prefix": "siglip", "dim": SIGLIP_DIM},
    ]

    def process(self, entries, dataset_dir, workers=32):
        """Run SigLIP as subprocess for CUDA isolation. Self-calls gpu_worker via Fire."""
        run_gpu_subprocess(entries, dataset_dir, __file__, self.human_name)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": SiglipProcessor.cli_main, "gpu_worker": gpu_worker})
