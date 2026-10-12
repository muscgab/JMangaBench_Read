"""e4 (formal_v177: Monkey-S + gamma static fusion + 4-layer looped decoder x3, 6817 vocab) adapter for the Read v1.3 benchmark.
Same protocol as eval_ab.py (the e4 final eval on sailgpu2): M.preprocess(img, 324, fit=config fit='pad'), fp16 autocast,
net.encode -> net.run(loops=n) and read out the n-th loop (only n loops are computed, so latency reflects n), argmax up to
the first EOS. Raw text is returned; r8 normalisation is applied at scoring time like every other model.
Weights: e4_model.pt = model+config of /home/clx/formal_runs/formal_v177/ckpt_last.pt (step 78,125; sha ada062ad...)."""
# sailgpu2 fp16 rerun (user 2026-10-12: "你就在这台sailgpu上面测试，每一个gpu测试一个，可以并行来跑；都跑fp16先看能不能跑"):
# copy of v13_20261011/remote/*; ROOT from env BENCH_ROOT (default /home/clx/bench_v13); BENCH_FP16=1 (default) casts the
# rival models to fp16 (10-11: Hayai/mangaOCR fp32, baberu bf16); e4 stays fp16 autocast; new n4_L1 = formal_fp32_N4 final,
# fp16-reparametrised (fp16_20261012/fp16_convert.reparam, k=[1,1,16,1], c=1/4, eps*c^2), fp16 autocast.
import os, sys
from pathlib import Path
import numpy as np
import torch

E4 = Path(os.environ.get("E4_DIR", "/home/clx/bench_v13/e4"))
CODE = Path(os.environ.get("NAR_CODE", "/home/clx/mangaOCR-NAR/experiments/small_nar_design"))
N4_K, N4_C = [1.0, 1.0, 16.0, 1.0], 0.25   # calibrated on the final N4 checkpoint (2026-10-12 15:0x, /home/clx/tmp/fp16_final)
os.environ.setdefault("NAR_VOCAB", str(CODE / "vocab/nar_vocabulary_6817.json"))
BUDGET = 324
_cfg = {}


def _mods():
    if str(CODE) not in sys.path: sys.path.insert(0, str(CODE))
    import model as M, looped as LP
    return M, LP


def prep(imgs):
    M, _ = _mods(); P, V, R, C, H, W = [], [], [], [], [], []
    for im in imgs:
        p, v, r, c, (h, w) = M.preprocess(im, BUDGET, fit=_cfg.get("fit", "pad"))
        P.append(p.numpy()); V.append(v.numpy()); R.append(r.numpy()); C.append(c.numpy()); H.append(h); W.append(w)
    return {"patches": np.stack(P), "valid": np.stack(V), "rows": np.stack(R), "cols": np.stack(C),
            "h": np.array(H, dtype=np.int64), "w": np.array(W, dtype=np.int64)}


def build(loops):
    M, LP = _mods()
    st = torch.load(E4 / "e4_model.pt", map_location="cpu", weights_only=False); c = st["config"]
    _cfg["fit"] = c.get("fit", "pad"); assert c.get("vocab", len(M.CHARACTERS)) == len(M.CHARACTERS), (c.get("vocab"), len(M.CHARACTERS))
    cfg = M.Config(encoder=M.MONKEY_S, fusion="static"); cfg.layers, cfg.ffn = c["layers"], c["ffn"]
    net = LP.LoopedNAR(cfg, len(c["keep"]), c["loops"], c["boundary"]); net.load_state_dict(st["model"], strict=True)
    net = net.cuda().eval(); assert 1 <= loops <= net.loops

    @torch.inference_mode()
    def infer(x):
        t = {k: torch.from_numpy(v).cuda(non_blocking=True) for k, v in x.items()}
        with torch.autocast("cuda", dtype=torch.float16):
            kvs, km, _ = net.encode(t["patches"], t["valid"], t["rows"], t["cols"], t["h"], t["w"])
            lg = net.run(kvs, km, loops)[-1][0]
        return M.decode(lg.float().argmax(-1).cpu())
    return infer


def build_n4():
    """formal_fp32_N4 final (E4_DIR/n4_model.pt = model+config of formal_fp32_N4/ckpt_last.pt, step 279,499), made fp16-safe by the
    exact reparametrisation of fp16_20261012/fp16_convert.py (fold s3 into down, up half / k_i, residual * c, RMSNorm eps * c^2),
    then the same fp16-autocast path as e4 (1 loop). A plain fp16 run of this checkpoint overflows (EM 0, 2026-10-12)."""
    M, LP = _mods()
    if str(CODE / "fp16_20261012") not in sys.path: sys.path.insert(0, str(CODE / "fp16_20261012"))
    import fp16_convert as FC
    st = torch.load(E4 / "n4_model.pt", map_location="cpu", weights_only=False); c = st["config"]
    _cfg["fit"] = c.get("fit", "pad"); assert c["loops"] == 1 and c.get("vocab", len(M.CHARACTERS)) == len(M.CHARACTERS)
    cfg = M.Config(encoder=M.MONKEY_S, fusion="static"); cfg.layers, cfg.ffn = c["layers"], c["ffn"]
    net = LP.LoopedNAR(cfg, len(c["keep"]), c["loops"], c["boundary"]); net.load_state_dict(st["model"], strict=True)
    assert FC.FIX_EPS
    FC.reparam(net, N4_K, N4_C)
    net = net.cuda().eval()

    @torch.inference_mode()
    def infer(x):
        t = {k: torch.from_numpy(v).cuda(non_blocking=True) for k, v in x.items()}
        with torch.autocast("cuda", dtype=torch.float16):
            kvs, km, _ = net.encode(t["patches"], t["valid"], t["rows"], t["cols"], t["h"], t["w"])
            lg = net.run(kvs, km, 1)[-1][0]
        return M.decode(lg.float().argmax(-1).cpu())
    return infer


def build_n4_graph(precapture=tuple(range(1, 49)), buckets=None):
    """N4 accelerated (2026-10-12 17:5x, user "你把N4加速"): fp16-safe reparametrised weights cast to fp16, n4_fast.full_batch
    (exact rewrite of the padded reference forward) replayed through CUDA graphs per exact batch size (1..48 captured at load;
    larger sizes captured on first use). Input = prep() output (padded 324). Returns (infer, capture_sec dict)."""
    M, LP = _mods()
    if str(CODE / "fp16_20261012") not in sys.path: sys.path.insert(0, str(CODE / "fp16_20261012"))
    import fp16_convert as FC
    import n4_fast as NF
    st = torch.load(E4 / "n4_model.pt", map_location="cpu", weights_only=False); c = st["config"]
    _cfg["fit"] = c.get("fit", "pad")
    cfg = M.Config(encoder=M.MONKEY_S, fusion="static"); cfg.layers, cfg.ffn = c["layers"], c["ffn"]
    net = LP.LoopedNAR(cfg, len(c["keep"]), c["loops"], c["boundary"]); net.load_state_dict(st["model"], strict=True)
    FC.reparam(net, N4_K, N4_C)
    net = net.cuda().half().eval()
    runner = NF.BatchGraphRunner(NF.N4Fast(net), precapture=precapture, buckets=buckets)

    def infer(x):
        t = {k: torch.from_numpy(v) for k, v in x.items()}
        ids = runner(t["patches"], t["valid"], t["rows"], t["cols"], t["h"], t["w"])
        return M.decode(ids.cpu())
    infer.capture_sec = runner.capture_sec
    return infer


def build_n4_pipe():
    """N4 release CUDA path (user 2026-10-12 23:0x "CUDA我们使用解同步路径"): same fp16 weights as build_n4_graph, run through
    fp16_20261012/gpu_pipeline.N4GpuPipeline (GPU bit-exact preprocessing written into the bucket CUDA-graph buffers 1..16, 32, 48,
    one request per call, blocking-sync event, torch threads 1). Input = list of PIL images or uint8 HWC arrays -> texts."""
    M, LP = _mods()
    if str(CODE / "fp16_20261012") not in sys.path: sys.path.insert(0, str(CODE / "fp16_20261012"))
    import fp16_convert as FC
    from gpu_pipeline import N4GpuPipeline
    st = torch.load(E4 / "n4_model.pt", map_location="cpu", weights_only=False); c = st["config"]
    cfg = M.Config(encoder=M.MONKEY_S, fusion="static"); cfg.layers, cfg.ffn = c["layers"], c["ffn"]
    net = LP.LoopedNAR(cfg, len(c["keep"]), c["loops"], c["boundary"]); net.load_state_dict(st["model"], strict=True)
    FC.reparam(net, N4_K, N4_C)
    pipe = N4GpuPipeline(net.cuda().half().eval())
    return lambda imgs: pipe([i if isinstance(i, np.ndarray) else np.asarray(i.convert("RGB")) for i in imgs])
