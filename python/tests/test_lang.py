# tests for birblib.lang: the canonical id is the ISO 639-1 code; display_name resolves a
# human-readable name and FAILS LOUD on an unknown code (never passes the bare code through).
import pytest

from birblib import lang


def test_display_name_resolves_known_codes():
    assert lang.display_name("en") == "English"
    assert lang.display_name("nl") == "Dutch"


def test_normalize_folds_region_and_case():
    assert lang.normalize("EN") == "en"
    assert lang.normalize("en-US") == "en"
    assert lang.normalize("en_GB") == "en"
    assert lang.normalize("zh-Hans") == "zh"


def test_display_name_accepts_region_tagged_codes():
    # the "fluent en" bug fix: a region-tagged code still resolves to the language name.
    assert lang.display_name("en-US") == "English"


def test_unknown_code_raises_not_passes_through():
    assert lang.is_known("xx") is False
    with pytest.raises(lang.UnknownLanguage):
        lang.display_name("xx")
