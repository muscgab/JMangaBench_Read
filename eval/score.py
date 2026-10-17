"""JMangaBench_Read v1.3.1 scoring: python eval/score.py --pred preds.jsonl [--gt data/gt.jsonl] [--name MODEL] [--out result.json]
preds.jsonl: one line per box, {"key": ..., "pred": "..."}; missing keys count as empty predictions.
Main metrics use RIN v1.1 (eval/normalize/rin.py) on prediction and label: composite (1 - NED, printed and non-printed averaged),
per-subset 1 - NED, CER (total edit distance / total label characters), EM with 95% Wilson CI.
EM_NFKC: exact match after Unicode NFKC only (prediction and raw label "text"), reported for reference.
Subsets: all / new / v12_kept / hard / gold / printed / non_printed / gold_random_audit, plus length, orientation and role buckets.
For the v1.2 SFX set (data/gt_sfx.jsonl) use the "all" section."""
import argparse, json, math, sys, unicodedata
from pathlib import Path
B = Path(__file__).resolve().parent
sys.path.insert(0, str(B / "normalize")); from rin import normalize_rin as N, POLICY_RIN

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

def score(pred, gt):
    K = lambda s: unicodedata.normalize("NFKC", s)
    rows = []
    for g in gt:
        p = pred.get(g["key"], ""); pn = N(p); ref = g.get("text_rin") or N(g["text"])
        ed = edit(pn, ref)
        rows.append({**g, "_ref": ref, "em": pn == ref, "em_nfkc": K(p) == K(g["text"]), "ed": ed,
                     "s": 1 - ed / max(len(ref), len(pn), 1), "missing": g["key"] not in pred})
    L = lambda g: "1-4" if g["n_chars"] <= 4 else "5-16" if g["n_chars"] <= 16 else "17-32" if g["n_chars"] <= 32 else ">32"
    sections = {"all": lambda g: True, "new": lambda g: g.get("origin") == "new", "v12_kept": lambda g: g.get("origin") == "v1.2",
                "hard": lambda g: g["gold_hard"], "gold": lambda g: g["gold"], "printed": lambda g: g["printed"],
                "non_printed": lambda g: g["non_printed"], "gold_random_audit": lambda g: g["gold_random_audit"]}
    for b in ("1-4", "5-16", "17-32", ">32"): sections[f"len_{b}"] = (lambda b: lambda g: L(g) == b)(b)
    for o in ("vertical", "horizontal", "square"): sections[f"orient_{o}"] = (lambda o: lambda g: g["orientation"] == o)(o)
    for r, nm in (("d", "dialogue"), ("n", "narration"), ("o", "other"), ("s", "sfx")): sections[f"role_{nm}"] = (lambda r: lambda g: g["role"] == r)(r)
    res = {"n_pred": len(pred), "missing": sum(r["missing"] for r in rows), "normalization": POLICY_RIN, "sections": {}}
    for s, f in sections.items():
        S = [r for r in rows if f(r)]; n = len(S)
        if not n: continue
        k = sum(r["em"] for r in S); chars = sum(len(r["_ref"]) for r in S)
        res["sections"][s] = {"n": n, "NED_score": round(100 * sum(r["s"] for r in S) / n, 2), "EM": round(100 * k / n, 2), "EM_95ci": wilson(k, n),
                              "CER": round(100 * sum(r["ed"] for r in S) / chars, 2) if chars else None,
                              "EM_NFKC": round(100 * sum(r["em_nfkc"] for r in S) / n, 2)}
    ned = lambda f: 100 * sum(r["s"] for r in rows if f(r)) / max(1, sum(1 for r in rows if f(r)))
    res["composite"] = round((ned(lambda r: r["printed"]) + ned(lambda r: r["non_printed"])) / 2, 2)
    return res, rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pred", required=True); ap.add_argument("--gt", default=str(B.parent / "data" / "gt.jsonl"))
    ap.add_argument("--name", default=None); ap.add_argument("--out", default=None); a = ap.parse_args()
    gt = [json.loads(l) for l in open(a.gt, encoding="utf-8")]
    pred = {}
    for l in open(a.pred, encoding="utf-8"):
        if l.strip(): r = json.loads(l); pred[r["key"]] = r.get("pred") or ""
    res, rows = score(pred, gt); res = {"model": a.name, **res}
    print(f"composite {res['composite']}")
    print(f"{'section':22s} {'n':>5s} {'1-NED':>7s} {'EM%':>7s} {'95%CI':>15s} {'CER%':>7s} {'EM_NFKC%':>9s}")
    for s, v in res["sections"].items(): print(f"{s:22s} {v['n']:5d} {v['NED_score']!s:>7s} {v['EM']!s:>7s} {str(v['EM_95ci']):>15s} {v['CER']!s:>7s} {v['EM_NFKC']!s:>9s}")
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
        Path(a.out).with_suffix(".per_item.jsonl").write_text("".join(json.dumps({"key": r["key"], "pred": pred.get(r["key"], ""), "em": r["em"], "ed": r["ed"], "s": round(r["s"], 6)}, ensure_ascii=False) + "\n" for r in rows))

if __name__ == "__main__": main()
