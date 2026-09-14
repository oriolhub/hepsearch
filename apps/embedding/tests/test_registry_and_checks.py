"""How a provider is chosen, cached, and validated before anything expensive happens."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock

import environ
import pytest
from django.core.checks import Error, Warning

from apps.embedding import registry
from apps.embedding.checks import check_embedding_dimension
from apps.embedding.fake import FakeEmbeddingProvider
from apps.embedding.local import LocalEmbeddingProvider

FAKE_PATH = "apps.embedding.fake.FakeEmbeddingProvider"
LOCAL_PATH = "apps.embedding.local.LocalEmbeddingProvider"


def shipped_settings(base_dir):
    """Load config/settings.py with the environment and the .env file suppressed.

    The "what is the default" scenario is about the literal baked into settings.py, not
    about whatever a contributor has configured locally. Executing the module through a
    throwaway spec keeps it out of sys.modules, so nothing global is disturbed.
    """
    spec = importlib.util.spec_from_file_location(
        "config._shipped_settings_probe", Path(base_dir) / "config" / "settings.py"
    )
    module = importlib.util.module_from_spec(spec)
    with (
        mock.patch.dict(os.environ, {"SECRET_KEY": "probe-only"}, clear=True),
        mock.patch.object(environ.Env, "read_env", lambda *args, **kwargs: None),
    ):
        spec.loader.exec_module(module)
    return module


class TestResolution:
    def test_the_default_is_the_real_provider(self, settings):
        # A fake default would let a corpus fill with meaningless vectors just because
        # nobody set the variable. Read from the shipped settings rather than the
        # resolved ones: a local .env may legitimately point this elsewhere.
        assert shipped_settings(settings.BASE_DIR).EMBEDDING_PROVIDER == LOCAL_PATH

    def test_the_configured_provider_is_constructed(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        registry.reset()
        assert isinstance(registry.get_provider(), LocalEmbeddingProvider)

    def test_the_setting_selects_the_provider(self, settings):
        settings.EMBEDDING_PROVIDER = FAKE_PATH
        registry.reset()
        assert isinstance(registry.get_provider(), FakeEmbeddingProvider)

    def test_an_unresolvable_path_raises_rather_than_falling_back(self, settings):
        # Substituting a working provider here would hide the misconfiguration and
        # write vectors from something nobody asked for.
        settings.EMBEDDING_PROVIDER = "apps.embedding.nope.NoSuchProvider"
        registry.reset()
        with pytest.raises(ImportError):
            registry.get_provider()


class TestCaching:
    def test_the_same_instance_is_returned(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        registry.reset()
        assert registry.get_provider() is registry.get_provider()

    def test_reset_constructs_a_fresh_instance(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        registry.reset()
        first = registry.get_provider()
        registry.reset()
        assert registry.get_provider() is not first

    def test_reset_picks_up_a_changed_setting(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        registry.reset()
        assert isinstance(registry.get_provider(), LocalEmbeddingProvider)
        settings.EMBEDDING_PROVIDER = FAKE_PATH
        registry.reset()
        assert isinstance(registry.get_provider(), FakeEmbeddingProvider)


class TestDimensionCheck:
    def test_matching_dimensions_report_nothing(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        settings.EMBEDDING_DIMENSION = 384
        settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        registry.reset()
        assert check_embedding_dimension(None) == []

    def test_a_mismatch_names_both_values(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        settings.EMBEDDING_DIMENSION = 768
        settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        registry.reset()
        (message,) = check_embedding_dimension(None)
        assert isinstance(message, Error)
        assert message.id == "embedding.E002"
        assert "768" in message.msg
        assert "384" in message.msg

    def test_an_unresolvable_provider_is_an_error_not_a_crash(self, settings):
        # `manage.py check` exists to report misconfiguration, so it must survive it.
        settings.EMBEDDING_PROVIDER = "apps.embedding.nope.NoSuchProvider"
        registry.reset()
        (message,) = check_embedding_dimension(None)
        assert isinstance(message, Error)
        assert message.id == "embedding.E001"

    def test_the_check_never_loads_a_model(self, settings):
        settings.EMBEDDING_PROVIDER = LOCAL_PATH
        settings.EMBEDDING_DIMENSION = 384
        settings.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        with mock.patch.dict(sys.modules, {"sentence_transformers": None}):
            registry.reset()
            assert check_embedding_dimension(None) == []


class TestFakeProviderWarning:
    def test_the_warning_is_silent_under_pytest(self, settings):
        # Tests configure the fake legitimately; a warning on every run is noise people
        # learn to ignore.
        settings.EMBEDDING_PROVIDER = FAKE_PATH
        registry.reset()
        assert check_embedding_dimension(None) == []

    def test_the_warning_is_emitted_outside_pytest(self, settings):
        settings.EMBEDDING_PROVIDER = FAKE_PATH
        registry.reset()
        without_pytest = {name: mod for name, mod in sys.modules.items() if name != "pytest"}
        with mock.patch.dict(sys.modules, without_pytest, clear=True):
            messages = check_embedding_dimension(None)
        (message,) = messages
        assert isinstance(message, Warning)
        assert message.id == "embedding.W001"
