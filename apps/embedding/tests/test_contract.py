"""The contract every embedding provider must satisfy, whatever it wraps.

These vectors all end up in one column and get compared against each other, so a
guarantee that only some implementations honour is not a guarantee. Parametrizing over
implementations means a future provider — a hosted API, say — earns this coverage by
being added to `PROVIDERS`, rather than by someone remembering to copy a test file.

Nothing here loads a model: every case is either metadata or a path the providers are
required to answer before touching one.
"""

import math

import pytest

from apps.embedding.fake import FakeEmbeddingProvider
from apps.embedding.local import LocalEmbeddingProvider
from apps.embedding.protocol import BlankTextError

PROVIDERS = {
    "fake": FakeEmbeddingProvider,
    "local": LocalEmbeddingProvider,
}


@pytest.fixture(params=sorted(PROVIDERS), ids=sorted(PROVIDERS))
def provider(request):
    return PROVIDERS[request.param]()


def norm(vector):
    return math.sqrt(sum(component * component for component in vector))


class TestMetadataIsFree:
    """Identity must be readable without embedding, because the system check needs it."""

    def test_dimension_matches_the_configured_contract(self, provider, settings):
        assert provider.dimension == settings.EMBEDDING_DIMENSION

    def test_model_name_is_a_non_empty_string(self, provider):
        assert isinstance(provider.model_name, str)
        assert provider.model_name.strip()


class TestEmptyBatch:
    def test_empty_sequence_returns_empty_list(self, provider):
        # Must hold for the local provider without sentence-transformers installed,
        # which is what proves no model was loaded.
        assert provider.embed([]) == []


class TestBlankText:
    @pytest.mark.parametrize("text", ["", " ", "\t", "\n  \n"])
    def test_blank_text_is_rejected(self, provider, text):
        with pytest.raises(BlankTextError):
            provider.embed([text])

    def test_a_blank_among_valid_texts_rejects_the_whole_batch(self, provider):
        # Partial success would leave the caller pairing N vectors with N+1 records.
        with pytest.raises(BlankTextError):
            provider.embed(["higgs boson", "   "])


class TestVectorShape:
    """Only the fake can run these offline; the local provider covers them in the slow test."""

    @pytest.fixture
    def offline_provider(self):
        return FakeEmbeddingProvider()

    def test_every_vector_is_normalized(self, offline_provider):
        vectors = offline_provider.embed(["higgs boson", "top quark mass measurement"])
        for vector in vectors:
            assert norm(vector) == pytest.approx(1.0)

    def test_every_vector_has_the_declared_dimension(self, offline_provider):
        vectors = offline_provider.embed(["higgs boson", "neutrino oscillation"])
        for vector in vectors:
            assert len(vector) == offline_provider.dimension

    def test_results_are_positionally_aligned_with_inputs(self, offline_provider):
        texts = ["alpha", "beta", "gamma"]
        batched = offline_provider.embed(texts)
        assert len(batched) == len(texts)
        for text, vector in zip(texts, batched, strict=True):
            assert offline_provider.embed([text])[0] == vector

    def test_punctuation_only_text_yields_one_unit_vector(self, offline_provider):
        # The contract is about non-whitespace content, not about what survives an
        # implementation's tokenizer. A transformer embeds "..." happily, so a
        # bag-of-words fake must not be stricter than the thing it stands in for.
        vectors = offline_provider.embed(["..."])
        assert len(vectors) == 1
        assert norm(vectors[0]) == pytest.approx(1.0)
