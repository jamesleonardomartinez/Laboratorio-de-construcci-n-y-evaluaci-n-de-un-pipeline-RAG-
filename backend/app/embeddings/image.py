"""siglip2-base-patch16 image embedding wrapper (3.2). Apache-2.0, 768-dim output."""

from functools import lru_cache

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from app.config import settings

IMAGE_EMBEDDING_DIM = 768


@lru_cache(maxsize=1)
def _get_model_and_processor():
    processor = AutoProcessor.from_pretrained(settings.image_embedding_model)
    model = AutoModel.from_pretrained(settings.image_embedding_model)
    model.eval()
    return model, processor


def embed_image(image_path: str) -> list[float]:
    return embed_images([image_path])[0]


def embed_images(image_paths: list[str]) -> list[list[float]]:
    if not image_paths:
        return []
    model, processor = _get_model_and_processor()
    images = [Image.open(p).convert("RGB") for p in image_paths]
    inputs = processor(images=images, return_tensors="pt")
    with torch.no_grad():
        features = model.get_image_features(**inputs)
        features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features.tolist()


def embed_text_siglip(text: str) -> list[float]:
    """Embeds a query string with SigLIP's own text tower (not bge-m3), so it
    lands in the same 768-dim space as image_chunks embeddings and can be
    used to search them. bge-m3 and SigLIP vectors are not interchangeable."""
    return embed_texts_siglip([text])[0]


def embed_texts_siglip(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model, processor = _get_model_and_processor()
    inputs = processor(text=texts, padding=True, return_tensors="pt")
    with torch.no_grad():
        features = model.get_text_features(**inputs)
        features = features / features.norm(p=2, dim=-1, keepdim=True)
    return features.tolist()
