"""整页变 batch 测试（2026-10-04 用户同意）：python page_batch.py MODEL
v1.1 的 3,522 张裁图按固定计划 pagebatch_plan.json 分批（batch 大小取自 v1 那 739 页在候选池里的真实每页框数，打乱循环；
跨页混合，所有模型同一计划）。单进程、预处理串行（直接用 run_eval 的 predict，与逐张评测同一套适配），逐批计时（CUDA 同步），
先用前 5 批预热。输出 preds_pagebatch/MODEL.jsonl（逐张预测，供打分与 bs=1 对比）与 results/MODEL_pagebatch.json（逐批耗时与汇总）。"""
import argparse, json, statistics, time
from pathlib import Path

import torch

import run_eval as RE


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("model"); a = ap.parse_args()
    gt, imgs = RE.load_images()
    plan = json.load(open(RE.ROOT / "pagebatch_plan.json"))["batches"]
    predict = RE.ADAPTERS[a.model]()
    for b in plan[:5]: predict([imgs[k] for k in b])  # 预热
    RE.sync(); torch.cuda.reset_peak_memory_stats()
    rows, per = [], []
    t_all = time.perf_counter()
    for b in plan:
        t = time.perf_counter(); out = predict([imgs[k] for k in b]); RE.sync(); dt = time.perf_counter() - t
        assert len(out) == len(b), (len(out), len(b))
        per.append({"n": len(b), "ms": round(1000 * dt, 2)})
        rows += [{"key": k, "pred": p} for k, p in zip(b, out)]
    total = time.perf_counter() - t_all
    out_dir = RE.ROOT / "preds_pagebatch"; out_dir.mkdir(exist_ok=True)
    (out_dir / f"{a.model}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    ms = sorted(p["ms"] for p in per)
    res = {"model": a.model, "n_imgs": len(rows), "n_batches": len(per), "total_sec": round(total, 1), "imgs_per_sec": round(len(rows) / total, 2),
           "batch_ms_mean": round(statistics.mean(ms), 2), "batch_ms_p50": ms[len(ms) // 2], "batch_ms_p90": ms[int(.9 * len(ms))], "batch_ms_max": ms[-1],
           "ms_per_img_mean": round(1000 * total / len(rows), 2), "peak_mem_mb": round(torch.cuda.max_memory_allocated() / 2**20),
           "method": "single process, serial preprocessing inside predict (same adapters as run_eval preds), per-batch CUDA sync, 5 warmup batches",
           "per_batch": per}
    (RE.ROOT / "results" / f"{a.model}_pagebatch.json").write_text(json.dumps(res, indent=1))
    print({k: v for k, v in res.items() if k != "per_batch"}, flush=True)


if __name__ == "__main__":
    main()
