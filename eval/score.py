"""JMangaBench_Read scoring: python eval/score.py --pred preds.jsonl [--gt data/gt.jsonl | data/gt_sfx.jsonl] [--name MODEL] [--out result.json]
preds.jsonl: one line per box, {"key": ..., "pred": "..."}; missing keys count as empty predictions.
Metrics (after r7 normalization): composite (1 - NED, printed / non-printed averaged), per-subset NED score (1 - NED mean),
CER (total edit distance / total label characters), EM, EM_raw (no normalization), EM 95% Wilson CI.
Subsets: all / hard / gold / printed / non_printed, plus gold_random_audit, length, orientation and role buckets.
Default --gt is the main set. The composite is defined for the main set; for the SFX set use the "all" section (1 - NED, CER, EM)."""
import argparse, json, math, sys
from pathlib import Path
B = Path(__file__).resolve().parent
sys.path.insert(0, str(B / "normalize")); from normalization_r7 import normalize_r7 as N

def edit(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1): cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def wilson(k, n, z=1.96):
    if not n: return [0, 0]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 2), round(100 * (c + h), 2)]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pred", required=True); ap.add_argument("--gt", default=str(B.parent / "data" / "gt.jsonl"))
    ap.add_argument("--name", default=None); ap.add_argument("--out", default=None); a = ap.parse_args()
    gt = [json.loads(l) for l in open(a.gt)]
    pred = {}
    for l in open(a.pred):
        if l.strip(): r = json.loads(l); pred[r["key"]] = r.get("pred") or ""
    rows = []
    for g in gt:
        p = pred.get(g["key"], ""); pn = N(p)
        ed = edit(pn, g["text_r7"])
        rows.append({**g, "em": pn == g["text_r7"], "em_raw": p == g["text"], "ed": ed, "s": 1 - ed / max(len(g["text_r7"]), len(pn), 1), "missing": g["key"] not in pred})
    L = lambda g: "1-4" if g["n_chars"] <= 4 else "5-16" if g["n_chars"] <= 16 else "17-32" if g["n_chars"] <= 32 else ">32"
    sections = {"hard": lambda g: g["gold_hard"], "gold": lambda g: g["gold"], "all": lambda g: True, "non_printed": lambda g: g["non_printed"],
                "printed": lambda g: g["printed"], "gold_random_audit": lambda g: g["gold_random_audit"]}
    for b in ("1-4", "5-16", "17-32", ">32"): sections[f"len_{b}"] = (lambda b: lambda g: L(g) == b)(b)
    for o in ("vertical", "horizontal", "square"): sections[f"orient_{o}"] = (lambda o: lambda g: g["orientation"] == o)(o)
    for r, nm in (("d", "dialogue"), ("n", "narration"), ("o", "other")): sections[f"role_{nm}"] = (lambda r: lambda g: g["role"] == r)(r)
    res = {"model": a.name, "n_pred": len(pred), "missing": sum(r["missing"] for r in rows), "normalization": "manga_nar_semantic_r7_20261003", "sections": {}}
    for s, f in sections.items():
        S = [r for r in rows if f(r)]; n = len(S); k = sum(r["em"] for r in S); chars = sum(r["n_chars"] for r in S)
        res["sections"][s] = {"n": n, "NED_score": round(100 * sum(r["s"] for r in S) / n, 2) if n else None, "EM": round(100 * k / n, 2) if n else None, "EM_95ci": wilson(k, n),
                              "CER": round(100 * sum(r["ed"] for r in S) / chars, 2) if chars else None,
                              "EM_raw": round(100 * sum(r["em_raw"] for r in S) / n, 2) if n else None}
    ned = lambda f: 100 * sum(r["s"] for r in rows if f(r)) / max(1, sum(1 for r in rows if f(r)))
    res["composite"] = round((ned(lambda r: r["printed"]) + ned(lambda r: r["non_printed"])) / 2, 2)
    print(f"composite {res['composite']}")
    print(f"{'section':22s} {'n':>5s} {'1-NED':>7s} {'EM%':>7s} {'95%CI':>15s} {'CER%':>7s} {'EMraw%':>7s}")
    for s, v in res["sections"].items(): print(f"{s:22s} {v['n']:5d} {v['NED_score']!s:>7s} {v['EM']!s:>7s} {str(v['EM_95ci']):>15s} {v['CER']!s:>7s} {v['EM_raw']!s:>7s}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
        Path(a.out).with_suffix(".per_item.jsonl").write_text("".join(json.dumps({"key": r["key"], "pred": pred.get(r["key"], ""), "em": r["em"], "ed": r["ed"], "s": round(r["s"], 6)}, ensure_ascii=False) + "\n" for r in rows))

if __name__ == "__main__": main()
