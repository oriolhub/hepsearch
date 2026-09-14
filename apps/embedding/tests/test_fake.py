"""Properties specific to the offline test double.

The point of these is that the fake is not merely *a* deterministic function: it is
deterministic **across processes**, and its geometry is faithful enough that HS-011 and
HS-012 can assert real ranking behaviour with it.
"""

import json
import math
import subprocess
import sys
from unittest import mock

import pytest

from apps.embedding.fake import FakeEmbeddingProvider


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


@pytest.fixture
def provider():
    return FakeEmbeddingProvider()


def test_model_name_identifies_the_vector_space(provider, settings):
    # Not a display label: HS-010 stores it beside each vector and HS-011 refuses to
    # compare across spaces, so a fake-populated corpus is self-evident.
    #
    # The width is pinned because the name tracks the configured dimension: reading it
    # from the ambient environment made this fail for anyone whose .env set another
    # width, which is not what this test is about.
    settings.EMBEDDING_DIMENSION = 384
    assert provider.model_name == "fake-bow-384"


def test_vectors_are_identical_in_a_separate_interpreter(provider, settings):
    """The determinism that actually matters.

    `hash("higgs")` is salted per interpreter via PYTHONHASHSEED, so a fake built on it
    would embed the same abstract differently in two processes — and `embed_papers`
    writes vectors in one process while a query embeds in another. Comparing against a
    vector computed in *this* process would never catch that; only a subprocess does.
    """
    text = "higgs boson self-coupling measurement"
    here = provider.embed([text])[0]

    script = (
        "import django, json, os;"
        "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings');"
        "django.setup();"
        "from apps.embedding.fake import FakeEmbeddingProvider;"
        f"print(json.dumps(FakeEmbeddingProvider().embed([{text!r}])[0]))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    there = json.loads(completed.stdout)

    assert there == pytest.approx(here)


def test_texts_sharing_words_are_closer_than_unrelated_texts(provider):
    # Geometry, not just determinism: HS-011's "the nearest vector ranks first" is only
    # a meaningful assertion offline if related texts really do land near each other.
    a, b, unrelated = provider.embed(
        [
            "higgs boson decay to two photons",
            "higgs boson decay channels",
            "neutrino oscillation baseline experiment",
        ]
    )
    assert cosine(a, b) > cosine(a, unrelated)
    assert cosine(a, b) > cosine(b, unrelated)


def test_dimension_follows_the_configured_contract(provider, settings):
    # The fake is drop-in wherever the real provider would be, including against
    # HS-010's VectorField, so it reads the width rather than declaring its own.
    settings.EMBEDDING_DIMENSION = 16
    vector = provider.embed(["higgs boson"])[0]
    assert len(vector) == 16
    assert math.sqrt(sum(c * c for c in vector)) == pytest.approx(1.0)
    assert provider.model_name == "fake-bow-16"


def test_embedding_loads_no_embedding_library(provider):
    # A None entry makes any `import sentence_transformers` raise, which is a real
    # assertion; checking `sys.modules` directly would not be, because collecting the
    # slow test imports the library on a machine that has the extra installed.
    with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
        vector = provider.embed(["higgs boson"])[0]
    assert len(vector) == provider.dimension
