"""Normalization r5 (adopted 2026-10-03 for the manga eval benchmark).

r5 = r4 + one fix: runs of 2+ wave marks -> one "〜", matching r4's long-mark rule (runs of 2+ "ー" -> one "ー").
r4 kept r3's "single vs multiple" distinction for 〜 (〜 != 〜〜, 〜〜 == 〜〜〜〜) while collapsing ー runs; the user
judged this inconsistency a rule omission. r4 stays untouched so earlier r4 results remain reproducible.
"""
from __future__ import annotations

import re

from normalization_r4 import normalize_r4

POLICY_R5 = "manga_nar_semantic_r5_20261003"
_WAVE = re.compile(r"〜{2,}")


def normalize_r5(text: str) -> str:
    return _WAVE.sub("〜", normalize_r4(text))


if __name__ == "__main__":
    cases = {"あ〜": "あ〜", "あ〜〜": "あ〜", "あ〜〜〜〜": "あ〜", "あ～～～": "あ〜", "あ~~": "あ〜", "あーーー": "あー",
             "あ〜ー": "あ〜ー", "あー〜": "あー〜", "いやなよか〜〜ん…": "いやなよか〜ん…", "……": "…", "～": "〜",
             "それは──": "それはー", "え…!?": "え…!?", "OK OK": "OKOK", "1.5": "1.5", "ジョン・スミス": "ジョン・スミス"}
    for source, expected in cases.items():
        got = normalize_r5(source)
        assert got == expected, (source, got, expected)
        assert normalize_r5(got) == got, ("not idempotent", source)
    print("normalize_r5 self-check passed:", len(cases), "cases")
