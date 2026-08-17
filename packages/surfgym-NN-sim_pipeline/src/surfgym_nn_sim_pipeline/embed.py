"""Embedding model registry and encoding.

Design intent: the rest of the pipeline (similarity.py, main.py) never imports
sentence-transformers or model2vec directly, and never branches on model name.
It only calls the `encode(texts) -> ndarray` closure returned by get_encoder().

Each model declares its own prefix/pooling here so a config mistake (e.g. Qwen3
needing a different pooling than bge) can't silently leak into the pipeline body.
Device is NOT part of the model definition -- it's an execution concern, passed
to get_encoder() at call time, so the same registry runs on a laptop CPU or an
A100 without editing this file.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

BACKEND_SENTENCE_TRANSFORMERS = "sentence-transformers"
BACKEND_MODEL2VEC = "model2vec"


class SanityCheckError(RuntimeError):
    """Raised when an encoder fails the identical/paraphrase/unrelated smoke test."""


@dataclass(frozen=True)
class EmbeddingModel:
    name: str
    repo_id: str
    revision: str
    backend: str
    pooling: str  # declared for the record (manifest, cache key); sentence-transformers
    # applies this from the model's own bundled config, we do not hand-roll it
    query_prefix: str = ""  # applied to both sides equally -- our comparisons are symmetric
    trust_remote_code: bool = False  # only set True for repos we've vetted (see MODELS below)


MODELS: dict[str, EmbeddingModel] = {
    "potion-base-32m": EmbeddingModel(
        name="potion-base-32m",
        repo_id="minishlab/potion-base-32M",
        revision="1e5a03f8eeb2c98b928fbbd846f22f816360919f",
        backend=BACKEND_MODEL2VEC,
        pooling="static-mean",
    ),
    "uae-large-v1": EmbeddingModel(
        name="uae-large-v1",
        repo_id="WhereIsAI/UAE-Large-V1",
        revision="9c9b2c999b3350cfb3171ed429320668e39b00b8",
        backend=BACKEND_SENTENCE_TRANSFORMERS,
        pooling="cls",
    ),
    "bge-large-en-v1.5": EmbeddingModel(
        name="bge-large-en-v1.5",
        repo_id="BAAI/bge-large-en-v1.5",
        revision="d4aa6901d3a41ba39fb536a557fa166f842b0e09",
        backend=BACKEND_SENTENCE_TRANSFORMERS,
        pooling="cls",
    ),
    "gte-large": EmbeddingModel(
        name="gte-large",
        repo_id="thenlper/gte-large",
        revision="4bef63f39fcc5e2d6b0aae83089f307af4970164",
        backend=BACKEND_SENTENCE_TRANSFORMERS,
        pooling="mean",
        # Superseded by Alibaba-NLP/gte-large-en-v1.5, which we tried first and
        # dropped: it loads via trust_remote_code from a SEPARATE, unpinned repo
        # (Alibaba-NLP/new-impl), whose current (and only recent) revision
        # crashes under transformers>=5 with a garbage position-id index. Pinning
        # our own repo's revision does nothing about that other repo's code, so
        # "revision pinned" was a false promise for that model. This predecessor
        # is a standard BERT checkpoint -- no remote code, no version coupling --
        # and still gives us the "different backbone" cross-check §2.1 wants.
    ),
    "qwen3-embedding-8b": EmbeddingModel(
        name="qwen3-embedding-8b",
        repo_id="Qwen/Qwen3-Embedding-8B",
        revision="1d8ad4ca9b3dd8059ad90a75d4983776a23d44af",
        backend=BACKEND_SENTENCE_TRANSFORMERS,
        pooling="last-token",
    ),
}

# Default routing set for a full ablation run. potion is dev-loop only (see
# 파이프라인 설계.md §2.2) and qwen3-8b is an occasional A100 confirmation run,
# so main.py's default excludes both; pass --model to opt in explicitly.
DEFAULT_MODELS = ("uae-large-v1", "bge-large-en-v1.5", "gte-large")


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _load_handle(model: EmbeddingModel, device: str):
    if model.backend == BACKEND_SENTENCE_TRANSFORMERS:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            model.repo_id,
            revision=model.revision,
            device=device,
            trust_remote_code=model.trust_remote_code,
        )
    if model.backend == BACKEND_MODEL2VEC:
        from model2vec import StaticModel

        # model2vec's loader has no revision parameter. Acceptable only because
        # potion is dev-loop-only (see DEFAULT_MODELS) and never backs a judgment.
        return StaticModel.from_pretrained(model.repo_id)
    raise ValueError(f"unknown backend: {model.backend!r} for model {model.name!r}")


def get_encoder(model: EmbeddingModel, device: str = "cpu") -> Callable[[list[str]], np.ndarray]:
    """Load `model` once and return a closure matching encode(texts) -> ndarray.

    The returned vectors are always L2-normalized, so cosine similarity is a
    plain dot product downstream.
    """
    handle = _load_handle(model, device)

    def encode(texts: list[str]) -> np.ndarray:
        inputs = (
            [f"{model.query_prefix}{text}" for text in texts] if model.query_prefix else list(texts)
        )

        if model.backend == BACKEND_SENTENCE_TRANSFORMERS:
            vectors = handle.encode(inputs, normalize_embeddings=True, convert_to_numpy=True)
        else:  # BACKEND_MODEL2VEC
            vectors = _l2_normalize(np.asarray(handle.encode(inputs), dtype=np.float32))

        return np.asarray(vectors, dtype=np.float32)

    return encode


_SANITY_BASE = "Open the file and save it as a PNG."
_SANITY_PARAPHRASE = "Please open the file and export it in PNG format."
_SANITY_UNRELATED = "What is the boiling point of water at sea level?"


def check_encoder_sanity(model: EmbeddingModel, device: str = "cpu") -> None:
    """Smoke-test an encoder before trusting it in a real run.

    Guards against the failure mode this design keeps calling out: a wrong
    prefix or pooling setting doesn't raise, it just produces a plausible but
    wrong number. This catches that before it reaches a metrics table.
    """
    encoder = get_encoder(model, device=device)
    vectors = encoder([_SANITY_BASE, _SANITY_BASE, _SANITY_PARAPHRASE, _SANITY_UNRELATED])
    identical_sim = float(np.dot(vectors[0], vectors[1]))
    paraphrase_sim = float(np.dot(vectors[0], vectors[2]))
    unrelated_sim = float(np.dot(vectors[0], vectors[3]))

    if identical_sim < 0.999:
        raise SanityCheckError(
            f"{model.name}: identical strings scored {identical_sim:.4f}, expected ~1.0"
        )
    if paraphrase_sim <= unrelated_sim:
        raise SanityCheckError(
            f"{model.name}: paraphrase ({paraphrase_sim:.4f}) did not score above "
            f"unrelated ({unrelated_sim:.4f})"
        )
