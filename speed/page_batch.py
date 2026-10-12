"""Read v1.3 batch = one page (user 2026-10-11): python page_batch.py MODEL
Read v1.3 keeps at most 6 boxes per page (mean 4.2), fewer than a real page, so as in the v1 page test (2026-10-04) the batch
sizes are the real per-page YOLO box counts of the 1,847 v1.3 pages in the candidate pool (mean 8.60, max 45), shuffled and
cycled over the shuffled 7,789 keys (page_plan.json, seed 20261011; each key exactly once, same plan for every model). Single process, preprocessing inside predict (same adapters as run_eval preds), CUDA sync per page, first 5 pages run
once as warmup (not timed) and then timed in order with all others. Output preds_page/MODEL.jsonl ({key, pred, page_id,
page_n, page_ms}) and results/MODEL_page.json (per-page latency summary)."""
import argparse, collections, json, statistics, time
import torch
import run_eval as RE


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("model"); a = ap.parse_args()
    gt, imgs = RE.load_images()
    plan = list(enumerate(json.load(open(RE.ROOT / "page_plan.json"))["batches"]))
    predict = RE.ADAPTERS[a.model]()
    for _, b in plan[:5]: predict([imgs[k] for k in b])  # warmup
    RE.sync(); torch.cuda.reset_peak_memory_stats()
    rows, per = [], []
    t_all = time.perf_counter()
    for pid, b in plan:
        t = time.perf_counter(); out = predict([imgs[k] for k in b]); RE.sync(); dt = time.perf_counter() - t
        assert len(out) == len(b), (len(out), len(b))
        per.append({"batch": pid, "n": len(b), "ms": round(1000 * dt, 3)})
        rows += [{"key": k, "pred": p, "batch": pid, "page_n": len(b), "page_ms": round(1000 * dt, 3)} for k, p in zip(b, out)]
    total = time.perf_counter() - t_all
    out_dir = RE.ROOT / "preds_page"; out_dir.mkdir(exist_ok=True)
    (out_dir / f"{a.model}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    ms = sorted(p["ms"] for p in per); q = lambda p: ms[min(len(ms) - 1, int(p * len(ms)))]
    res = {"model": a.model, "n_imgs": len(rows), "n_pages": len(per), "batch_size_mean": round(len(rows) / len(per), 2),
           "batch_size_max": max(p["n"] for p in per), "total_sec": round(total, 1), "imgs_per_sec": round(len(rows) / total, 2),
           "page_ms_mean": round(statistics.mean(ms), 2), "page_ms_p50": q(.5), "page_ms_p90": q(.9), "page_ms_p99": q(.99), "page_ms_max": ms[-1],
           "ms_per_img_mean": round(1000 * total / len(rows), 2), "peak_mem_mb": round(torch.cuda.max_memory_allocated() / 2**20),
           "method": "batch sizes = real per-page YOLO box counts (page_plan.json), single process, serial preprocessing inside predict, per-page CUDA sync, 5 warmup pages",
           "gpu": torch.cuda.get_device_name(0), "per_page": per}
    (RE.ROOT / "results" / f"{a.model}_page.json").write_text(json.dumps(res, indent=1))
    print({k: v for k, v in res.items() if k != "per_page"}, flush=True)


if __name__ == "__main__":
    main()
