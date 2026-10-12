"""Normalization r8 (adopted 2026-10-11 for Read v1.3 scoring).

r8 = r7 + two symbol unifications the user found while reviewing Read v1.3 (four text-queue boxes noted "归一化问题",
where all three readers agreed but r7 kept the spellings apart):
  ⁇ (U+2047) -> ??   (r7 already splits ⁉ ⁈ ‼ into two characters; ⁇ was missing)
  ⊠ (U+22A0) -> ☒ (U+2612)   (the same censor box glyph)
User 2026-10-11: "⁇ 转成 ??，⊠ 和 ☒加上吧；汉字零那个不加上" -> 〇 (U+3007) and ○ stay distinct.
r7 stays untouched so earlier results (Read v1.2, training labels) remain reproducible.
"""
from __future__ import annotations

from normalization_r7 import normalize_r7

POLICY_R8 = "manga_nar_semantic_r8_20261011"
_R8 = str.maketrans({"⁇": "??", "⊠": "☒"})


def normalize_r8(text: str) -> str:
    return normalize_r7(text).translate(_R8)


if __name__ == "__main__":
    cases = {"言う⁇": "言う??", "言う??": "言う??", "言う？？": "言う??", "して⊠⊠を": "して☒☒を", "して☒☒を": "して☒☒を",
             "ド〇ール": "ド〇ール", "ド○ール": "ド○ール", "ド◯ール": "ド○ール", "何⁉": "何!?", "う゛っ": "ゔっ"}
    for source, expected in cases.items():
        got = normalize_r8(source)
        assert got == expected, (source, got, expected)
    print("ok", len(cases))
