"""Versioned NAR targets alongside the immutable legacy CTC/visual contract.

This module does not render, repair pixels, infer OCR text, or modify old labels.
Whitespace is retained as a single ASCII boundary space; lexical scoring removes
it only AFTER normalization, so independent punctuation spans are not joined.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json
import re
import unicodedata as ud

import regex

POLICY = "manga_nar_semantic_r3_6816_pause_20260909_v1"
LEXICAL_POLICY = "manga_nar_lexical_r3_20260909_v1"
LEGACY_DICTIONARY_SHA256 = "a2226c666f31829aafe7adecba85c1008b2221cc8873ab9481e7cb5dad09c318"
EXTRA_CHARACTERS = ("…", "—", "ヘ", "ベ", "ペ", "∼", "─", "–", " ")
DICTIONARY_COUNT = 6816
DOT_RULE = "dot_pause_short_or_long"
# These source glyph variants no longer have independent output classes,
# including inside protected text. Protection still preserves literal counts.
NON_TARGET_ALIASES = {"·": "・", "‐": "-", "‑": "-", "―": "—",
                      "‥": "・・", "−": "-", "⋯": "…", "◯": "○", "〰": "〜"}
DOTS = {".": ".", "．": ".", "・": "・", "･": "・", "·": "・",
        "…": "・・・", "⋯": "・・・", "‥": "・・"}
ALIASES = {"～": "〜", "〰": "〜", "ｰ": "ー", "·": "・", "◯": "○",
           "―": "—", "−": "-", "‐": "-", "‑": "-"}
COMPAT = {"″": "′′", "‼": "!!", "⁈": "?!", "⁉": "!?", "℃": "°C",
          "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
          "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
          "㈱": "(株)", "㎏": "kg", "㎜": "mm", "㎝": "cm", "㎞": "km", "㏄": "cc"}
_GRAPHEMES = regex.compile(r"\X")
_LEXICAL_CHAR = regex.compile(r"[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Latin}]")
_LEXICAL_MODIFIERS = frozenset("ー々〻ヽヾゝゞ")
_TECHNICAL_PATTERNS = (
    ("backtick_code", re.compile(r"`[^`\r\n]*`")),
    ("url", re.compile(r"(?:https?://|ftp://|www\.)[^\s<>\"「」『』]+", re.I)),
    ("email", re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("relative_path", re.compile(r"(?<!\w)\.{1,2}[/\\][A-Za-z0-9_./\\~:-]+")),
    ("numeric_range", re.compile(r"[0-9]+(?:\.[0-9]+)?[ \t]*[〜~∼]+[ \t]*[0-9]+(?:\.[0-9]+)?")),
    ("ascii_dot_range", re.compile(r"(?<!\w)[A-Za-z0-9]+\.{2,}[A-Za-z0-9]+(?!\w)")),
)


def _width(unit):
    if unit == "￥":
        return "¥"
    if (len(unit) == 1 and 0xFF01 <= ord(unit) <= 0xFF5E) or (
        unit and all(0xFF61 <= ord(c) <= 0xFF9F for c in unit)
        and any(0xFF61 <= ord(c) <= 0xFF9D for c in unit)
    ):
        return ud.normalize("NFC", ud.normalize("NFKC", unit))
    return ud.normalize("NFC", unit)


def _units(text):
    if not isinstance(text, str):
        raise TypeError("NAR input must be str")
    if any(ud.category(c) == "Cs" or (ud.category(c) == "Cc" and c not in "\t\r\n") for c in text):
        raise ValueError("NAR input contains unsupported control/surrogate")
    return [(m.start(), m.end(), m.group()) for m in _GRAPHEMES.finditer(text)]


def _protection(units, explicit, source_length):
    shadow, owners = [], []
    for a, b, unit in units:
        value = " " if unit.isspace() else _width(unit)
        shadow.append(value)
        owners.extend([(a, b)] * len(value))
    value = "".join(shadow)
    found = []
    for name, pattern in _TECHNICAL_PATTERNS:
        for m in pattern.finditer(value):
            found.append({"raw_start": owners[m.start()][0], "raw_end": owners[m.end()-1][1], "reason": name})
    for span in explicit or ():
        a, b = span["raw_start"], span["raw_end"]
        if type(a) is not int or type(b) is not int or not 0 <= a < b <= source_length:
            raise ValueError("invalid explicitly protected NAR span")
        found.append({"raw_start": a, "raw_end": b, "reason": str(span.get("reason", "declared_technical"))})
    return sorted(found, key=lambda r: (r["raw_start"], r["raw_end"], r["reason"]))


def build_nar_contract(source_text: str, *, protected_spans=None) -> dict:
    units = _units(source_text)
    protected = _protection(units, protected_spans, len(source_text))
    atoms = []
    for a, b, raw in units:
        reasons = sorted({p["reason"] for p in protected if a < p["raw_end"] and p["raw_start"] < b})
        if raw.isspace():
            value = " "
        else:
            value = COMPAT.get(raw, _width(raw))
            if not reasons:
                value = ALIASES.get(raw, value)
            value = "".join(NON_TARGET_ALIASES.get(c, c) for c in value)
        # One expansion token may map to the same whole source grapheme.
        atoms.extend({"char": c, "raw_start": a, "raw_end": b, "protected": bool(reasons),
                      "protection_reasons": reasons} for c in value)
    tokens, operations = [], []

    def emit(chars, selected, kind):
        a, b = selected[0]["raw_start"], selected[-1]["raw_end"]
        start = len(tokens)
        for c in chars:
            tokens.append({"text": c, "target_index": len(tokens), "raw_start": a, "raw_end": b,
                           "kind": kind, "source_text": source_text[a:b]})
        return start, len(tokens)

    i = 0
    while i < len(atoms):
        atom = atoms[i]
        c = atom["char"]
        if c == " ":
            j = i + 1
            while j < len(atoms) and atoms[j]["char"] == " ":
                j += 1
            if tokens and j < len(atoms):
                emit(" ", atoms[i:j], "boundary_space")
            i = j
            continue
        if not atom["protected"] and c in DOTS:
            j = i + 1
            while j < len(atoms) and not atoms[j]["protected"] and atoms[j]["char"] in DOTS:
                j += 1
            selected = atoms[i:j]
            points = [(point, x) for x in selected for point in DOTS[x["char"]]]
            n = len(points)
            pause_count = 0 if n < 3 else 1 if n < 6 else 2
            if n < 3:
                start = len(tokens)
                for point, owner in points:
                    emit(point, [owner], "literal_point")
                end = len(tokens)
            else:
                start, end = emit("…" * pause_count, selected, "grouped_pause")
            operations.append({"rule": DOT_RULE, "raw_start": selected[0]["raw_start"],
                               "raw_end": selected[-1]["raw_end"], "point_count": n,
                               "pause_token_count": pause_count,
                               "pause_class": "literal_points" if n < 3 else "short" if n < 6 else "long",
                               "target_start": start, "target_end": end})
            i = j
            continue
        if not atom["protected"] and c in "ー〜":
            j = i + 1
            while j < len(atoms) and not atoms[j]["protected"] and atoms[j]["char"] == c:
                j += 1
            start, end = emit(c * min(2, j-i), atoms[i:j], "prolonged_run" if c == "ー" else "wave_run")
            operations.append({"rule": "single_or_multiple", "symbol": c,
                               "raw_start": atom["raw_start"], "raw_end": atoms[j-1]["raw_end"],
                               "source_count": j-i, "target_start": start, "target_end": end})
            i = j
            continue
        emit(c, [atom], "protected_literal" if atom["protected"] else "character")
        i += 1
    return {"schema": "manga_nar_text_contract_v1", "policy": POLICY, "source_text": source_text,
            "text_target": "".join(t["text"] for t in tokens), "target_length": len(tokens),
            "tokens": tokens, "operations": operations, "protected_spans": protected,
            "mapping_policy": "normalized token to complete source span; shared run regions are allowed",
            "whitespace_policy": "preserve one boundary space; trim ends; never join separated symbol runs"}


def normalize_nar(text: str) -> str:
    """Normalize points to one pause for 3-5, two for 6+, idempotently."""
    return build_nar_contract(text)["text_target"]


def lexical_view(text: str) -> str:
    normalized = normalize_nar(text)
    result = []
    for unit in _GRAPHEMES.findall(normalized):
        base = next((c for c in unit if not ud.category(c).startswith("M")), None)
        is_script_letter = base is not None and ud.category(base).startswith("L") and bool(_LEXICAL_CHAR.fullmatch(base))
        keep = base is None or base in _LEXICAL_MODIFIERS or (
            base is not None and (ud.category(base).startswith("N") or is_script_letter)
        )
        if keep:
            # Orphan combining marks are retained as errors, never silently erased.
            result.extend(c for c in unit if ud.category(c)[0] in "LMN")
    return "".join(result)


@lru_cache(maxsize=8)
def load_nar_vocabulary(root: str | Path) -> dict:
    root = Path(root)
    path = root / "assets/manga_real_contract/nar_character_dict_v1.json"
    raw = path.read_bytes()
    data = json.loads(raw)
    chars = data["characters"]
    legacy = (root / "assets/manga_real_contract/character_dict_tcy12.txt").read_bytes()
    if sha256(legacy).hexdigest() != LEGACY_DICTIONARY_SHA256 or data["legacy_dictionary_sha256"] != LEGACY_DICTIONARY_SHA256:
        raise ValueError("legacy_dictionary_fingerprint_changed")
    if (data["policy"] != POLICY or len(chars) != DICTIONARY_COUNT
            or data.get("character_count") != len(chars)
            or len(chars) != len(set(chars)) or any(len(c) != 1 for c in chars)):
        raise ValueError("invalid_nar_dictionary")
    if chars[:len(legacy.decode().splitlines())] != legacy.decode().splitlines():
        raise ValueError("nar_base_dictionary_order_changed")
    appended = chars[len(legacy.decode().splitlines()):]
    if appended != sorted(EXTRA_CHARACTERS) or data.get("appended_characters") != appended:
        raise ValueError("nar_appended_dictionary_changed")
    return {"characters": chars, "char_to_id": {c: i for i, c in enumerate(chars)},
            "sha256": sha256(raw).hexdigest(), "policy": POLICY}


def attach_nar_contract(metadata: dict, vocabulary: dict) -> dict:
    source = metadata["source_text"]
    contract = build_nar_contract(source)
    c2i = vocabulary["char_to_id"]
    oov = sorted(set(contract["text_target"]) - set(c2i))
    if oov:
        raise ValueError("nar_target_oov:" + "".join(oov))
    glyphs = metadata["glyphs"]
    body_indices = [i for i, g in enumerate(glyphs) if g.get("kind", "body") == "body"]
    covered = set()
    for token in contract["tokens"]:
        a, b = token["raw_start"], token["raw_end"]
        owners = [i for i in body_indices if glyphs[i]["raw_start"] < b and a < glyphs[i]["raw_end"]]
        if not owners and token["kind"] != "boundary_space":
            raise ValueError("nar_token_has_no_source_glyph")
        token["glyph_indices"] = owners
        token["region_policy"] = "union_of_referenced_glyph_regions; may overlap other target tokens"
        covered.update(owners)
    if covered != set(body_indices):
        raise ValueError("nar_uncovered_body_glyph")
    # Confirm logical point counts against already rendered body-token records.
    for operation in contract["operations"]:
        if operation["rule"] != DOT_RULE:
            continue
        a, b = operation["raw_start"], operation["raw_end"]
        ids = [i for i in body_indices if glyphs[i]["raw_start"] < b and a < glyphs[i]["raw_end"]]
        actual = 0
        for i in ids:
            rendered = glyphs[i].get("render_text", glyphs[i].get("text", ""))
            if not rendered or any(c not in DOTS for c in rendered):
                raise ValueError("nar_dot_span_crosses_non_dot_glyph")
            actual += sum(len(DOTS[c]) for c in rendered)
        if actual != operation["point_count"]:
            raise ValueError("nar_dot_count_differs_from_rendered_token_record")
        operation["source_glyph_indices"] = ids
        operation["rendered_token_point_count"] = actual
        operation["pixel_validation_basis"] = "legacy pre-optics symbol QA; this check verifies its token accounting"
    contract["vocabulary_sha256"] = vocabulary["sha256"]
    contract["target_token_ids"] = [c2i[c] for c in contract["text_target"]]
    contract["token_id_convention"] = "zero-based character dictionary; EOS/model special IDs are not assigned here"
    contract["body_glyph_coverage"] = {"body_glyphs": len(body_indices), "covered": len(covered), "ruby_included": False}
    return contract


def audit_nar_metadata(metadata: dict, vocabulary: dict) -> list[str]:
    try:
        expected = attach_nar_contract(metadata, vocabulary)
    except (ValueError, KeyError, TypeError) as exc:
        return ["nar_contract_invalid:" + str(exc)]
    errors = []
    if metadata.get("nar_text_contract") != expected:
        errors.append("nar_text_contract_mismatch")
    if metadata.get("text_target_nar") != expected["text_target"]:
        errors.append("nar_top_level_target_mismatch")
    return errors
