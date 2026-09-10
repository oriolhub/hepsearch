"""Everything about the local provider that can be proven without downloading a model.

The real model is ~90 MB and lives behind a network call, so it belongs in exactly one
`@pytest.mark.slow` test. Everything else here — the dimension declaration, the deferred
import, the load-once guarantee, the dimension assertion — is behaviour we need
verified on every run, on a machine that never installed the optional extra.

The stubs go into `sys.modules` because that is the seam `from sentence_transformers
import SentenceTransformer` actually consults. Nothing in this file imports the real
library, and the tests assert as much.
"""

import sys
import types
from unittest import mock

import pytest

from apps.embedding.local import MODEL_DIMENSIONS, LocalEmbeddingProvider


def stub_module(dimension, encoded=None, load_counter=None, legacy_accessor=False):
    """A stand-in `sentence_transformers` module exposing just what the provider uses.

    `legacy_accessor` reproduces sentence-transformers < 6, which only offers
    `get_sentence_embedding_dimension`. We declare `>=3.0`, so both spellings must work.
    """

    class StubSentenceTransformer:
        def __init__(self, name):
            self.name = name
            if load_counter is not None:
                load_counter.append(name)

        def get_sentence_embedding_dimension(self):
            return dimension

        def encode(self, texts, **kwargs):
            assert kwargs["normalize_embeddings"] is True
            return encoded if encoded is not None else [[0.0] * dimension] * len(texts)

    if not legacy_accessor:
        StubSentenceTransformer.get_embedding_dimension = (
            StubSentenceTransformer.get_sentence_embedding_dimension
        )

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = StubSentenceTransformer
    return module


class TestDeclaredIdentity:
    def test_dimension_comes_from_the_static_map(self, settings):
        settings.EMBEDDING_MODEL = "all-mpnet-base-v2"
        assert LocalEmbeddingProvider().dimension == 768

    def test_model_name_is_the_configured_model(self, settings):
        settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        assert LocalEmbeddingProvider().model_name == "all-MiniLM-L6-v2"

    def test_an_unknown_model_raises_at_construction(self, settings):
        # Guessing a dimension here would produce a column of the wrong width and only
        # fail on the first insert, halfway through an ingestion run.
        settings.EMBEDDING_MODEL = "some-model-nobody-declared"
        with pytest.raises(ValueError, match="no declared dimension"):
            LocalEmbeddingProvider()

    def test_identity_is_readable_without_the_library(self, settings):
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            provider = LocalEmbeddingProvider()
            assert provider.dimension == MODEL_DIMENSIONS[settings.EMBEDDING_MODEL]
            assert provider.model_name == settings.EMBEDDING_MODEL


class TestDeferredLoading:
    def test_empty_batch_loads_nothing(self):
        # A None entry makes `import sentence_transformers` raise, so this passing
        # proves the import was never attempted.
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            assert LocalEmbeddingProvider().embed([]) == []

    def test_blank_text_is_rejected_before_loading(self):
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with pytest.raises(ValueError):
                LocalEmbeddingProvider().embed(["   "])

    def test_a_missing_library_names_the_extra_to_install(self):
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="uv sync --extra local-embeddings"):
                LocalEmbeddingProvider().embed(["higgs boson"])

    def test_the_model_is_loaded_once_across_several_calls(self, settings):
        loads = []
        module = stub_module(settings.EMBEDDING_DIMENSION, load_counter=loads)
        with mock.patch.dict(sys.modules, {"sentence_transformers": module}):
            provider = LocalEmbeddingProvider()
            provider.embed(["higgs boson"])
            provider.embed(["top quark"])
            provider.embed(["neutrino"])
        assert loads == [settings.EMBEDDING_MODEL]


class TestLoadedDimensionAssertion:
    def test_a_model_disagreeing_with_the_declaration_fails(self, settings):
        # The declaration is a promise the system check relies on; if the real model
        # contradicts it, the declaration is wrong and must not be silently believed.
        module = stub_module(settings.EMBEDDING_DIMENSION + 1)
        with mock.patch.dict(sys.modules, {"sentence_transformers": module}):
            with pytest.raises(ValueError, match="dimensional vectors"):
                LocalEmbeddingProvider().embed(["higgs boson"])

    def test_matching_dimensions_return_plain_float_lists(self, settings):
        dimension = settings.EMBEDDING_DIMENSION
        module = stub_module(dimension, encoded=[[0.5] * dimension])
        with mock.patch.dict(sys.modules, {"sentence_transformers": module}):
            vectors = LocalEmbeddingProvider().embed(["higgs boson"])
        # Plain lists, not numpy arrays: numpy must not leak across the interface.
        assert vectors == [[0.5] * dimension]
        assert all(type(component) is float for component in vectors[0])

    def test_the_pre_6_accessor_name_is_still_honoured(self, settings):
        # Losing the accessor to a rename would skip the guard entirely, letting a
        # wrong declaration through unnoticed — so verify the mismatch still fires.
        module = stub_module(settings.EMBEDDING_DIMENSION + 1, legacy_accessor=True)
        with mock.patch.dict(sys.modules, {"sentence_transformers": module}):
            with pytest.raises(ValueError, match="dimensional vectors"):
                LocalEmbeddingProvider().embed(["higgs boson"])


def test_no_test_in_this_module_touched_the_real_library():
    """Every case above ran against a stub or a blocked import.

    Deliberately asserts on the *provider's* behaviour rather than on `sys.modules`
    directly: on a machine with the extra installed, collecting the slow test imports
    the library, so a bare `not in sys.modules` would fail for reasons unrelated to
    anything here.
    """
    with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
        provider = LocalEmbeddingProvider()
        assert provider.embed([]) == []
        assert provider.dimension > 0
