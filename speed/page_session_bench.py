"""Real use, one page at a time (user 2026-10-12: "真实工况'一次一页'的情况下我们速度大概快多少"). Resident process; pages come from
page_plan.json (per-page box counts = real YOLO counts on Danbooru pages, crops = Read v1.3, seed-shuffled; mean 8.7 boxes), the
same pages for every model. A request = one whole page (crops decoded in memory) -> texts; the model gets the page as one batch
(predict(list)), as in page_batch.py. Reading gaps between pages: 0 s (a chapter in one go), 10 s (fast reading), 30 s (slow
reading); PER pages per gap, different pages per gap, 3 warm-up pages first (not timed).
Models: run_eval.py adapters (fp16; n4b_L1 = release N4, CUDA graphs for buckets 1,2,4,8,16,32,48), or coreml_gpu / coreml_ane
(Mac, deploy/n4_coreml_infer.py, crops one by one). Usage: python page_session_bench.py MODEL [GAPS] [PER]
-> results/page_session_MODEL.json (remote BENCH_ROOT) or results_first_crop/page_session_MODEL.json (Mac)."""
import time
T0 = time.perf_counter()
import json  # noqa: E402
import os  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

NAME = sys.argv[1]
GAPS = [float(x) for x in (sys.argv[2] if len(sys.argv) > 2 else "0,10,30").split(",")]
PER = int(sys.argv[3]) if len(sys.argv) > 3 else 8
LOCAL = NAME.startswith("coreml")  # coreml_gpu / coreml_ane / coremlb_gpu (batched)
HERE = Path(__file__).resolve().parent
if LOCAL:
    V13 = Path("/Users/chenlixing/mangaOCR-NAR/experiments/manga_eval_benchmark/v13_20261011")
    PLAN, OUT = HERE / "page_plan.json", HERE / "results_first_crop"
else:
    ROOT = Path(os.environ.get("BENCH_ROOT", "/home/clx/bench_v13"))
    V13, PLAN, OUT = ROOT / "bundle", ROOT / "page_plan.json", ROOT / "results"
OUT.mkdir(exist_ok=True)

from PIL import Image  # noqa: E402

files = {json.loads(l)["key"]: json.loads(l)["file"] for l in open(V13 / "gt.jsonl", encoding="utf-8")}
plan = json.load(open(PLAN))["batches"][: 3 + PER * len(GAPS)]


def load(k):
    with Image.open(V13 / files[k]) as im:
        im.load(); return im.convert("RGB")


pages = [[load(k) for k in b] for b in plan]
T1 = time.perf_counter()
if LOCAL:
    sys.path.insert(0, "/Users/chenlixing/mangaOCR-NAR/experiments/small_nar_design/fp16_20261012/deploy")
    import n4_coreml_infer as RT
    if NAME.startswith("coremlb"):                      # multifunction CoreML (coreml_batch.py): static b1/2/4/8/16, macOS 15+
        sys.path.insert(0, "/Users/chenlixing/mangaOCR-NAR/experiments/small_nar_design/fp16_20261012")
        import coreml_batch as CB
        mlc = Path(RT.__file__).parent / "n4_coreml_mf_fp16.mlmodelc"
        SIZES = (1, 2, 4, 8, 16)
        fns = {b: CB.BatchModel(mlc, NAME.split("_")[1], [b], f"b{b}") for b in SIZES}
        COST = {1: 14.7, 2: 23.1, 4: 39.6, 8: 71.7, 16: 134.7}   # measured ms per call (M1 Pro GPU, coreml_batch bench 10-12)
        bplan = {0: []}                                    # cheapest bucket sequence for n crops (padding allowed)
        for n in range(1, 49):
            bplan[n] = min(([b] + bplan[max(0, n - b)] for b in SIZES), key=lambda q: sum(COST[x] for x in q))
        for b in SIZES:                                    # first call of each function specialises it (~0.2-0.3 s) -> at startup
            fns[b].predict(b)
        voc = json.loads((Path(RT.__file__).parent / "nar_vocabulary_6817.json").read_text(encoding="utf-8"))["characters"]

        def text(row):
            row = row[: row.index(len(voc))] if len(voc) in row else row
            return "".join(voc[i] for i in row if i < len(voc))

        def page(crops):
            out, i = [], 0
            while i < len(crops):
                for b in bplan[min(len(crops) - i, 48)]:
                    part = crops[i:i + b]
                    if not part:
                        break
                    m = fns[b]
                    for j, im in enumerate(part):
                        RT.preprocess(im, m.crop(b, j))
                    for a in m.slots[b][0].values():        # padding rows repeat the last real crop (outputs dropped)
                        a[len(part):] = a[len(part) - 1]
                    out += [text(r) for r in m.predict(b).tolist()[:len(part)]]
                    i += len(part)
            return out
    else:
        ocr = RT.MangaOcrNar(NAME.split("_")[1])

        def page(crops):
            return [ocr(im) for im in crops]
    DEV = "Apple M1 Pro " + NAME.split("_")[1]
else:
    sys.path.insert(0, os.environ.get("BENCH_CODE", "/home/clx/bench_v13/code"))
    import torch
    import run_eval as RE
    predict = RE.ADAPTERS[NAME]()

    def page(crops):
        out = predict(crops); torch.cuda.synchronize(); return out
    DEV = torch.cuda.get_device_name(0)
for p in pages[:3]:
    page(p)
startup = time.perf_counter() - T1
res, preds, i = [], {}, 3
for gap in GAPS:
    rows = []
    for _ in range(PER):
        time.sleep(gap)
        t = time.perf_counter(); out = page(pages[i]); ms = 1000 * (time.perf_counter() - t)
        rows.append({"boxes": len(pages[i]), "ms": round(ms, 1)})
        preds.update(dict(zip(plan[i], out))); i += 1
    ms = [r["ms"] for r in rows]
    res.append({"gap_s": gap, "pages": rows, "page_ms_median": round(statistics.median(ms), 1), "page_ms_mean": round(statistics.mean(ms), 1),
                "page_ms_max": max(ms), "boxes_total": sum(r["boxes"] for r in rows), "ms_per_box": round(sum(ms) / sum(r["boxes"] for r in rows), 2)})
    print(json.dumps({k: v for k, v in res[-1].items() if k != "pages"}), flush=True)
out = {"model": NAME, "device": DEV, "startup_s": round(startup, 2), "gaps": res, "preds": preds}
(OUT / f"page_session_{NAME}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({"done": NAME, "startup_s": out["startup_s"]}), flush=True)
