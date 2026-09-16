import pytest

from apps.search.modes import SearchMode, parse_mode


def test_missing_mode_defaults_to_hybrid():
    assert parse_mode(None) is SearchMode.HYBRID


def test_known_mode_is_parsed():
    assert parse_mode("semantic") is SearchMode.SEMANTIC


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        parse_mode("unknown")
