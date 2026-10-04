"""吞吐测试 v2（2026-10-03 用户同意）：预处理与 GPU 推理并行，batch 两段搜索取最大吞吐。
用法：python speed2.py MODEL [--check N]
- 每个模型拆成 prep（CPU：各模型自带的预处理，返回 numpy）与 infer（GPU 推理 + 解码）。
- 预处理由 fork 出的 WORKERS 个进程（各 1 线程）提前做；主进程 torch 线程数 MAIN_THREADS；合计不超过容器 10 核。
  进程池在加载 GPU 模型之前创建（子进程不碰 CUDA），整个模型测试期间复用，不把启动开销算进吞吐。
- 搜索同 run_eval：粗搜翻倍至 OOM 或连续两档下降 → 细搜 [B/2,2B] 步长 B/4，B 与细搜点 3 次取中位数；
  每点记录吞吐、峰值显存（allocated/reserved）、GPU 利用率均值（nvidia-smi 200 ms 采样）、与 batch=1 输出一致率；
  每个满 batch 的推理耗时（含解码，p50/p90/max，末尾不满的 batch 不计）；主循环等预处理的时间占比 prep_wait_frac（>0 说明 CPU 跟不上）。
- --check N：先用前 N 张核对 prep+infer 的 batch=1 输出与 preds/MODEL.jsonl 完全一致（保证拆分没改变模型行为）。
结果 results/MODEL_speed2.json。"""
import argparse, json, os, random, subprocess, sys, threading, time
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com"); os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
from pathlib import Path
import multiprocessing as mp
import numpy as np
import torch
from PIL import Image

ROOT = Path("/root/autodl-tmp/eval_v1"); BUNDLE = ROOT / "v1_eval_bundle"; MODELS = ROOT / "models"
WORKERS, MAIN_THREADS = 6, 3
IMGS, PREP = {}, None

def to_np(d): return {k: (v.numpy() if isinstance(v, torch.Tensor) else v) for k, v in d.items()}
def to_cuda(d): return {k: (torch.from_numpy(v).cuda(non_blocking=True) if isinstance(v, np.ndarray) else v) for k, v in d.items()}

# ---------------- adapters：返回 (build_prep, build_infer)；build_prep 只建 CPU 对象 ----------------
def preview():
    d = MODELS / "preview"; sys.path.insert(0, str(d))
    def build_prep():
        from manga_ocr_nar.model import make_image_processor
        c = json.loads((d / "model_manifest.json").read_text())["contract"]
        proc = make_image_processor(min_pixels=int(c["image_min_pixels"]), max_pixels=int(c["image_max_pixels"]))
        return lambda imgs: to_np(dict(proc(images=[i.convert("RGB") for i in imgs], return_tensors="pt")))
    def build_infer():
        from manga_ocr_nar.inference import MangaOCRNar
        from manga_ocr_nar.model import EOS_ID
        m = MangaOCRNar(d, device="cuda", precision="auto")
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

def hayai(sub, patches):
    def f():
        def build_prep():
            from transformers import AutoProcessor
            proc = AutoProcessor.from_pretrained(MODELS / "siglip2_naflex")
            return lambda imgs: to_np(dict(proc(images=[i.convert("RGB") for i in imgs], max_num_patches=patches, return_tensors="pt")))
        def build_infer():
            from transformers import AutoModel, PreTrainedTokenizerFast
            model = AutoModel.from_pretrained(MODELS / sub, trust_remote_code=True).cuda().eval()
            tok = PreTrainedTokenizerFast.from_pretrained(MODELS / sub)
            @torch.inference_mode()
            def infer(x):
                x = to_cuda(x)
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
        @torch.inference_mode()
        def infer(x):
            pv = torch.from_numpy(x["pixel_values"]).to(ocr.device)
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
        tok = AutoTokenizer.from_pretrained(d); model = VisionEncoderDecoderModel.from_pretrained(d).cuda().eval()
        @torch.inference_mode()
        def infer(x):
            out = model.generate(torch.from_numpy(x["pixel_values"]).cuda(), max_length=300)
            return [post_process(tok.decode(r, skip_special_tokens=True)) for r in out.cpu()]
        return infer
    return build_prep, build_infer

def paddle():
    d = MODELS / "paddleocr_vl_manga"
    def make_proc():
        from transformers import AutoProcessor
        p = AutoProcessor.from_pretrained(d, trust_remote_code=True, use_fast=True); p.tokenizer.padding_side = "left"; return p
    def build_prep():
        proc = make_proc()
        def prep(imgs):
            imgs = [i.convert("RGB") for i in imgs]
            msgs = [[{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}] for im in imgs]
            texts = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            return to_np(dict(proc(text=texts, images=[[im] for im in imgs], return_tensors="pt", padding=True)))
        return prep
    def build_infer():
        from transformers import AutoModelForCausalLM
        try:
            import flash_attn  # noqa: F401
            attn = "flash_attention_2"
        except ImportError:
            attn = "sdpa"
        model = AutoModelForCausalLM.from_pretrained(d, trust_remote_code=True, torch_dtype=torch.bfloat16, attn_implementation=attn).cuda().eval()
        proc = make_proc()
        if model.generation_config.pad_token_id is None: model.generation_config.pad_token_id = proc.tokenizer.eos_token_id
        @torch.inference_mode()
        def infer(x):
            x = to_cuda(x)
            g = model.generate(**x, max_new_tokens=512, do_sample=False, use_cache=True)
            return proc.batch_decode(g[:, x["input_ids"].shape[1]:], skip_special_tokens=True)
        return infer
    return build_prep, build_infer

def dreco(sub, module, cls):
    def f():
        d = MODELS / sub
        def build_prep():
            def prep(imgs):
                arr = [np.asarray(i.convert("RGB"))[..., ::-1] for i in imgs]
                H = max(a.shape[0] for a in arr); W = max(a.shape[1] for a in arr)
                batch = np.zeros((len(arr), H, W, 3), dtype=np.uint8)
                for k, a in enumerate(arr): batch[k, : a.shape[0], : a.shape[1]] = a
                return {"images": np.ascontiguousarray(batch.transpose(0, 3, 1, 2)), "sizes": np.array([[a.shape[0], a.shape[1]] for a in arr], dtype=np.int64)}
            return prep
        def build_infer():
            sys.path.insert(0, str(d)); OCR = getattr(__import__(module), cls); ocr = OCR.from_pretrained(device="cuda")
            @torch.inference_mode()
            def infer(x):
                return ocr.decode(ocr.forward_gpu(torch.from_numpy(x["images"]).cuda(), torch.from_numpy(x["sizes"]).cuda()))
            return infer
        return build_prep, build_infer
    return f

def looped(loops, dtype):  # 2026-10-04 补测 looped 试验模型，见 looped_adapter.py
    def f():
        import looped_adapter as LA
        return (lambda: LA.prep), (lambda: LA.build(loops, dtype))
    return f

ADAPTERS = {"preview": preview, "hayai_v2": hayai("hayai_v2", 256), "hayai_nova_p256": hayai("hayai_nova", 256), "hayai_nova_p384": hayai("hayai_nova", 384),
            "hayai_nova_p512": hayai("hayai_nova", 512), "baberu": baberu, "manga_ocr": manga_ocr, "paddleocr_vl_manga": paddle,
            "mangadreco": dreco("mangadreco", "manga_dreco", "MangaDReCo"), "mangadrec": dreco("mangadrec", "manga_drec", "MangaDReC"),
            "looped_L3_fp32": looped(3, "fp32"), "looped_L3_bf16": looped(3, "bf16"), "looped_L1_bf16": looped(1, "bf16")}

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
