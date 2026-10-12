"""Batched PaddleOCR-VL-For-Manga adapter (user 2026-10-12: "你把paddleOCR-VL的batch推理修一下。应该是能修好的").
Same settings as the 2026-10-03 v1 adapter (bf16, sdpa when flash-attn is absent, prompt "OCR:", greedy, max_new_tokens 512,
left padding). sailgpu2 (2026-10-12 23:xx, Read v1.3): PADDLE_DIR / PADDLE_DTYPE env (2080 Ti has no native bf16). Run with PYTHONPATH=/root/autodl-tmp/m109/rivals/tf455 (transformers 4.55.4).

Root cause of the 2026-10-04 batch failure (bs2 agreement 0.27): the vision tower packs the patches of every image in the batch
into ONE sequence and separates images only through cu_seqlens, which SiglipAttention uses solely on the flash-attn varlen path.
Without flash-attn it falls back to sdpa/eager with attention_mask=None, so patches of different images attend to each other
(bs=1 has a single image and is unaffected). Fix (v2): when cu_seqlens has more than one segment and flash-attn is not used, split the packed
sequence into a padded per-image batch with a key-padding mask (v1 = full N x N block-diagonal mask: 127/128 = bs1 at bs 16 but
OOM at bs 64). The text side (3D rope with attention_mask, left padding) already handles
padding (get_rope_index places positions only on unmasked tokens; rope deltas use the padded length)."""
import torch

import os
M = os.environ.get("PADDLE_DIR", "/root/autodl-tmp/m109/rivals/models/paddleocr_vl_manga")
DTYPE = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}[os.environ.get("PADDLE_DTYPE", "bf16")]
_proc = None


def _processor():
    global _proc
    if _proc is None:
        from transformers import AutoProcessor
        _proc = AutoProcessor.from_pretrained(M, trust_remote_code=True, use_fast=True)
        _proc.tokenizer.padding_side = "left"
    return _proc


def prep(imgs):
    proc = _processor()
    msgs = [[{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}] for im in imgs]
    texts = proc.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    return dict(proc(text=texts, images=[[im] for im in imgs], return_tensors="pt", padding=True))


def _patch_vision_attention(model):
    """Per-image attention for the packed vision sequence: split (1, N, D) by cu_seqlens into a padded batch (S, L, D),
    run the original attention with a key-padding mask (S, 1, 1, L) and the rope cos/sin gathered the same way, then scatter
    back. Memory grows with sum(L^2) per image instead of N^2 (a full N x N block mask OOMed at bs 64)."""
    cls = type(model.visual.vision_model.encoder.layers[0].self_attn)
    if getattr(cls, "_per_image_patch", False):
        return
    orig = cls.forward

    def forward(self, hidden_states, attention_mask=None, output_attentions=False, cu_seqlens=None, rope_emb=None):
        if (attention_mask is not None or cu_seqlens is None or len(cu_seqlens) <= 2
                or self.config._attn_implementation == "flash_attention_2" or hidden_states.shape[0] != 1):
            return orig(self, hidden_states, attention_mask=attention_mask, output_attentions=output_attentions,
                        cu_seqlens=cu_seqlens, rope_emb=rope_emb)
        dev = hidden_states.device
        cu = cu_seqlens.to(dev).long(); lens = cu[1:] - cu[:-1]; S, L = len(lens), int(lens.max())
        ar = torch.arange(L, device=dev)
        valid = ar[None, :] < lens[:, None]                                   # (S, L)
        idx = torch.where(valid, cu[:-1, None] + ar[None, :], torch.zeros_like(valid, dtype=torch.long))
        hs = hidden_states[0][idx]                                            # (S, L, D)
        if rope_emb is not None:
            rope_emb = (rope_emb[0][idx], rope_emb[1][idx])                   # (S, L, head_dim)
        mask = torch.zeros(S, 1, 1, L, dtype=hidden_states.dtype, device=dev)
        mask.masked_fill_(~valid[:, None, None, :], torch.finfo(hidden_states.dtype).min)
        one = torch.tensor([0, L], dtype=cu_seqlens.dtype, device=cu_seqlens.device)  # single segment: no recursion
        out, _ = orig(self, hs, attention_mask=mask, output_attentions=False, cu_seqlens=one, rope_emb=rope_emb)
        return out[valid].unsqueeze(0), None

    cls.forward = forward
    cls._per_image_patch = True


def load():
    from transformers import AutoModelForCausalLM
    try:
        import flash_attn  # noqa: F401
        attn = "flash_attention_2"
    except ImportError:
        attn = "sdpa"
    model = AutoModelForCausalLM.from_pretrained(M, trust_remote_code=True, torch_dtype=DTYPE, attn_implementation=attn).cuda().eval()
    _patch_vision_attention(model)
    proc = _processor()
    if model.generation_config.pad_token_id is None:
        model.generation_config.pad_token_id = proc.tokenizer.eos_token_id

    @torch.inference_mode()
    def infer(x):
        x = {k: (v.cuda() if isinstance(v, torch.Tensor) else v) for k, v in x.items()}
        g = model.generate(**x, max_new_tokens=512, do_sample=False, use_cache=True)
        return proc.batch_decode(g[:, x["input_ids"].shape[1]:], skip_special_tokens=True)
    infer.attn = attn
    return infer
