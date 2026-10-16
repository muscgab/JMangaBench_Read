"""Read v1.3 benchmark (user 2026-10-11, AutoDL RTX 3060): python run_eval.py MODEL [--stage preds|smoke]
preds: all 7,789 crops one by one (batch=1); every row stores its own end-to-end latency lat_ms (image already decoded in
memory; includes the model's preprocessing, inference and decoding; CUDA synchronised before the clock stops); 20 warmup
crops are not timed. Adapters / precision / generation settings are the 2026-10-03 v1 ones (README defaults), plus e4
(e4_adapter.py, fp16, loops 1/2/3). Results: preds/MODEL.jsonl ({key, pred, lat_ms}), results/MODEL_preds.json."""
# sailgpu2 fp16 rerun (user 2026-10-12: "你就在这台sailgpu上面测试，每一个gpu测试一个，可以并行来跑；都跑fp16先看能不能跑"):
# copy of v13_20261011/remote/*; ROOT from env BENCH_ROOT (default /home/clx/bench_v13); BENCH_FP16=1 (default) casts the
# rival models to fp16 (10-11: Hayai/mangaOCR fp32, baberu bf16); e4 stays fp16 autocast; new n4_L1 = formal_fp32_N4 final,
# fp16-reparametrised (fp16_20261012/fp16_convert.reparam, k=[1,1,16,1], c=1/4, eps*c^2), fp16 autocast.
import argparse, io, json, os, random, statistics, sys, time, traceback
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com"); os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # 远程直连 huggingface.co 不通
from pathlib import Path
import torch
from PIL import Image

ROOT = Path(os.environ.get("BENCH_ROOT", "/home/clx/bench_v13")); BUNDLE = ROOT / "bundle"; MODELS = ROOT / "models"
FP16 = os.environ.get("BENCH_FP16", "1") == "1"
torch.set_num_threads(int(os.environ.get("BENCH_THREADS", "8")))  # 16:55 rerun: uncapped threads x 4 processes overloaded the 40 cores (load ~80)
DEV = "cuda"

def sync(): torch.cuda.synchronize()

# ---------------- adapters：load() -> predict(list[PIL.Image]) -> list[str] ----------------
def make_hayai(sub, patches):
    def load():
        from transformers import AutoModel, AutoProcessor, PreTrainedTokenizerFast
        d = MODELS / sub
        model = AutoModel.from_pretrained(d, trust_remote_code=True).cuda().eval()  # README：默认精度（fp32）
        if FP16: model = model.half()
        tok = PreTrainedTokenizerFast.from_pretrained(d)
        proc = AutoProcessor.from_pretrained(MODELS / "siglip2_naflex")
        @torch.inference_mode()
        def predict(imgs):
            x = proc(images=[i.convert("RGB") for i in imgs], max_num_patches=patches, return_tensors="pt").to(DEV)
            if FP16: x["pixel_values"] = x["pixel_values"].half()
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
    if FP16: ocr.model.half()
    dt = next(ocr.model.parameters()).dtype
    @torch.inference_mode()
    def predict(imgs):
        pv = ocr.image_processor([i.convert("RGB") for i in imgs], return_tensors="pt")["pixel_values"].to(ocr.device, dt)
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
    import transformers.modeling_utils as _mu; _mu.check_torch_load_is_safe = lambda: None  # official kha-white pytorch_model.bin; transformers 4.57 refuses torch.load on torch<2.6 (CVE-2025-32434); still weights_only=True
    model = VisionEncoderDecoderModel.from_pretrained(d).cuda().eval()  # manga-ocr 包默认 fp32，max_length=300
    if FP16: model = model.half()
    @torch.inference_mode()
    def predict(imgs):
        x = proc([i.convert("L").convert("RGB") for i in imgs], return_tensors="pt").pixel_values.cuda()
        if FP16: x = x.half()
        out = model.generate(x, max_length=300)
        return [post_process(tok.decode(r, skip_special_tokens=True)) for r in out.cpu()]
    return predict

def make_n4():
    def load():
        import e4_adapter as EA
        infer = EA.build_n4()
        return lambda imgs: infer(EA.prep(imgs))
    return load

def make_n4g():
    def load():
        import e4_adapter as EA
        infer = EA.build_n4_graph()
        print("n4g capture sec (batch: s):", infer.capture_sec, flush=True)
        return lambda imgs: infer(EA.prep(imgs))
    return load

def make_n4b():
    """release default (user 2026-10-12 22:2x): CUDA graphs for batch sizes 1..16 (exact) plus buckets 32 and 48; larger pages padded up"""
    def load():
        import e4_adapter as EA
        infer = EA.build_n4_graph(buckets=tuple(range(1, 17)) + (32, 48))
        print("n4b capture sec (bucket: s):", infer.capture_sec, flush=True)
        return lambda imgs: infer(EA.prep(imgs))
    return load

def make_n4p():
    """release CUDA path = decoupled pipeline (e4_adapter.build_n4_pipe; user 2026-10-12 23:0x)"""
    def load():
        import e4_adapter as EA
        return EA.build_n4_pipe()
    return load

def load_preview():
    """Preview release (user 2026-10-12 23:xx: run Preview on Read v1.3). CUDA default would be bf16 (emulated on the 2080 Ti);
    precision from PREVIEW_PREC (default fp16). Batched exactly as the v1 adapter (processor -> runner logits -> argmax to EOS)."""
    d = MODELS / "preview"; sys.path.insert(0, str(d))
    from manga_ocr_nar.inference import MangaOCRNar
    from manga_ocr_nar.model import EOS_ID
    m = MangaOCRNar(d, device="cuda", precision=os.environ.get("PREVIEW_PREC", "fp16"))
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

def load_paddle():
    """PaddleOCR-VL-For-Manga with the fixed batch path (paddle_batch.py, per-image vision attention); needs PYTHONPATH with
    transformers 4.55.4 (/home/clx/bench_v13/paddle/tf455), PADDLE_DIR, PADDLE_DTYPE."""
    import paddle_batch as PB
    infer = PB.load(); mb = int(os.environ.get("PADDLE_MAXB", "16"))   # a 45-crop page in one batch OOMs on 11 GB -> chunks of <= 16
    def run(chunk):                                                    # a chunk of 16 with one huge crop still OOMs (lm_head
        try:                                                           # 8.78 GiB, 10-12 22:1x) -> halve that chunk and retry
            return infer(PB.prep(chunk))
        except torch.OutOfMemoryError:
            if len(chunk) == 1: raise
            torch.cuda.empty_cache(); h = len(chunk) // 2
            return run(chunk[:h]) + run(chunk[h:])
    def predict(imgs):
        imgs = [i.convert("RGB") for i in imgs]
        return [t for j in range(0, len(imgs), mb) for t in run(imgs[j:j + mb])]
    return predict

def make_looped(loops):
    """LoopNAR-α (looped_v1, Read v1.2 table) on Read v1.3 (user 2026-10-12 23:xx); precision LOOPNAR_DTYPE (default fp16)."""
    def load():
        import looped_adapter as LA
        infer = LA.build(loops, os.environ.get("LOOPNAR_DTYPE", "fp16"))
        return lambda imgs: infer(LA.prep(imgs))
    return load

def make_e4(loops):
    def load():
        import e4_adapter as EA
        infer = EA.build(loops)
        return lambda imgs: infer(EA.prep(imgs))
    return load

def make_cpt(turbo):
    """manga-ocr-base-CPT (mangaOCR after continued pre-training, mocr_ct3 final; user 2026-10-14): release package as shipped,
    MODELS/manga-ocr-base-CPT-turbo (CUDA graphs for batch 1-16/24/32/48 + GPU preprocessing) or MODELS/manga-ocr-base-CPT (plain
    PyTorch, batches of <= 16). Encoder fp16 matmuls / decoder fp32 (= training-time evaluation; the package default)."""
    def load():
        import numpy as np
        d = MODELS / ("manga-ocr-base-CPT-turbo" if turbo else "manga-ocr-base-CPT")
        sys.path.insert(0, str(d))
        if turbo:
            from manga_ocr_base_cpt_turbo import MangaOcrBaseCPTTurbo
            ocr = MangaOcrBaseCPTTurbo("cuda", "fp32", d)
            return lambda imgs: ocr([np.asarray(i.convert("RGB")) for i in imgs])
        from manga_ocr_base_cpt import MangaOcrBaseCPT
        ocr = MangaOcrBaseCPT("cuda", d)
        return lambda imgs: ocr(list(imgs))
    return load

def make_nars(name):
    """manga-ocr-nar package 1.1.0 as released (2026-10-16), CUDA backend: MODELS/<name> = a downloaded model repository
    (manga-ocr-nar-small-distil: fp16 with simulated int8, CUDA graphs for batch 1-16/32/48 + GPU preprocessing)."""
    def load():
        import numpy as np
        d = MODELS / name
        sys.path.insert(0, str(d))
        from manga_ocr_nar_small import MangaOcrNarSmall
        ocr = MangaOcrNarSmall("cuda", model_dir=d)
        return lambda imgs: ocr([np.asarray(i.convert("RGB")) for i in imgs])
    return load

ADAPTERS = {
    "nars_distil_rel": make_nars("manga-ocr-nar-small-distil"),
    "cpt_turbo": make_cpt(True), "cpt_plain": make_cpt(False),
    "n4_L1": make_n4(), "n4g_L1": make_n4g(), "n4b_L1": make_n4b(), "n4p_L1": make_n4p(), "e4_L1": make_e4(1), "e4_L2": make_e4(2), "e4_L3": make_e4(3),
    "hayai_nova_p256": make_hayai("hayai_nova", 256), "hayai_nova_p384": make_hayai("hayai_nova", 384), "hayai_nova_p512": make_hayai("hayai_nova", 512),
    "hayai_v2": make_hayai("hayai_v2", 256),  # README: standard line 256
    "baberu": load_baberu, "manga_ocr": load_manga_ocr, "preview": load_preview, "paddleocr_vl_manga": load_paddle,
    "loopnar_a_L1": make_looped(1), "loopnar_a_L2": make_looped(2), "loopnar_a_L3": make_looped(3),
}

def load_images():
    gt = [json.loads(l) for l in open(BUNDLE / "gt.jsonl")]
    imgs = {}
    for g in gt:
        with Image.open(BUNDLE / g["file"]) as im: im.load(); imgs[g["key"]] = im.copy()
    return gt, imgs

def run_preds(name, predict, gt, imgs):
    out_path = ROOT / "preds" / f"{name}.jsonl"; out_path.parent.mkdir(exist_ok=True)
    for g in gt[:20]: predict([imgs[g["key"]]])  # warmup, not timed
    sync(); torch.cuda.reset_peak_memory_stats()
    lat, rows = [], []
    t_all = time.perf_counter()
    for g in gt:
        t = time.perf_counter(); p = predict([imgs[g["key"]]])[0]; sync(); dt = time.perf_counter() - t
        lat.append(dt); rows.append({"key": g["key"], "pred": p, "lat_ms": round(1000 * dt, 3)})
    total = time.perf_counter() - t_all
    out_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    lat.sort(); q = lambda p: round(1000 * lat[min(len(lat) - 1, int(p * len(lat)))], 2)
    return {"model": name, "n": len(rows), "batch": 1, "total_sec": round(total, 1), "lat_ms_mean": round(1000 * statistics.mean(lat), 2),
            "lat_ms_p50": q(.5), "lat_ms_p90": q(.9), "lat_ms_p99": q(.99), "lat_ms_max": round(1000 * lat[-1], 2),
            "imgs_per_sec_bs1": round(len(rows) / total, 2), "peak_mem_mb_bs1": round(torch.cuda.max_memory_allocated() / 2**20),
            "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("model"); ap.add_argument("--stage", default="preds", choices=["preds", "smoke"]); a = ap.parse_args()
    (ROOT / "results").mkdir(exist_ok=True)
    gt, imgs = load_images()
    predict = ADAPTERS[a.model]()
    meta = {"attn": getattr(predict, "attn", None)}
    if a.stage == "smoke":
        sub = gt[:16]; t = time.perf_counter(); preds = [predict([imgs[g["key"]]])[0] for g in sub]; sync()
        ok = sum(p.replace(" ", "") == g["text_r8"] for p, g in zip(preds, sub))  # rough (raw vs r8); real scoring is local
        for p, g in list(zip(preds, sub))[:6]: print(repr(g["text"]), "->", repr(p))
        print(f"SMOKE {a.model}: EM {ok}/16, {1000 * (time.perf_counter() - t) / 16:.1f} ms/img, mem {torch.cuda.max_memory_allocated() / 2**20:.0f} MB", flush=True); return
    if a.stage == "preds":
        r = run_preds(a.model, predict, gt, imgs) | meta; print(r, flush=True)
        (ROOT / "results" / f"{a.model}_preds.json").write_text(json.dumps(r, indent=1))

if __name__ == "__main__":
    main()
