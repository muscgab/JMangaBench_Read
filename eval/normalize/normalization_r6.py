"""Normalization r6 (adopted 2026-10-03 for the manga eval benchmark).

r6 = r5 + quote unification: every double-quote form (“ ” „ ‟ 〝 〞 〟 ＂ ″ ") -> '"', every single-quote form
(‘ ’ ‚ ‛ ＇ ′ ') -> "'". The user judged these variants meaningless (models mix “”, 〝〟 and " for the same glyphs).
Corner brackets 「」『』 and 〈〉 are kept distinct. r5 stays untouched so earlier r5 results remain reproducible.
"""
from __future__ import annotations

from normalization_r5 import normalize_r5

POLICY_R6 = "manga_nar_semantic_r6_20261003"
_QUOTES = str.maketrans({c: '"' for c in "“”„‟〝〞〟＂″"} | {c: "'" for c in "‘’‚‛＇′"})


def normalize_r6(text: str) -> str:
    return normalize_r5(text).translate(_QUOTES)


if __name__ == "__main__":
    cases = {"〝168321〟だね…！": '"168321"だね…!', "“１６８３２１”だね…！": '"168321"だね…!', "”こんな”関係": '"こんな"関係',
             "〝かわいい〟から": '"かわいい"から', "‘a’": "'a'", "「家族」": "「家族」", "『家族』": "『家族』", "あ〜〜": "あ〜",
             "……": "…", "〈声〉": "〈声〉"}
    for source, expected in cases.items():
        got = normalize_r6(source)
        assert got == expected, (source, got, expected)
        assert normalize_r6(got) == got, ("not idempotent", source)
    print("normalize_r6 self-check passed:", len(cases), "cases")
