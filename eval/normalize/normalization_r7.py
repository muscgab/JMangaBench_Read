"""Normalization r7 (adopted 2026-10-03 for the manga eval benchmark).

r7 = r6 + dakuten/handakuten form unification. The user found models differ only in how the voicing mark is written:
precomposed vs separate (ゔ / う゛, が / か゛) and spacing vs combining marks (あ゛ U+309B / あ゙ U+3099, halfwidth ﾞﾟ).
Rule: map every mark form to the combining mark, compose with NFC where a precomposed kana exists (う゛ -> ゔ),
then write any remaining mark as the spacing form (あ゙ -> あ゛). Presence vs absence of a mark is NOT merged
(ん゛っ != んっ). r6 stays untouched so earlier results remain reproducible.
"""
from __future__ import annotations

import unicodedata

from normalization_r6 import normalize_r6

POLICY_R7 = "manga_nar_semantic_r7_20261003"
_TO_COMBINING = str.maketrans({"゛": "゙", "゜": "゚", "ﾞ": "゙", "ﾟ": "゚"})
_TO_SPACING = str.maketrans({"゙": "゛", "゚": "゜"})


def normalize_r7(text: str) -> str:
    return unicodedata.normalize("NFC", normalize_r6(text).translate(_TO_COMBINING)).translate(_TO_SPACING)


if __name__ == "__main__":
    cases = {"う゛っ": "ゔっ", "ゔっ": "ゔっ", "ゔッ": "ゔッ", "か゛": "が", "は゜": "ぱ", "あ゙あ゙": "あ゛あ゛",
             "あ゛あ゛": "あ゛あ゛", "ん゛っ♡": "ん゛っ♡", "んっ♡": "んっ♡", "エ゙": "エ゛", "ウ゛": "ヴ",
             "〝かわいい〟": '"かわいい"', "あ〜〜": "あ〜", "がぎぐ": "がぎぐ"}
    for source, expected in cases.items():
        got = normalize_r7(source)
        assert got == expected, (source, got, expected)
        assert normalize_r7(got) == got, ("not idempotent", source)
    print("normalize_r7 self-check passed:", len(cases), "cases")
