"""Resident process: first-crop latency after idle, every model (user 2026-10-12: "普通工况，常驻 + 第一框延迟各个模型的延迟情况",
"选一个小一点的或者是聪明一点的测试方法"). Paired design on the SAME 5 crops for every model (Read v1.3, n_chars == median, file
order), so autoregressive output length cancels:
  startup  process start -> model loaded + 20 warm-up crops (other crops) done
  warm[c]  median of 3 back-to-back calls of crop c with the device busy
  cold[c]  after IDLE s with nothing running (2080 Ti measured 10-12: P2 1350 MHz held <= 15.6 s, then P8 300 MHz) one call of c;
  second[c] the call right after cold[c]
Penalty = cold - warm per crop (median over crops). Models: run_eval.py adapters (fp16; n4g_L1 = accelerated N4, CUDA graphs),
or coreml_ane / coreml_gpu (Mac, deploy/n4_coreml_infer.py). Usage: python first_crop_bench.py MODEL [IDLE] -> results/first_crop_MODEL.json"""
import time
T0 = time.perf_counter()
import json  # noqa: E402
import os  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

NAME = sys.argv[1]
IDLE = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
LOCAL = NAME.startswith("coreml")
if LOCAL:
    V13 = Path("/Users/chenlixing/mangaOCR-NAR/experiments/manga_eval_benchmark/v13_20261011")
    OUT = Path(__file__).resolve().parent / "results_first_crop"
else:
    V13 = Path(os.environ.get("BENCH_ROOT", "/home/clx/bench_v13")) / "bundle"
    OUT = Path(os.environ.get("BENCH_ROOT", "/home/clx/bench_v13")) / "results"
OUT.mkdir(exist_ok=True)

from PIL import Image  # noqa: E402

gt = [json.loads(l) for l in open(V13 / "gt.jsonl", encoding="utf-8")]
med = sorted(g["n_chars"] for g in gt)[len(gt) // 2]
test = [g for g in gt if g["n_chars"] == med][:5]
warmup = [g for g in gt if g["n_chars"] != med][:20]


def load(g):
    with Image.open(V13 / g["file"]) as im:
        im.load(); return im.convert("RGB")


test_im, warm_im = [load(g) for g in test], [load(g) for g in warmup]
T_DATA = time.perf_counter() - T0
T1 = time.perf_counter()
if LOCAL:
    sys.path.insert(0, "/Users/chenlixing/mangaOCR-NAR/experiments/small_nar_design/fp16_20261012/deploy")
    import n4_coreml_infer as RT
    ocr = RT.MangaOcrNar(NAME.split("_")[1])

    def one(im):
        return ocr(im)
    DEV = "Apple M1 Pro " + NAME.split("_")[1]
else:
    sys.path.insert(0, os.environ.get("BENCH_CODE", "/home/clx/bench_v13/code"))
    import torch
    import run_eval as RE
    predict = RE.ADAPTERS[NAME]()

    def one(im):
        out = predict([im])[0]; torch.cuda.synchronize(); return out
    DEV = torch.cuda.get_device_name(0)
for im in warm_im:
    one(im)
startup = time.perf_counter() - T1


def timed(im):
    t = time.perf_counter(); txt = one(im); return 1000 * (time.perf_counter() - t), txt


warm, cold, second, texts = [], [], [], []
for im in test_im:
    for w in warm_im[:5]:                                 # keep the device busy
        one(w)
    warm.append(statistics.median([timed(im)[0] for _ in range(3)]))
for im in test_im:
    time.sleep(IDLE)
    c, txt = timed(im); s, _ = timed(im)
    cold.append(c); second.append(s); texts.append(txt)
pen = [c - w for c, w in zip(cold, warm)]
md = lambda v: round(statistics.median(v), 1)
res = {"model": NAME, "device": DEV, "idle_s": IDLE, "startup_s": round(startup, 2), "data_load_s_excluded": round(T_DATA, 2),
       "crops": [g["key"] for g in test], "n_chars": med, "warm_ms": [round(x, 1) for x in warm], "cold_ms": [round(x, 1) for x in cold],
       "second_ms": [round(x, 1) for x in second], "warm_median": md(warm), "cold_median": md(cold), "second_median": md(second),
       "penalty_median": md(pen), "cold_over_warm": round(statistics.median(cold) / statistics.median(warm), 2), "texts": texts}
(OUT / f"first_crop_{NAME}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in res.items() if k not in ("crops", "texts")}, ensure_ascii=False), flush=True)
