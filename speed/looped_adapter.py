"""LoopNAR-α = looped_v1 试验模型适配（2026-10-04 用户要求补测；2026-10-12 23:xx 用户要求在 sailgpu2 上补测 Read v1.3：路径改到 bench_v13，加 fp16 autocast，2080 Ti 无原生 bf16）。run_eval.py 与 speed2.py 共用。
模型：small_nar_design/looped.py 的 LoopedNAR（C0 起 4 层共享 decoder × 3 圈，boundary=norm，95 万张续训）；
权重 = 25724:runs/loopexp/looped_v1/ckpt_last.pt（sha cf654b18…）只取 model/config 导出的 looped_v1_model.pt（sha 191d8def…）。
预处理与 10-01 Mixed 评测相同：model.preprocess(image, 384)（固定 384 token 预算，补零到 384，可直接堆叠成 batch）。
解码与 eval_mixed_ar.text_of 相同：每槽 argmax，截到第一个 EOS。
精度：fp32 = 10-01 Mixed 评测口径（TF32 关）；bf16 = torch.autocast（与 Preview 在 CUDA 上默认 bf16 对应；Preview 是整模型转 bf16，此处是 autocast）。
loops：1/2/3 = 只跑前 n 圈并用该圈读出（可调深度）。"""
import sys
from pathlib import Path

import numpy as np
import torch

CODE = Path("/home/clx/mangaOCR-NAR/experiments/small_nar_design")  # model.py 默认字表 = ../../release/manga-ocr-nar-preview/nar_vocabulary.json（6816，与 looped_v1 训练一致；进程内不得设 NAR_VOCAB）
CK = Path("/home/clx/bench_v13/models/looped_v1/looped_v1_model.pt")
BUDGET = 384


def _M():
    if str(CODE) not in sys.path: sys.path.insert(0, str(CODE))
    import model as M
    return M


def prep(imgs):
    M = _M(); P, V, R, C, H, W = [], [], [], [], [], []
    for im in imgs:
        p, v, r, c, (h, w) = M.preprocess(im, BUDGET)
        P.append(p.numpy()); V.append(v.numpy()); R.append(r.numpy()); C.append(c.numpy()); H.append(h); W.append(w)
    return {"patches": np.stack(P), "valid": np.stack(V), "rows": np.stack(R), "cols": np.stack(C),
            "h": np.array(H, dtype=np.int64), "w": np.array(W, dtype=np.int64)}


def build(loops, dtype):
    M = _M(); import looped as LP
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    ck = torch.load(CK, map_location="cpu", weights_only=False); cfg = ck["config"]
    net = LP.LoopedNAR(M.Config(encoder=M.MONKEY_S, fusion="static"), cfg["k"], cfg["loops"], cfg.get("boundary", "raw"))
    net.load_state_dict(ck["model"], strict=True); net = net.float().cuda().eval()
    assert 1 <= loops <= net.loops and dtype in ("fp32", "bf16", "fp16")
    assert len(M.CHARACTERS) == 6816, ("looped_v1 uses the Preview vocabulary", len(M.CHARACTERS))

    @torch.inference_mode()
    def infer(x):
        t = {k: torch.from_numpy(v).cuda(non_blocking=True) for k, v in x.items()}
        with torch.autocast("cuda", dtype=torch.bfloat16 if dtype == "bf16" else torch.float16, enabled=dtype != "fp32"):
            kvs, km, _ = net.encode(t["patches"], t["valid"], t["rows"], t["cols"], t["h"], t["w"])
            lg = net.run(kvs, km, loops=loops)[-1][0]
        out = []
        for row in lg.argmax(-1).cpu().tolist():
            row = row[: row.index(M.EOS)] if M.EOS in row else row
            out.append("".join(M.CHARACTERS[i] for i in row if i < M.EOS))
        return out
    return infer
