"""RIN (Reading-Invariant Normalization) v1.1, the scoring normalization of JMangaBench_Read v1.3.1.

RIN merges spelling variants that do not change what a reader reads: character width, whitespace, the form and length of
pause dots, long marks, wave marks and dashes, quote forms, the encoding of voicing marks, and a few compatibility characters.
Characters, kana size, brackets and the presence of a voicing mark are kept.
- RIN v1.1 (Read v1.3.1, 2026-10-17) = internal rule set r9 (policy id manga_nar_semantic_r9_20261017): RIN v1 plus solid hearts
  ♥ (U+2665) and ❤ (U+2764, with or without a variation selector) -> ♡ (U+2661). Labels already use ♡, so only predictions change.
- RIN v1 (Read v1.3) = r8 (manga_nar_semantic_r8_20261011): r7 (used by Read v1.2) plus "⁇" -> "??" and "⊠" -> "☒".
  Still available as normalize_rin_v1 for reproducing v1.3 numbers.
"""
from normalization_r8 import normalize_r8
from normalization_r9 import normalize_r9

POLICY_RIN = "RIN-1.1 (manga_nar_semantic_r9_20261017)"


def normalize_rin(text: str) -> str:
    return normalize_r9(text)


def normalize_rin_v1(text: str) -> str:
    return normalize_r8(text)
