"""
GVE (General Video Embeddings) processor. Uses all GPUs via subprocess for CUDA isolation.
Prefetches images via ThreadPoolExecutor so GPUs stay saturated.

GVE-3B (Alibaba-NLP/GVE-3B) is a multimodal embedding model built on Qwen2.5-VL-3B.
Produces 2048-dim L2-normalized embeddings via last-token pooling. Unlike CLIP/SigLIP
(dual-encoder), GVE uses a single unified model for both text and vision. Trained on
13M multimodal pairs with modality pyramid curriculum.

Uses GVE-3B (not 7B) because GVE-7B requires ~16GB VRAM per GPU and doesn't fit on
our 15GB GPUs. GVE-3B achieves 0.571 avg vs 0.600 for GVE-7B on UVRB benchmark.

Compatibility: GVE's custom HuggingFace code targets transformers 4.x. We load the
model as native Qwen2_5_VLForConditionalGeneration (supported in transformers 5.x) and
extract last-token hidden states ourselves, bypassing the custom code entirely.

ONLY processes the given batch entries. Does NOT rebuild FAISS.

Usage:
    uv run python preprocess/processors/gve.py main --entries_json=... --dataset_dir=datasets/pexels
    uv run python preprocess/processors/gve.py gpu_worker --list_path=/tmp/samples.json
"""

import os
import json

import numpy as np
import fire

from preprocess.processors.base import Processor, run_gpu_subprocess, distribute_across_gpus, mean_pairwise_cosine_distance
from preprocess.video_utils import save_json_atomic, save_npy_atomic


GVE_MODEL = "Alibaba-NLP/GVE-3B"
GVE_DIM = 2048        # Qwen2.5-VL-3B hidden_size
FORWARD_BATCH = 1     # images per GPU forward pass (3B model, tight on 15GB GPUs)
PREFETCH_CHUNK = 8    # samples per prefetch chunk (progress updates every chunk)
GVE_MAX_PIXELS = 384 * 384  # cap image resolution to limit vision tokens and VRAM


def _load_gve_model(device, model_path=GVE_MODEL):
    """
    Load GVE-3B as native Qwen2_5_VLForConditionalGeneration.

    GVE's custom Qwen25VLForEmbedding class is incompatible with transformers 5.x.
    Since the custom class only removes the LM head from the forward pass (we extract
    hidden states ourselves anyway), we load the base Qwen2.5-VL architecture directly.

    Args:
        device: torch device string (e.g. "cuda:0")
        model_path: HuggingFace model name or local path to cached model

    Returns (model, processor) tuple.
    """
    import torch
    from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    ).to(device).eval()

    processor = AutoProcessor.from_pretrained(
        model_path,
        use_fast=True,
    )
    processor.tokenizer.padding_side = "left"

    return model, processor


# ========================================================================
# GPU worker — runs in subprocess for CUDA isolation
# ========================================================================

def _load_image(path):
    """Load and resize image for GVE. Caps at GVE_MAX_PIXELS to limit VRAM.

    Returns PIL Image or None on missing/corrupt file.
    """
    if not path or not os.path.exists(path):
        return None
    from PIL import Image
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        if w * h > GVE_MAX_PIXELS:
            scale = (GVE_MAX_PIXELS / (w * h)) ** 0.5
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
    except Exception as e:
        print(f"    WARN: Failed to load image {path}: {e}", flush=True)
        return None


def _batched_gve_forward(model, processor, images, device, forward_batch):
    """
    Run GVE on a list of PIL images in batched forward passes.
    Pure function (given model state).

    Uses Qwen2.5-VL chat template to format image inputs, then extracts
    last-token hidden state as the embedding.

    Args:
        model: Qwen2_5_VLForConditionalGeneration on device
        processor: AutoProcessor for GVE
        images: list of PIL Images (no Nones — caller must filter)
        device: torch device string
        forward_batch: max images per forward pass

    Returns:
        (N, GVE_DIM) float16 numpy array of L2-normalized embeddings

    >>> _batched_gve_forward(None, None, [], "cpu", 4).shape
    (0, 2048)
    """
    if not images:
        return np.empty((0, GVE_DIM), dtype=np.float16)

    import torch
    import torch.nn.functional as F
    from qwen_vl_utils import process_vision_info
    all_features = []

    for i in range(0, len(images), forward_batch):
        batch_imgs = images[i:i + forward_batch]

        # Build chat messages for each image
        batch_messages = []
        for img in batch_imgs:
            batch_messages.append([
                {"role": "user", "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": "Describe this image."},
                ]}
            ])

        # Process all messages through the processor
        batch_texts = [
            processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            for msgs in batch_messages
        ]

        # Process vision info for each message set
        all_image_inputs = []
        for msgs in batch_messages:
            img_inputs, _ = process_vision_info(msgs)
            all_image_inputs.extend(img_inputs if img_inputs else [])

        inputs = processor(
            text=batch_texts, images=all_image_inputs,
            padding=True, truncation=True, max_length=1200,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs, output_hidden_states=True)
            # Last-token pooling from final hidden state
            features = outputs.hidden_states[-1][:, -1, :]  # (B, 2048)
            features = F.normalize(features, p=2, dim=1)

        all_features.append(features.cpu().float().numpy().astype(np.float16))
        del inputs, outputs, features
        torch.cuda.empty_cache()

    return np.concatenate(all_features, axis=0)


def _gpu_worker_fn(args):
    """
    Process a slice of samples on one GPU. Called via torch.multiprocessing.Pool.

    Batches all valid images through GVE in forward_batch-sized GPU passes.
    Prefetches in small chunks for visible progress.
    """
    gpu_id, samples, model_name, forward_batch = args
    device = f"cuda:{gpu_id}"

    from preprocess.processors.base import make_gpu_logger
    log = make_gpu_logger(gpu_id)

    log(f"Loading GVE model (3B params, may take a minute)...")
    model, processor = _load_gve_model(device, model_name)
    log(f"Model loaded. Processing {len(samples)} samples...")

    from concurrent.futures import ThreadPoolExecutor
    prefetch = ThreadPoolExecutor(max_workers=8)
    frame_files = ["gve_first.npy", "gve_embedding.npy", "gve_last.npy"]
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

        # Collect valid images for batched GVE forward pass
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
            all_embs = _batched_gve_forward(
                model, processor, valid_images, device, forward_batch
            )
        else:
            all_embs = np.empty((0, GVE_DIM), dtype=np.float16)

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
                gve_std = mean_pairwise_cosine_distance(stacked)
                save_json_atomic({"gve_std": gve_std}, os.path.join(sd, "gve_std.json"))

        done += len(chunk)
        log(f"{done}/{len(samples)} samples ({done * 100 // len(samples)}%)")


def gpu_worker(list_path, model=GVE_MODEL, forward_batch=FORWARD_BATCH):
    """
    Subprocess entry point for CUDA-isolated GPU work.
    Distributes across all available GPUs via torch.multiprocessing.Pool.

    Args:
        list_path: JSON file with [{video_name, sample_dir}, ...]
        model: HuggingFace GVE model name
        forward_batch: max images per GPU forward pass
    """
    with open(list_path) as f:
        samples = json.load(f)

    # Resolve to local cache path before spawning GPU workers. Without this,
    # 8 simultaneous from_pretrained() calls race on HuggingFace's cache lock
    # and some fail with "does not appear to have a file named model-*.safetensors".
    from huggingface_hub import snapshot_download
    print(f"  Pre-caching GVE model ({model})...", flush=True)
    local_model_path = snapshot_download(model)
    print(f"  Model cached at {local_model_path}. Distributing across GPUs...", flush=True)

    distribute_across_gpus(
        label="GVE",
        samples=samples,
        worker_fn=_gpu_worker_fn,
        make_chunk_args=lambda gpu_id, chunk: (gpu_id, chunk, local_model_path, forward_batch),
    )


# ========================================================================
# Text encoder — lazy-loaded singleton for query-time encoding
# ========================================================================

_text_model = None
_text_processor = None


def _ensure_text_encoder():
    """Load GVE model on first use (lazy singleton). Same model encodes text and vision."""
    global _text_model, _text_processor
    if _text_model is None:
        from rp import select_torch_device
        from server.status import set_status
        device = select_torch_device(reserve=True)
        msg = f"Loading GVE text encoder on {device} (3B params, may take a minute)..."
        set_status(msg)
        print(msg)
        _text_model, _text_processor = _load_gve_model(str(device))
        set_status("GVE text encoder ready.")
        print("GVE text encoder ready.")


# ========================================================================
# Processor class
# ========================================================================

class GveProcessor(Processor):
    name = "gve"
    human_name = "GVE Embeddings"
    depends_on = ["ingest"]

    embedding_space = {
        "prefix": "gve",
        "dim": GVE_DIM,
        "model": GVE_MODEL,
        "description": "GVE-3B cosine similarity (Qwen2.5-VL backbone)",
        "score_field": {
            "key": "gve_score",
            "label": "GVE Score",
            "description": "Cosine similarity between the text embedding of the search query and the GVE image embedding of the video's middle frame. GVE-3B (Alibaba-NLP/GVE-3B, 2048-dim) is a multimodal embedding model built on Qwen2.5-VL. Higher = more visually similar to query text.",
            "dtype": "float",
            "dynamic": True,
            "range": [0, 1],
        },
    }

    @staticmethod
    def encode_text(query):
        """
        Encode a text query into GVE embedding space. Lazy-loads model on first call.

        Returns (2048,) float32 ndarray, L2-normalized.

        str -> (2048,) float32

        >>> isinstance(GveProcessor.encode_text("sunset over ocean"), np.ndarray)  # doctest: +SKIP
        True
        """
        import torch
        import torch.nn.functional as F
        _ensure_text_encoder()
        device = next(_text_model.parameters()).device

        messages = [
            {"role": "user", "content": [{"type": "text", "text": query}]}
        ]
        texts = _text_processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _text_processor(
            text=[texts], return_tensors="pt", padding=True
        ).to(device)

        with torch.no_grad():
            outputs = _text_model(**inputs, output_hidden_states=True)
            text_features = outputs.hidden_states[-1][:, -1, :]  # (1, 2048)
            text_features = F.normalize(text_features, p=2, dim=1)

        return text_features.cpu().float().numpy().flatten()

    artifacts = [
        {"filename": "gve_embedding.npy", "label": "GVE Embedding (middle)", "description": "2048-dim float16 L2-normalized embedding of thumb_middle.jpg. Model: Alibaba-NLP/GVE-3B.", "type": "data"},
        {"filename": "gve_first.npy", "label": "GVE Embedding (first)", "description": "2048-dim float16 embedding of thumb_first.jpg.", "type": "data"},
        {"filename": "gve_last.npy", "label": "GVE Embedding (last)", "description": "2048-dim float16 embedding of thumb_last.jpg.", "type": "data"},
        {"filename": "gve_std.json", "label": "GVE Diversity", "description": "JSON: {gve_std: float}. Mean pairwise cosine distance of 3 frame embeddings.", "type": "data"},
    ]

    fields = {
        "gve_std": {"label": "GVE Diversity", "description": "Mean pairwise cosine distance between GVE (Alibaba-NLP/GVE-3B, 2048-dim) embeddings of thumb_first/middle/last.jpg.", "dtype": "float"},
    }

    aggregation = [
        {"type": "json_dict", "source": "gve_std.json", "target": "video_stats.json"},
        {"type": "vector_index", "source": "gve_embedding.npy", "prefix": "gve", "dim": GVE_DIM},
    ]

    def process(self, entries, dataset_dir, workers=32):
        """Run GVE as subprocess for CUDA isolation. Self-calls gpu_worker via Fire."""
        run_gpu_subprocess(entries, dataset_dir, __file__, self.human_name)


# ========================================================================
# Fire CLI
# ========================================================================

if __name__ == "__main__":
    fire.Fire({"main": GveProcessor.cli_main, "gpu_worker": gpu_worker})
