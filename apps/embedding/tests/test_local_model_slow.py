"""The one test that loads the real model. Excluded from the default run.

Everything else about `LocalEmbeddingProvider` is verified against stubs, but stubs
cannot tell us whether `all-MiniLM-L6-v2` actually produces 384 dimensions or whether
its geometry is any good. That needs the real thing — a ~90 MB download and several
seconds of load — which is why this is the only module marked `slow`.

The `importorskip` sits in a fixture rather than at module level, and both halves of
that matter:

- Not a plain import at module scope: **pytest collects before it deselects**, so
  anything imported there is paid for even by a run that deselects every test in the
  file. Importing `sentence_transformers` at module scope added ~13 s of torch import
  to the default suite on a machine with the extra installed.
- Not a plain marker either: on a machine that never ran `uv sync --extra
  local-embeddings`, a module-scope import would make collection *fail* rather than
  skip. `importorskip` inside the fixture keeps the default run fast and green
  regardless of what is installed.

Nothing at module scope needs the library — `apps.embedding.local` imports it lazily by
design, so that module is importable either way.

    uv sync --extra local-embeddings
    uv run pytest -m slow
"""

import math

import pytest

from apps.embedding.local import LocalEmbeddingProvider

pytestmark = pytest.mark.slow


@pytest.fixture
def provider():
    pytest.importorskip(
        "sentence_transformers",
        reason="install the optional extra: uv sync --extra local-embeddings",
    )
    return LocalEmbeddingProvider()


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_the_real_model_honours_the_embedding_contract(provider, settings):
    (vector,) = provider.embed(["measurement of the higgs boson self-coupling"])
    assert len(vector) == settings.EMBEDDING_DIMENSION
    assert len(vector) == provider.dimension
    assert math.sqrt(sum(c * c for c in vector)) == pytest.approx(1.0, abs=1e-5)

    query, related, unrelated = provider.embed(
        [
            "how do we measure the Higgs self-coupling?",
            "Constraints on the trilinear scalar interaction from di-boson production",
            "Seismic attenuation in the Earth's lower mantle",
        ]
    )
    assert cosine(query, related) > cosine(query, unrelated)
