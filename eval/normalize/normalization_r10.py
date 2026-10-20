"""Normalization r10 (adopted 2026-10-20; = RIN v1.2, the scoring normalization of JMangaBench_Read v1.3.2).

r10 = r9 + solid / outlined stars fold to the hollow star, as hearts do in r9: ★ (U+2605), ✩ (U+2729) and ⭐ (U+2B50),
with or without a variation selector (U+FE0F / U+FE0E), -> ☆ (U+2606). User 2026-10-20: "星星按照你的想法改动" (fold like
♡; music symbols ♪ ♫ ♬ stay distinct, user: "音乐符号不折叠"). ✡ (hexagram) is a different shape and is kept.
Read v1.2 / v1.3 labels contain ★ in 4 boxes, so labels and predictions both change. r7 / r8 / r9 stay untouched so
earlier results remain reproducible (rin.normalize_rin_v11 = r9).
"""
from __future__ import annotations

import re

from normalization_r9 import normalize_r9

POLICY_R10 = "manga_nar_semantic_r10_20261020"
_STAR = re.compile("[★✩⭐][︎️]?")


def fold_stars(text: str) -> str:
    return _STAR.sub("☆", text)


def normalize_r10(text: str) -> str:
    return fold_stars(normalize_r9(text))


if __name__ == "__main__":
    cases = {"イメチェン★": "イメチェン☆", "✩部屋": "☆部屋", "⭐️ね": "☆ね", "☆♪": "☆♪", "★♫♬": "☆♫♬",
             "✡": "✡", "あっ❤★": "あっ♡☆", "言う⁇★": "言う??☆"}
    for source, expected in cases.items():
        got = normalize_r10(source)
        assert got == expected, (source, got, expected)
        assert normalize_r10(got) == got, ("not idempotent", source)
    print("ok", len(cases))
