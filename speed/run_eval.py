"""v1 评测：python run_eval.py MODEL [--stage preds|speed|all]
preds：全部 3,524 张逐张（batch=1）推理，写 preds/MODEL.jsonl，同时记录每张端到端延迟（图片已在内存，含预处理，CUDA 同步）。
speed：固定 512 张（seed 0），batch 从 1 起倍增，记录吞吐（张/秒）与峰值显存，直到 OOM 或吞吐连续两档下降；
       并把每档 batch 的输出与 batch=1 输出比对，报告一致率（批量 padding 可能改变自回归模型输出）。
精度与生成参数用各模型 README / 官方脚本的默认值，见 ADAPTERS 注释。结果写 results/MODEL_{preds,speed}.json。"""
import argparse, io, json, os, random, statistics, sys, time, traceback
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com"); os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # 远程直连 huggingface.co 不通
from pathlib import Path
import torch
from PIL import Image

ROOT = Path("/root/autodl-tmp/eval_v1"); BUNDLE = ROOT / "v1_eval_bundle"; MODELS = ROOT / "models"
DEV = "cuda"

def sync(): torch.cuda.synchronize()

# ---------------- adapters：load() -> predict(list[PIL.Image]) -> list[str] ----------------
def load_preview():
    d = MODELS / "preview"; sys.path.insert(0, str(d))
    from manga_ocr_nar.inference import MangaOCRNar
    from manga_ocr_nar.model import EOS_ID
    m = MangaOCRNar(d, device="cuda", precision="auto")  # CUDA 默认 bf16
    @torch.inference_mode()
    def predict(imgs):
        enc = m.processor(images=[i.convert("RGB") for i in imgs], return_tensors="pt")
        logits = m.runner(enc["pixel_values"].to(device=m.device, dtype=m.dtype), enc["image_grid_thw"])["logits"]
        out = []
        for ids in logits.argmax(-1).cpu().tolist():
            if EOS_ID in ids: ids = ids[: ids.index(EOS_ID)]
            out.append("".join(m.characters[i] for i in ids if 0 <= i < EOS_ID))
        return out
    return predict

def make_hayai(sub, patches):
    def load():
        from transformers import AutoModel, AutoProcessor, PreTrainedTokenizerFast
        d = MODELS / sub
        model = AutoModel.from_pretrained(d, trust_remote_code=True).cuda().eval()  # README：默认精度（fp32）
        tok = PreTrainedTokenizerFast.from_pretrained(d)
        proc = AutoProcessor.from_pretrained(MODELS / "siglip2_naflex")
        @torch.inference_mode()
        def predict(imgs):
            x = proc(images=[i.convert("RGB") for i in imgs], max_num_patches=patches, return_tensors="pt").to(DEV)
            return list(model.generate(pixel_values=x["pixel_values"], pixel_attention_mask=x["pixel_attention_mask"], spatial_shapes=x["spatial_shapes"],
                                       tokenizer=tok, max_new_tokens=128, repetition_penalty=1.0))
        return predict
    return load

def load_baberu():
    d = MODELS / "baberu"; sys.path.insert(0, str(d))
    import inference as bi
    from transformers import AutoImageProcessor, LogitsProcessorList
    bi.build_ocr_image_processor = lambda name="": AutoImageProcessor.from_pretrained(
        MODELS / "dinov2_base", do_center_crop=False, size={"height": 224, "width": 224}, crop_size=None)
    ocr = bi.BaberuOCR(d, device="cuda")  # CUDA 默认 bf16；生成参数同 README __call__ 默认值
    @torch.inference_mode()
    def predict(imgs):
        pv = ocr.image_processor([i.convert("RGB") for i in imgs], return_tensors="pt")["pixel_values"].to(ocr.device)
        ids = torch.full((len(imgs), 1), ocr.tok.bos_token_id, device=ocr.device)
        lp = LogitsProcessorList([bi.CapContentRun(ocr._content_ids, 12)])
        out = ocr.model.generate(input_ids=ids, pixel_values=pv, max_new_tokens=128, do_sample=False, repetition_penalty=1.2, logits_processor=lp,
                                 eos_token_id=ocr.tok.eos_token_id, pad_token_id=ocr.tok.pad_token_id, bos_token_id=ocr.tok.bos_token_id, use_cache=True)
        return [ocr.tok.decode(r[1:].cpu().tolist(), skip_special_tokens=True) for r in out]
    return predict

def load_manga_ocr():
    from manga_ocr.ocr import post_process
    from transformers import AutoTokenizer, VisionEncoderDecoderModel, ViTImageProcessor
    d = MODELS / "manga_ocr"
    proc = ViTImageProcessor.from_pretrained(d); tok = AutoTokenizer.from_pretrained(d)
    model = VisionEncoderDecoderModel.from_pretrained(d).cuda().eval()  # manga-ocr 包默认 fp32，max_length=300
    @torch.inference_mode()
    def predict(imgs):
        x = proc([i.convert("L").convert("RGB") for i in imgs], return_tensors="pt").pixel_values.cuda()
        out = model.generate(x, max_length=300)
        return [post_process(tok.decode(r, skip_special_tokens=True)) for r in out.cpu()]
    return predict

def load_paddle():
    from transformers import AutoModelForCausalLM, AutoProcessor
    d = MODELS / "paddleocr_vl_manga"
    try:
        import flash_attn  # noqa: F401
        attn = "flash_attention_2"
    except ImportError:
        attn = "sdpa"
    model = AutoModelForCausalLM.from_pretrained(d, trust_remote_code=True, torch_dtype=torch.bfloat16, attn_implementation=attn).cuda().eval()
    proc = AutoProcessor.from_pretrained(d, trust_remote_code=True, use_fast=True)
    proc.tokenizer.padding_side = "left"  # 批量生成用左 padding；准确率以 batch=1 为准
    if model.generation_config.pad_token_id is None: model.generation_config.pad_token_id = proc.tokenizer.eos_token_id
    @torch.inference_mode()
    def predict(imgs):
        imgs = [i.convert("RGB") for i in imgs]
        msgs = [[{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}] for im in imgs]
        texts = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        x = proc(text=texts, images=[[im] for im in imgs], return_tensors="pt", padding=True)
        x = {k: (v.cuda() if isinstance(v, torch.Tensor) else v) for k, v in x.items()}
        g = model.generate(**x, max_new_tokens=512, do_sample=False, use_cache=True)
        return proc.batch_decode(g[:, x["input_ids"].shape[1]:], skip_special_tokens=True)
    predict.attn = attn
    return predict

def make_dreco(sub, module, cls):
    def load():
        import numpy as np
        d = MODELS / sub; sys.path.insert(0, str(d))
        OCR = getattr(__import__(module), cls)
        ocr = OCR.from_pretrained(device="cuda")
        @torch.inference_mode()
        def predict(imgs):
            arr = [np.asarray(i.convert("RGB"))[..., ::-1] for i in imgs]
            H = max(a.shape[0] for a in arr); W = max(a.shape[1] for a in arr)
            batch = np.zeros((len(arr), H, W, 3), dtype=np.uint8)
            for k, a in enumerate(arr): batch[k, : a.shape[0], : a.shape[1]] = a
            x = torch.from_numpy(batch).permute(0, 3, 1, 2).contiguous().cuda()
            sizes = torch.tensor([[a.shape[0], a.shape[1]] for a in arr], device="cuda")
            return ocr.decode(ocr.forward_gpu(x, sizes))
        return predict
    return load

def make_looped(loops, dtype):  # 2026-10-04 补测 looped 试验模型，见 looped_adapter.py
    def load():
        import looped_adapter as LA
        infer = LA.build(loops, dtype)
        return lambda imgs: infer(LA.prep(imgs))
    return load

ADAPTERS = {
    "preview": load_preview,
    "looped_L3_fp32": make_looped(3, "fp32"), "looped_L3_bf16": make_looped(3, "bf16"), "looped_L2_bf16": make_looped(2, "bf16"), "looped_L1_bf16": make_looped(1, "bf16"),
    "hayai_nova_p256": make_hayai("hayai_nova", 256), "hayai_nova_p384": make_hayai("hayai_nova", 384), "hayai_nova_p512": make_hayai("hayai_nova", 512),
    "hayai_v2": make_hayai("hayai_v2", 256),  # README：标准行 256
    "baberu": load_baberu, "manga_ocr": load_manga_ocr, "paddleocr_vl_manga": load_paddle,
    "mangadreco": make_dreco("mangadreco", "manga_dreco", "MangaDReCo"), "mangadrec": make_dreco("mangadrec", "manga_drec", "MangaDReC"),
}

def load_images():
    gt = [json.loads(l) for l in open(BUNDLE / "gt.jsonl")]
    imgs = {}
    for g in gt:
        with Image.open(BUNDLE / g["file"]) as im: im.load(); imgs[g["key"]] = im.copy()
    return gt, imgs

def run_preds(name, predict, gt, imgs):
    out_path = ROOT / "preds" / f"{name}.jsonl"; out_path.parent.mkdir(exist_ok=True)
    for g in gt[:8]: predict([imgs[g["key"]]])  # 预热
    sync(); torch.cuda.reset_peak_memory_stats()
    lat, rows = [], []
    t_all = time.perf_counter()
    for g in gt:
        t = time.perf_counter(); p = predict([imgs[g["key"]]])[0]; sync(); lat.append(time.perf_counter() - t)
        rows.append({"key": g["key"], "pred": p})
    total = time.perf_counter() - t_all
    out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    lat.sort()
    return {"model": name, "n": len(rows), "batch": 1, "total_sec": round(total, 1), "lat_ms_mean": round(1000 * statistics.mean(lat), 2),
            "lat_ms_p50": round(1000 * lat[len(lat) // 2], 2), "lat_ms_p90": round(1000 * lat[int(.9 * len(lat))], 2),
            "imgs_per_sec_bs1": round(len(rows) / total, 2), "peak_mem_mb_bs1": round(torch.cuda.max_memory_allocated() / 2**20)}

def run_speed(name, predict, gt, imgs):
    """两段搜索：粗搜 batch 1,2,4,… 翻倍（单次，至 OOM 或连续两档下降）找到最快档 B；
    细搜 [B/2, 2B] 内步长 max(1, B/4) 补测（不超过 OOM 档），B 与细搜各点重复 3 次取吞吐中位数。
    报告最快 batch、吞吐、峰值显存（allocated / reserved）、与 batch=1 输出一致率，以及吞吐在最高值 3% 以内的 batch 范围。"""
    keys = sorted(random.Random(0).sample([g["key"] for g in gt], 512))
    ref = {k: predict([imgs[k]])[0] for k in keys}  # batch=1 参考输出

    def once(bs):
        batches = [keys[i:i + bs] for i in range(0, len(keys), bs)]
        predict([imgs[k] for k in batches[0]])  # 预热
        sync(); torch.cuda.reset_peak_memory_stats(); t = time.perf_counter(); outs = {}
        for b in batches:
            for k, p in zip(b, predict([imgs[k] for k in b])): outs[k] = p
        sync(); dt = time.perf_counter() - t
        return {"ips": len(keys) / dt, "alloc": torch.cuda.max_memory_allocated() / 2**20, "reserved": torch.cuda.max_memory_reserved() / 2**20,
                "agree": sum(outs[k] == ref[k] for k in keys) / len(keys)}

    def measure(bs, reps):
        runs = []
        try:
            for _ in range(reps): runs.append(once(bs))
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache(); return {"batch": bs, "oom": True}
        ips = sorted(r["ips"] for r in runs)
        return {"batch": bs, "imgs_per_sec": round(ips[len(ips) // 2], 2), "imgs_per_sec_runs": [round(x, 2) for x in ips], "reps": reps,
                "peak_alloc_mb": round(max(r["alloc"] for r in runs)), "peak_reserved_mb": round(max(r["reserved"] for r in runs)),
                "agree_with_bs1": round(min(r["agree"] for r in runs), 4)}

    pts = {}; oom_at = None; bs = 1; down = 0; best = None
    while bs <= 512:  # 粗搜
        r = measure(bs, 1); pts[bs] = r; print(name, "coarse", r, flush=True)
        if r.get("oom"): oom_at = bs; break
        if best is None or r["imgs_per_sec"] > pts[best]["imgs_per_sec"]: best, down = bs, 0
        else:
            down += 1
            if down >= 2: break
        bs *= 2
    step = max(1, best // 4); lo = max(1, best // 2); hi = min(best * 2, (oom_at - 1) if oom_at else 512)
    for b in sorted({best, *range(lo, hi + 1, step)}):  # 细搜（含 B 本身）重复 3 次
        if oom_at and b >= oom_at: continue
        r = measure(b, 3); pts[b] = r; print(name, "fine", r, flush=True)
        if r.get("oom"): oom_at = b if not oom_at else min(oom_at, b)
    ok = {b: r for b, r in pts.items() if not r.get("oom")}
    top = max(ok.values(), key=lambda r: r["imgs_per_sec"])
    plateau = sorted(b for b, r in ok.items() if r["imgs_per_sec"] >= 0.97 * top["imgs_per_sec"])
    return {"model": name, "subset": 512, "method": "coarse doubling + fine search in [B/2,2B] step B/4, 3 reps median",
            "points": [pts[b] for b in sorted(pts)], "best": top, "plateau_within_3pct": plateau, "oom_at": oom_at,
            "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--stage", default="all", choices=["preds", "speed", "all", "smoke"]); a = ap.parse_args()
    (ROOT / "results").mkdir(exist_ok=True)
    gt, imgs = load_images()
    predict = ADAPTERS[a.model]()
    meta = {"attn": getattr(predict, "attn", None)}
    if a.stage == "smoke":
        sys.path.insert(0, str(BUNDLE / "normalize")); from normalization_r7 import normalize_r7 as N
        sub = gt[:16]; t = time.perf_counter(); preds = [predict([imgs[g["key"]]])[0] for g in sub]; sync()
        ok = sum(N(p) == g["text_r7"] for p, g in zip(preds, sub))
        for p, g in list(zip(preds, sub))[:6]: print(repr(g["text"]), "->", repr(p))
        print(f"SMOKE {a.model}: EM {ok}/16, {1000 * (time.perf_counter() - t) / 16:.1f} ms/img, mem {torch.cuda.max_memory_allocated() / 2**20:.0f} MB", flush=True); return
    if a.stage in ("preds", "all"):
        r = run_preds(a.model, predict, gt, imgs) | meta; print(r, flush=True)
        (ROOT / "results" / f"{a.model}_preds.json").write_text(json.dumps(r, indent=1))
    if a.stage == "speed":  # 2026-10-03 23:5x：本轮 run_all 的 all 只跑 preds，吞吐改用并行预处理新方法（speed2）统一重测
        r = run_speed(a.model, predict, gt, imgs) | meta
        (ROOT / "results" / f"{a.model}_speed.json").write_text(json.dumps(r, indent=1))

if __name__ == "__main__":
    main()
