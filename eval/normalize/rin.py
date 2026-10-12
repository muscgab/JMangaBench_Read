"""RIN (Reading-Invariant Normalization) v1, the scoring normalization of JMangaBench_Read v1.3.

RIN merges spelling variants that do not change what a reader reads: character width, whitespace, the form and length of
pause dots, long marks, wave marks and dashes, quote forms, the encoding of voicing marks, and a few compatibility characters.
Characters, kana size, brackets and the presence of a voicing mark are kept. RIN v1 is identical to the internal rule set
r8 (policy id manga_nar_semantic_r8_20261011): r7 (used by Read v1.2) plus "⁇" -> "??" and "⊠" -> "☒".
"""
from normalization_r8 import normalize_r8

POLICY_RIN = "RIN-1 (manga_nar_semantic_r8_20261011)"


def normalize_rin(text: str) -> str:
    return normalize_r8(text)
