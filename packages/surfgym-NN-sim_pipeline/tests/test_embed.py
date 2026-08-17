"""Uses potion-base-32m only -- it's the dev-loop model precisely because it's
fast enough to run in a test (no GPU, no multi-second transformer load).
"""

import pytest
from surfgym_nn_sim_pipeline.embed import (
    MODELS,
    SanityCheckError,
    check_encoder_sanity,
    get_encoder,
)

model2vec = pytest.importorskip("model2vec")

POTION = MODELS["potion-base-32m"]


def test_sanity_check_passes_for_potion():
    check_encoder_sanity(POTION)


def test_encoder_returns_l2_normalized_vectors():
    encoder = get_encoder(POTION)
    vectors = encoder(["one sentence", "a different one"])

    assert vectors.shape[0] == 2
    norms = (vectors**2).sum(axis=1) ** 0.5
    assert all(abs(norm - 1.0) < 1e-4 for norm in norms)


def test_sanity_check_raises_on_broken_encoder(monkeypatch):
    import surfgym_nn_sim_pipeline.embed as embed_module

    def fake_get_encoder(model, device="cpu"):
        # always return the same vector regardless of input -- an encoder this
        # broken should fail the sanity check rather than silently pass.
        import numpy as np

        def encoder(texts):
            return np.tile(np.array([[1.0, 0.0]], dtype=np.float32), (len(texts), 1))

        return encoder

    monkeypatch.setattr(embed_module, "get_encoder", fake_get_encoder)

    with pytest.raises(SanityCheckError):
        embed_module.check_encoder_sanity(POTION)
