"""NAR target normalization r4 for the small 2-step NAR (adopted 2026-09-28).

r4 = the release r3 `normalize_nar` (NFKC width folding, aliases, protected technical spans), then:
  1. delete all whitespace (column/line breaks are not transcribed);
  2. every pause run -> one "…"  (any run of …, or of 2+ ・ / 2+ ASCII '.', mixed runs included);
     a single ・ (name separator) and a single '.' are kept;
  3. long horizontal marks — ─ ― ━ ー -> "ー", and runs of 2+ "ー" -> one "ー";
  4. short marks – ‐ ‑ − ‒ - -> "-";
  5. wave marks ~ ∼ 〜 -> "〜".
The r3 policy stays untouched so every Preview result remains reproducible; compare Preview under r4 by
applying `normalize_r4` to both its predictions and the references.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # bundle: manga_ocr_nar/ 在同目录
from manga_ocr_nar.normalization import normalize_nar  # noqa: E402

POLICY_R4 = "manga_nar_semantic_r4_20260928"
REMOVED_OUTPUT_CLASSES = (" ", "—", "─", "―", "━", "–", "‐", "‑", "−", "‒", "~", "∼")
_TABLE = str.maketrans({**{c: "ー" for c in "—─―━"}, **{c: "-" for c in "–‐‑−‒"}, "~": "〜", "∼": "〜"})
_PAUSE = re.compile(r"(?:…|・{2,}|\.{2,})(?:…|・|\.)*")
_LONG = re.compile(r"ー{2,}")


def normalize_r4(text: str) -> str:
    s = re.sub(r"\s+", "", normalize_nar(text))
    s = _PAUSE.sub("…", s.translate(_TABLE))
    return _LONG.sub("ー", s)


if __name__ == "__main__":
    cases = {"……": "…", "・・・・・・": "…", "‥": "…", "・": "・", "ジョン・スミス": "ジョン・スミス",
             "あ… い": "あ…い", "それは──": "それはー", "あーーー": "あー", "–": "-", "～": "〜", "~": "〜",
             "1.5": "1.5", "OK OK": "OKOK", "え…!?": "え…!?"}
    for source, expected in cases.items():
        got = normalize_r4(source)
        assert got == expected, (source, got, expected)
        assert normalize_r4(got) == got, ("not idempotent", source)
    print("normalize_r4 self-check passed:", len(cases), "cases")
