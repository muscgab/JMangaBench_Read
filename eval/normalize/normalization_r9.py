"""Normalization r9 (adopted 2026-10-17; = RIN v1.1, the scoring normalization of JMangaBench_Read v1.3.1).

r9 = r8 + solid hearts fold to the hollow heart: ♥ (U+2665) and ❤ (U+2764), with or without a variation selector
(U+FE0F / U+FE0E), -> ♡ (U+2661). User 2026-10-17: "把心号归一，归一成那个不是实心的心号". Read v1.2 / v1.3 and Sol
labels already use only ♡, so the rule changes predictions only. r7 / r8 stay untouched so earlier results remain reproducible.
"""
from __future__ import annotations

import re

from normalization_r8 import normalize_r8

POLICY_R9 = "manga_nar_semantic_r9_20261017"
_HEART = re.compile("[♥❤][︎️]?")


def fold_hearts(text: str) -> str:
    return _HEART.sub("♡", text)


def normalize_r9(text: str) -> str:
    return fold_hearts(normalize_r8(text))


if __name__ == "__main__":
    cases = {"あっ♥": "あっ♡", "あっ❤": "あっ♡", "あっ❤️": "あっ♡", "♥︎ん": "♡ん", "あっ♡": "あっ♡",
             "♥♥♡": "♡♡♡", "言う⁇": "言う??", "う゛っ♥": "ゔっ♡", "💕": "💕"}
    for source, expected in cases.items():
        got = normalize_r9(source)
        assert got == expected, (source, got, expected)
        assert normalize_r9(got) == got, ("not idempotent", source)
    print("ok", len(cases))
