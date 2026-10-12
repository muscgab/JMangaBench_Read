"""Read v1.3 max-throughput test (user 2026-10-11, AutoDL RTX 3060, CPU quota 7 cores): python speed2.py MODEL [--check N]
Same method as the 2026-10-03 speed2: CPU preprocessing (each model's own) in a fork pool ahead of the GPU, batch search
(coarse doubling to OOM or two drops, then fine [B/2,2B] step B/4, 3 reps median) on a fixed 512-crop subset (seed 0);
per point: throughput, peak memory, GPU utilisation, per full-batch latency, prep_wait_frac, agreement with batch=1.
Workers 4 + main 3 threads (container quota 7 cores). --check N: first N crops' prep+infer bs=1 output must equal preds/MODEL.jsonl.
Result results/MODEL_speed2.json."""
# sailgpu2 fp16 rerun (user 2026-10-12: "你就在这台sailgpu上面测试，每一个gpu测试一个，可以并行来跑；都跑fp16先看能不能跑"):
# copy of v13_20261011/remote/*; ROOT from env BENCH_ROOT (default /home/clx/bench_v13); BENCH_FP16=1 (default) casts the
# rival models to fp16 (10-11: Hayai/mangaOCR fp32, baberu bf16); e4 stays fp16 autocast; new n4_L1 = formal_fp32_N4 final,
# fp16-reparametrised (fp16_20261012/fp16_convert.reparam, k=[1,1,16,1], c=1/4, eps*c^2), fp16 autocast.
import argparse, json, os, random, subprocess, sys, threading, time
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com"); os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from pathlib import Path
import multiprocessing as mp
import numpy as np
import torch
from PIL import Image

ROOT = Path(os.environ.get("BENCH_ROOT", "/home/clx/bench_v13")); BUNDLE = ROOT / "bundle"; MODELS = ROOT / "models"
FP16 = os.environ.get("BENCH_FP16", "1") == "1"
WORKERS, MAIN_THREADS = 4, 3
IMGS, PREP = {}, None

def to_np(d): return {k: (v.numpy() if isinstance(v, torch.Tensor) else v) for k, v in d.items()}
def to_cuda(d): return {k: (torch.from_numpy(v).cuda(non_blocking=True) if isinstance(v, np.ndarray) else v) for k, v in d.items()}

# ---------------- adapters：返回 (build_prep, build_infer)；build_prep 只建 CPU 对象 ----------------
def hayai(sub, patches):
    def f():
        def build_prep():
            from transformers import AutoProcessor
            proc = AutoProcessor.from_pretrained(MODELS / "siglip2_naflex")
            return lambda imgs: to_np(dict(proc(images=[i.convert("RGB") for i in imgs], max_num_patches=patches, return_tensors="pt")))
        def build_infer():
            from transformers import AutoModel, PreTrainedTokenizerFast
            model = AutoModel.from_pretrained(MODELS / sub, trust_remote_code=True).cuda().eval()
            if FP16: model = model.half()
            tok = PreTrainedTokenizerFast.from_pretrained(MODELS / sub)
            @torch.inference_mode()
            def infer(x):
                x = to_cuda(x)
                if FP16: x["pixel_values"] = x["pixel_values"].half()
                return list(model.generate(pixel_values=x["pixel_values"], pixel_attention_mask=x["pixel_attention_mask"], spatial_shapes=x["spatial_shapes"],
                                           tokenizer=tok, max_new_tokens=128, repetition_penalty=1.0))
            return infer
        return build_prep, build_infer
    return f

def baberu():
    d = MODELS / "baberu"; sys.path.insert(0, str(d))
    def make_proc():
        from transformers import AutoImageProcessor
        return AutoImageProcessor.from_pretrained(MODELS / "dinov2_base", do_center_crop=False, size={"height": 224, "width": 224}, crop_size=None)
    def build_prep():
        proc = make_proc()
        return lambda imgs: to_np(dict(proc([i.convert("RGB") for i in imgs], return_tensors="pt")))
    def build_infer():
        import inference as bi
        from transformers import LogitsProcessorList
        bi.build_ocr_image_processor = lambda name="": make_proc()
        ocr = bi.BaberuOCR(d, device="cuda")
        if FP16: ocr.model.half()
        dt = next(ocr.model.parameters()).dtype
        @torch.inference_mode()
        def infer(x):
            pv = torch.from_numpy(x["pixel_values"]).to(ocr.device, dt)
            ids = torch.full((pv.shape[0], 1), ocr.tok.bos_token_id, device=ocr.device)
            out = ocr.model.generate(input_ids=ids, pixel_values=pv, max_new_tokens=128, do_sample=False, repetition_penalty=1.2,
                                     logits_processor=LogitsProcessorList([bi.CapContentRun(ocr._content_ids, 12)]),
                                     eos_token_id=ocr.tok.eos_token_id, pad_token_id=ocr.tok.pad_token_id, bos_token_id=ocr.tok.bos_token_id, use_cache=True)
            return [ocr.tok.decode(r[1:].cpu().tolist(), skip_special_tokens=True) for r in out]
        return infer
    return build_prep, build_infer

def manga_ocr():
    d = MODELS / "manga_ocr"
    def build_prep():
        from transformers import ViTImageProcessor
        proc = ViTImageProcessor.from_pretrained(d)
        return lambda imgs: {"pixel_values": proc([i.convert("L").convert("RGB") for i in imgs], return_tensors="pt").pixel_values.numpy()}
    def build_infer():
        from manga_ocr.ocr import post_process
        from transformers import AutoTokenizer, VisionEncoderDecoderModel
        import transformers.modeling_utils as _mu; _mu.check_torch_load_is_safe = lambda: None  # official kha-white pytorch_model.bin; transformers 4.57 refuses torch.load on torch<2.6 (CVE-2025-32434); still weights_only=True
        tok = AutoTokenizer.from_pretrained(d); model = VisionEncoderDecoderModel.from_pretrained(d).cuda().eval()
        if FP16: model = model.half()
        @torch.inference_mode()
        def infer(x):
            pv = torch.from_numpy(x["pixel_values"]).cuda()
            out = model.generate(pv.half() if FP16 else pv, max_length=300)
            return [post_process(tok.decode(r, skip_special_tokens=True)) for r in out.cpu()]
        return infer
    return build_prep, build_infer

def e4(loops):
    def f():
        import e4_adapter as EA
        def build_infer():
            inf = EA.build(loops); return inf
        return (lambda: EA.prep), build_infer
    return f

def preview():
    """Preview release (2026-10-12 23:xx), precision PREVIEW_PREC (default fp16; fp16 == fp32 on 260/260 crops)."""
    d = MODELS / "preview"; sys.path.insert(0, str(d))
    def build_prep():
        from manga_ocr_nar.model import make_image_processor
        c = json.loads((d / "model_manifest.json").read_text(encoding="utf-8"))["contract"]
        proc = make_image_processor(min_pixels=int(c["image_min_pixels"]), max_pixels=int(c["image_max_pixels"]))
        return lambda imgs: to_np(dict(proc(images=[i.convert("RGB") for i in imgs], return_tensors="pt")))
    def build_infer():
        from manga_ocr_nar.inference import MangaOCRNar
        from manga_ocr_nar.model import EOS_ID
        m = MangaOCRNar(d, device="cuda", precision=os.environ.get("PREVIEW_PREC", "fp16"))
        @torch.inference_mode()
        def infer(x):
            logits = m.runner(torch.from_numpy(x["pixel_values"]).to(device=m.device, dtype=m.dtype), torch.from_numpy(x["image_grid_thw"]))["logits"]
            out = []
            for ids in logits.argmax(-1).cpu().tolist():
                if EOS_ID in ids: ids = ids[: ids.index(EOS_ID)]
                out.append("".join(m.characters[i] for i in ids if 0 <= i < EOS_ID))
            return out
        return infer
    return build_prep, build_infer

def paddle():
    """PaddleOCR-VL-For-Manga, fixed batch path (paddle_batch.py); PYTHONPATH with transformers 4.55.4, PADDLE_DIR, PADDLE_DTYPE."""
    import paddle_batch as PB
    def build_prep():
        return lambda imgs: to_np(PB.prep([i.convert("RGB") for i in imgs]))
    def build_infer():
        infer = PB.load()
        return lambda x: infer({k: (torch.from_numpy(v) if isinstance(v, np.ndarray) else v) for k, v in x.items()})
    return build_prep, build_infer

def looped(loops):  # LoopNAR-α (looped_v1), see looped_adapter.py
    def f():
        import looped_adapter as LA
        return (lambda: LA.prep), (lambda: LA.build(loops, os.environ.get("LOOPNAR_DTYPE", "fp16")))
    return f

def n4():
    import e4_adapter as EA
    return (lambda: EA.prep), EA.build_n4

def n4g():
    import e4_adapter as EA
    return (lambda: EA.prep), EA.build_n4_graph

def n4p():  # release decoupled path: CPU prep = decode to uint8 only, everything else on the GPU
    import e4_adapter as EA
    return (lambda: (lambda imgs: [np.asarray(i.convert("RGB")) for i in imgs])), EA.build_n4_pipe

ADAPTERS = {"n4p_L1": n4p, "n4g_L1": n4g, "n4_L1": n4, "e4_L1": e4(1), "e4_L2": e4(2), "e4_L3": e4(3), "hayai_v2": hayai("hayai_v2", 256), "hayai_nova_p256": hayai("hayai_nova", 256),
            "hayai_nova_p384": hayai("hayai_nova", 384), "hayai_nova_p512": hayai("hayai_nova", 512), "baberu": baberu, "manga_ocr": manga_ocr,
            "preview": preview, "paddleocr_vl_manga": paddle,
            "loopnar_a_L1": looped(1), "loopnar_a_L2": looped(2), "loopnar_a_L3": looped(3)}

def _worker_init():
    torch.set_num_threads(1)
def _prep_keys(keys):
    return PREP([IMGS[k] for k in keys])

class GpuUtil:
    def __enter__(self):
        self.p = subprocess.Popen(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits", "-lms", "200"], stdout=subprocess.PIPE, text=True)
        self.vals = []; self.t = threading.Thread(target=lambda: [self.vals.append(int(l)) for l in self.p.stdout if l.strip().isdigit()], daemon=True); self.t.start(); return self
    def __exit__(self, *a):
        self.p.terminate(); self.p.wait(); self.t.join(timeout=2)
    @property
    def mean(self): return round(sum(self.vals) / len(self.vals), 1) if self.vals else None

def main():
    global PREP
    ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--check", type=int, default=64); a = ap.parse_args()
    gt = [json.loads(l) for l in open(BUNDLE / "gt.jsonl")]
    keys = sorted(random.Random(0).sample([g["key"] for g in gt], 512))
    need = set(keys) | {g["key"] for g in gt[: a.check]}
    for g in gt:
        if g["key"] in need:
            with Image.open(BUNDLE / g["file"]) as im: im.load(); IMGS[g["key"]] = im.copy()
    build_prep, build_infer = ADAPTERS[a.model]()
    PREP = build_prep()
    pool = mp.get_context("fork").Pool(WORKERS, initializer=_worker_init)  # 在加载 GPU 模型之前 fork
    torch.set_num_threads(MAIN_THREADS)
    infer = build_infer()
    sync = torch.cuda.synchronize

    # 1) 拆分正确性：bs=1 输出与 run_eval 的 preds 一致
    preds = {json.loads(l)["key"]: json.loads(l)["pred"] for l in open(ROOT / "preds" / f"{a.model}.jsonl")}
    chk = [g["key"] for g in gt[: a.check]]
    got = {k: infer(PREP([IMGS[k]]))[0] for k in chk}
    match = sum(got[k] == preds[k] for k in chk) / len(chk); print(a.model, "split check vs preds:", match, flush=True)

    ref = {k: infer(PREP([IMGS[k]]))[0] for k in keys}  # batch=1 参考

    def once(bs):
        batches = [keys[i:i + bs] for i in range(0, len(keys), bs)]
        infer(PREP([IMGS[k] for k in batches[0]]))  # 预热
        sync(); torch.cuda.reset_peak_memory_stats(); outs = {}; bt = []; wait = 0.0
        with GpuUtil() as u:
            t = time.perf_counter(); last = t
            for b, x in zip(batches, pool.imap(_prep_keys, batches)):
                t0 = time.perf_counter(); wait += t0 - last  # 等预处理的时间
                for k, p in zip(b, infer(x)): outs[k] = p
                sync(); last = time.perf_counter()
                if len(b) == bs: bt.append(last - t0)  # 只记满 batch 的推理耗时
            dt = last - t
        return {"ips": len(keys) / dt, "alloc": torch.cuda.max_memory_allocated() / 2**20, "reserved": torch.cuda.max_memory_reserved() / 2**20,
                "agree": sum(outs[k] == ref[k] for k in keys) / len(keys), "util": u.mean, "bt": bt, "wait_frac": wait / dt}

    def measure(bs, reps):
        runs = []
        try:
            for _ in range(reps): runs.append(once(bs))
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache(); return {"batch": bs, "oom": True}
        ips = sorted(r["ips"] for r in runs)
        bt = sorted(x for r in runs for x in r["bt"]); q = lambda p: round(1000 * bt[min(len(bt) - 1, int(p * len(bt)))], 2) if bt else None
        return {"batch": bs, "imgs_per_sec": round(ips[len(ips) // 2], 2), "imgs_per_sec_runs": [round(x, 2) for x in ips], "reps": reps,
                "batch_ms_p50": q(.5), "batch_ms_p90": q(.9), "batch_ms_max": q(1.0), "n_full_batches": len(bt),
                "prep_wait_frac": round(sum(r["wait_frac"] for r in runs) / len(runs), 3),
                "peak_alloc_mb": round(max(r["alloc"] for r in runs)), "peak_reserved_mb": round(max(r["reserved"] for r in runs)),
                "gpu_util_mean": round(sum(r["util"] or 0 for r in runs) / len(runs), 1), "agree_with_bs1": round(min(r["agree"] for r in runs), 4)}

    pts = {}; oom_at = None; bs = 1; down = 0; best = None
    while bs <= 512:
        r = measure(bs, 1); pts[bs] = r; print(a.model, "coarse", r, flush=True)
        if r.get("oom"): oom_at = bs; break
        if best is None or r["imgs_per_sec"] > pts[best]["imgs_per_sec"]: best, down = bs, 0
        else:
            down += 1
            if down >= 2: break
        bs *= 2
    step = max(1, best // 4); lo = max(1, best // 2); hi = min(best * 2, (oom_at - 1) if oom_at else 512)
    for b in sorted({best, *range(lo, hi + 1, step)}):
        if oom_at and b >= oom_at: continue
        r = measure(b, 3); pts[b] = r; print(a.model, "fine", r, flush=True)
        if r.get("oom"): oom_at = b if not oom_at else min(oom_at, b)
    pool.close(); pool.join()
    ok = {b: r for b, r in pts.items() if not r.get("oom")}
    top = max(ok.values(), key=lambda r: r["imgs_per_sec"])
    res = {"model": a.model, "subset": 512, "split_check_vs_preds": match, "workers": WORKERS, "main_threads": MAIN_THREADS,
           "method": "parallel CPU prep (fork pool) + GPU infer; coarse doubling + fine [B/2,2B] step B/4, 3 reps median",
           "points": [pts[b] for b in sorted(pts)], "best": top, "plateau_within_3pct": sorted(b for b, r in ok.items() if r["imgs_per_sec"] >= 0.97 * top["imgs_per_sec"]),
           "oom_at": oom_at, "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__}
    (ROOT / "results" / f"{a.model}_speed2.json").write_text(json.dumps(res, indent=1)); print("BEST", a.model, top, flush=True)

if __name__ == "__main__":
    main()
