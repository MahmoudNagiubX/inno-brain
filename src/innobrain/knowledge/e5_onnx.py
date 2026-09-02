import asyncio
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from innobrain.providers.contracts import EmbeddingProvider

from .embedding_assets import E5Assets, resolve_e5_assets


def mean_pool(last_hidden: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask[..., None].astype(np.float32)
    summed = (last_hidden * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    return summed / counts


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


class MultilingualE5OnnxProvider(EmbeddingProvider):
    """CPU-only E5 provider; the ONNX model is a replaceable local asset."""

    def __init__(
        self,
        assets: E5Assets | None = None,
        *,
        model_path: Path | None = None,
        tokenizer_path: Path | None = None,
        session: object | None = None,
        tokenizer: Tokenizer | None = None,
        dimension: int = 384,
        max_tokens: int = 512,
        download_assets: bool = False,
    ) -> None:
        if assets is None and (model_path is None or tokenizer_path is None):
            assets = resolve_e5_assets(download=download_assets)
        if assets is not None:
            model_path = assets.model_path
            tokenizer_path = assets.tokenizer_path
        if model_path is None or tokenizer_path is None:
            raise ValueError("model_path and tokenizer_path are required")

        self.dimension = dimension
        self.max_tokens = max_tokens
        self.tokenizer = tokenizer or Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.enable_truncation(max_length=max_tokens)
        pad_id = self.tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise RuntimeError("E5 tokenizer has no <pad> token")
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")
        self.session = session or ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

    async def embed(self, text: str) -> Sequence[float]:
        return await self.embed_query(text)

    async def embed_query(self, text: str) -> Sequence[float]:
        return await asyncio.to_thread(self._embed_one, f"query: {text}")

    async def embed_passage(self, text: str) -> Sequence[float]:
        return await asyncio.to_thread(self._embed_one, f"passage: {text}")

    def _embed_one(self, text: str) -> list[float]:
        encoding = self.tokenizer.encode(text)
        input_ids = np.asarray([encoding.ids], dtype=np.int64)
        attention_mask = np.asarray([encoding.attention_mask], dtype=np.int64)
        input_names = {item.name for item in self.session.get_inputs()}
        model_inputs: dict[str, np.ndarray] = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if "token_type_ids" in input_names:
            model_inputs["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)

        outputs = self.session.run(None, model_inputs)
        last_hidden = next(
            (output for output in outputs if np.asarray(output).ndim == 3),
            outputs[0],
        )
        pooled = _l2_normalize(mean_pool(np.asarray(last_hidden), attention_mask))[0]
        if pooled.shape != (self.dimension,):
            raise RuntimeError(
                f"E5 embedding dimension {pooled.shape[0]} does not match {self.dimension}"
            )
        if not np.isfinite(pooled).all():
            raise RuntimeError("E5 embedding contains non-finite values")
        return pooled.astype(np.float32).tolist()
