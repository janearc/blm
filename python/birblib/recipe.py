# birblib.recipe -- the recipe seam, for the birbs that hold the recipe principle.
#
# the principle (grackle's, the cleanest in the set): the caller submits INTENT (a
# prompt), the PIPELINE owns the tuning (the recipe), and a caller override is honored but
# recorded as an anti-pattern -- so a bento that was second-guessed says so. leaf birbs
# (image, speech, text-clean) hold this; an engine birb that exposes raw params instead
# declares named presets and does not use this module.
#
# the recipe's FIELD SHAPE is the birb's own (grackle's width/height/steps/...): birblib
# does not freeze it (that is open decision §9.2). what birblib owns is the one semantic
# every recipe birb shares -- lay caller overrides over the pipeline's values, validate
# the override KEYS against an allow-list, and record what was overridden. that record is
# what lands under the manifest's detail as the anti_pattern signal.

import dataclasses


@dataclasses.dataclass
class Request:
    # intent. `prompt` is the only thing a caller must supply; `recipe` names the tuned
    # config the pipeline owns; `overrides` is the anti-pattern path (honored, recorded).
    prompt: str
    recipe: str = ""
    overrides: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Resolution:
    # the outcome of laying a request's overrides over a recipe's values. `values` is the
    # fully-resolved field set the birb runs with; `overrides` is what the caller forced
    # (empty is the blessed path); `anti_pattern` is the honest bool for the manifest.
    values: dict
    overrides: dict
    anti_pattern: bool


def resolve(recipe_values: dict, overrides: dict, overridable) -> Resolution:
    # lay `overrides` over `recipe_values`, rejecting any override key not in `overridable`
    # (a typo or an attempt to override a field the pipeline does not surrender fails loud,
    # before the work, not silently). returns a Resolution; the birb does its own
    # domain validation (grackle's "dims on the 64-grid") on resolution.values afterward.
    bad = set(overrides) - set(overridable)
    if bad:
        raise ValueError(
            f"unknown override(s) {sorted(bad)}; overridable: {sorted(overridable)}"
        )
    values = dict(recipe_values)
    values.update(overrides)
    return Resolution(values=values, overrides=dict(overrides), anti_pattern=bool(overrides))
