# tests for birblib.recipe: lay caller overrides over the pipeline's values, reject an
# override key the pipeline does not surrender, and record overriding as the anti-pattern.
import pytest

from birblib.recipe import Request, resolve


def test_no_overrides_is_the_blessed_path():
    r = resolve({"width": 1024, "steps": 8}, {}, {"width", "steps"})
    assert r.values == {"width": 1024, "steps": 8}
    assert r.overrides == {}
    assert r.anti_pattern is False


def test_overrides_are_layered_and_recorded():
    r = resolve({"width": 1024, "steps": 8}, {"steps": 28}, {"width", "steps"})
    assert r.values == {"width": 1024, "steps": 28}
    assert r.overrides == {"steps": 28}
    assert r.anti_pattern is True


def test_unknown_override_key_fails_loud():
    with pytest.raises(ValueError, match="unknown override"):
        resolve({"width": 1024}, {"height": 512}, {"width"})


def test_request_defaults():
    req = Request(prompt="a cat")
    assert req.prompt == "a cat"
    assert req.recipe == ""
    assert req.overrides == {}
