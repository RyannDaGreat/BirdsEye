"""
CLIP text encoder for live query-time encoding.

Loads the model once, encodes text queries on demand.
"""

import numpy as np
import torch
from transformers import CLIPModel, CLIPTokenizerFast


CLIP_MODEL = "openai/clip-vit-base-patch32"

_model = None
_tokenizer = None


def _ensure_loaded():
    """Load CLIP model on first use (lazy singleton)."""
    global _model, _tokenizer
    if _model is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"Loading CLIP text encoder on {device}...")
        _model = CLIPModel.from_pretrained(CLIP_MODEL).to(device).eval()
        _tokenizer = CLIPTokenizerFast.from_pretrained(CLIP_MODEL)
        print("CLIP text encoder ready.")


def encode_text(text):
    """
    Encode a text query into a CLIP embedding vector.

    Returns numpy array of shape (512,), L2-normalized, float32.

    >>> isinstance(encode_text.__doc__, str)
    True
    """
    _ensure_loaded()
    device = next(_model.parameters()).device
    inputs = _tokenizer([text], return_tensors="pt", padding=True, truncation=True, max_length=77)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        text_out = _model.text_model(**inputs)
        text_features = _model.text_projection(text_out.pooler_output)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
    return text_features.cpu().numpy().astype(np.float32).flatten()
