# birblib.lang -- one canonical language id and a code -> display-name resolver.
#
# the canonical identifier is the ISO 639-1 code ("en", "nl"), nothing else. a birb that
# needs a HUMAN-READABLE name in a prompt asks display_name() -- it never interpolates a
# raw code (the "fluent en" bug, where a prompt said "respond in fluent en" instead of
# "fluent English"). one token (the code) feeds both a voice-map birb and a prompt birb,
# so the live-translation fan-out does not each re-derive the mapping.
#
# the table is the ISO 639-1 set the fleet actually uses, curated rather than pulled from
# a dependency (the box is on a connectivity-hostile network; a vendored dict is honest
# and offline). extend it as a birb needs a language -- a code with no name fails LOUD
# (UnknownLanguage), it does not pass the bare code through.
#
# SCOPE (answering @janearc's review question): the canonical id is a SINGLE language. A
# bento is in one language at a time; this module does not model CODE-SWITCHING (a recording
# that moves between, say, Dutch and English mid-utterance). Code-switching is a real but
# SEPARATE concern -- a future seam that would carry a sequence or a primary+secondary, owned
# by the transcription birb, not by this id. Deliberately out of scope here so the one-token
# id stays simple and feeds both a voice-map birb and a prompt birb without ambiguity.

# ISO 639-1 (two-letter) code -> English display name. add rows as needed.
_NAMES = {
    "ar": "Arabic",
    "bn": "Bengali",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "zh": "Chinese",
}


class UnknownLanguage(ValueError):  # noqa: N818 - reads as the bad value it names
    # the code is not in the table -- fail loud rather than interpolate a bare code into a
    # prompt or a voice map. add the row to _NAMES if the language is real.
    pass


def normalize(code: str) -> str:
    # fold a code to its canonical ISO 639-1 form: lowercase, and drop any region/script
    # subtag ("en-US", "en_GB", "zh-Hans" -> "en", "en", "zh"). the canonical id is the
    # language alone; region is a separate concern a birb carries elsewhere if it needs it.
    return code.strip().lower().replace("_", "-").split("-", 1)[0]


def is_known(code: str) -> bool:
    return normalize(code) in _NAMES


def display_name(code: str) -> str:
    # the human-readable English name for a code ("en" -> "English"), for a prompt. raises
    # UnknownLanguage on a code with no name -- the named-wall rule applied to language.
    key = normalize(code)
    if key not in _NAMES:
        raise UnknownLanguage(f"no display name for language code {code!r}")
    return _NAMES[key]
