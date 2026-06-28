# birblib.names -- safe_name, the filename normalizer the file-ingest birbs all carried.
#
# magpie and turtledove shipped this character-for-character identical, with the same
# fifteen-case test suite, because an ingest birb cannot trust an inbox filename: iOS
# hands us spaces, a crafted name carries "../../" or a bidi override, accented latin
# slugs two different ways under NFC vs NFD. one tested copy lives here; a birb that
# archives an operator's file under a legible name imports it.
#
# CASE + COLLISIONS (answering @janearc's review question): safe_name lowercases, so on a
# CASE-INSENSITIVE filesystem (default macOS, the shop's box) "Memo.m4a" and "memo.m4a" slug
# the same, and on a case-SENSITIVE fs they still slug the same -- the slug is deliberately
# case-folded so a name means one thing regardless of which fs it lands on. A name with no
# ascii form (CJK, Cyrillic) folds to "untitled". Neither is data loss, and this is the why:
# the human-facing slug is ONLY for legibility; uniqueness comes from the bento's uuid
# directory. Two "untitled" memos (or a "Memo"/"memo" pair) land in different uuid dirs and
# never collide. The slug is a label, not a key.

import re
import unicodedata
from pathlib import Path

# cap the slug well under the common 255-byte filesystem name limit. the bento's uuid dir
# keeps separate runs separate, so the human-facing name need not be unique -- only legible
# and writable everywhere.
_MAX_STEM = 200


def safe_name(filename: str) -> str:
    # normalize to ascii, lowercase, no spaces or shell-hostile characters; runs of unsafe
    # chars collapse to a single hyphen. Path(...).stem drops any directory parts, so
    # traversal ("../../x") and separators cannot survive a name.
    p = Path(filename)
    # decompose and drop combining marks so accented latin folds to its base letter
    # (café -> cafe) the SAME way regardless of NFC vs NFD input form -- otherwise the one
    # visible name slugs two different ways and two files collide differently.
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", p.stem) if not unicodedata.combining(c)
    )
    # anything still outside the safe set -- unicode punctuation, CJK, emoji, control,
    # bidi/zero-width -- collapses to a hyphen; a name with no ascii form (a CJK or
    # Cyrillic name) falls through to "untitled" (a naming choice, not loss: see the uuid dir).
    stem = re.sub(r"[^a-z0-9._-]+", "-", folded.lower()).strip("-_.") or "untitled"
    # cap length, then re-strip in case the cut left a trailing separator.
    stem = stem[:_MAX_STEM].rstrip("-_.") or "untitled"
    suffix = "".join(
        c for c in unicodedata.normalize("NFKD", p.suffix) if not unicodedata.combining(c)
    ).lower()
    suffix = re.sub(r"[^a-z0-9.]+", "", suffix)
    return stem + suffix
