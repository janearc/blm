# tests for birblib.names.safe_name -- the same hard cases the audio birbs pinned (a
# filename is a source of many sad nights). ported with the utility so the contract lives
# where the code does.
import unicodedata

import pytest

from birblib.names import safe_name


def test_normalizes_spaces():
    assert safe_name("freezer food and handsome man.m4a") == "freezer-food-and-handsome-man.m4a"


@pytest.mark.parametrize(
    "given, expected",
    [
        ("Voice Memo 12.m4a", "voice-memo-12.m4a"),
        ("a  b   c.WAV", "a-b-c.wav"),
        ("weird!!!name???.mp3", "weird-name.mp3"),
        ("--leading.trailing--.flac", "leading.trailing.flac"),
        ("keep_me.ok-1.aac", "keep_me.ok-1.aac"),
        ("memo\nwith\nnewlines.m4a", "memo-with-newlines.m4a"),
        ("tab\tseparated.m4a", "tab-separated.m4a"),
        ("null\x00byte.m4a", "null-byte.m4a"),
        ("zero​width.m4a", "zero-width.m4a"),
        ("rtl‮override.m4a", "rtl-override.m4a"),
        ("emoji \U0001f600 memo.m4a", "emoji-memo.m4a"),
        ("café.m4a", "cafe.m4a"),
        ("résumé.m4a", "resume.m4a"),
        ("smart’quote.m4a", "smart-quote.m4a"),
        ("a—b.m4a", "a-b.m4a"),
    ],
)
def test_cases(given, expected):
    assert safe_name(given) == expected


def test_empty_stem_falls_back_to_untitled():
    assert safe_name("???.m4a") == "untitled.m4a"


def test_non_latin_falls_back_to_untitled():
    assert safe_name("日本語.m4a") == "untitled.m4a"
    assert safe_name("Москва.m4a") == "untitled.m4a"


def test_normalization_stable_nfc_equals_nfd():
    nfc = unicodedata.normalize("NFC", "café.m4a")
    nfd = unicodedata.normalize("NFD", "café.m4a")
    assert safe_name(nfc) == safe_name(nfd) == "cafe.m4a"


def test_neutralizes_path_traversal():
    assert safe_name("../../etc/passwd.m4a") == "passwd.m4a"
    assert safe_name("a/b/c.m4a") == "c.m4a"


def test_caps_length():
    out = safe_name("a" * 300 + ".m4a")
    assert out.endswith(".m4a")
    assert len(out) - len(".m4a") <= 200
