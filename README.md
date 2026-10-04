# JMangaBench_Read v1.2 — a Japanese manga OCR benchmark

[English](README.md) | [中文](README_zh.md) · [Appendix](APPENDIX.md) · [Interactive leaderboard](https://muscgab.github.io/JMangaBench_Read/) · [Dataset (images)](https://huggingface.co/datasets/muscgab/JMangaBench_Read)

JMangaBench_Read evaluates the accuracy and speed of OCR models on text boxes cropped from Japanese manga pages. The main set contains the text a reader reads and a translation pipeline translates: speech, narration and asides. Sound effects are kept in a separate set.

- Main set: 3,142 text boxes from 732 pages by 732 artists (one page per artist). SFX set: 380 boxes.
- All pages first posted between 2025-10-01 and 2026-03-10.
- Labels from three LLM readers and human review (547 main-set boxes human-confirmed).
- Speed measured per image, per page and at maximum throughput on one RTX 3080 Ti.

Found an error in a label, a score or the docs? Please [open an issue](https://github.com/muscgab/JMangaBench_Read/issues). Corrections are welcome.

## Leaderboard

Ranked by composite score (defined in [Scoring](#scoring)). Main set, 3,142 boxes, RTX 3080 Ti.

| # | Model | Arch | Params | Composite ↑ | CER % ↓ | EM % ↑ | Per-image ms ↓ | Per-page ms (p50) ↓ | Max img/s ↑ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Hayai v2.5 Nova p512 | AR | 157M | **96.54** | 2.71 | 87.40 | 102.3 | 205.2 | 84 (b192) |
| 2 | Hayai v2.5 Nova p384 | AR | 157M | **96.51** | 2.63 | 87.36 | 94.7 | 212.8 | 130 (b192) |
| 3 | Hayai v2.5 Nova p256 | AR | 157M | **96.49** | 3.08 | 86.28 | 92.0 | 189.3 | 163 (b256) |
| 4 | Hayai v2.1 | AR | 156M | **95.83** | 2.67 | 86.25 | 91.3 | 189.6 | 143 (b320) |
| 5 | Preview † | NAR | 196M | **95.55** | 3.21 | 85.30 | 51.1 | 81.5 | 167 (b20) |
| 6 | PaddleOCR-VL-For-Manga | AR (VLM) | 959M | **94.64** | 2.13 | 87.08 | 253.9 | — | 4.0 (b1) § |
| 7 | LoopNAR-α L2 † ‡ | NAR | 50M | **94.24** | 3.55 | 82.78 | 27.5 | 56.8 | — |
| 8 | LoopNAR-α L3 † ‡ | NAR | 50M | **94.13** | 3.50 | 82.46 | 32.5 | 62.6 | 239 (b28) |
| 9 | LoopNAR-α L1 † ‡ | NAR | 50M | **93.88** | 4.07 | 81.51 | 22.5 | 52.1 | 268 (b24) |
| 10 | baberuOCR | AR | 113M | **93.54** | 3.89 | 82.65 | 100.9 | 216.2 | 160 (b256) |
| 11 | mangaOCR | AR | 111M | **90.13** | 5.01 | 78.04 | 66.5 | 206.0 | 46 (b24) |

- † Made by the authors of this benchmark (see [Conflict of interest](#conflict-of-interest)).
- ‡ Experimental model in development. L1/L2/L3 = number of decoder loops, same weights.
- § Batched outputs are invalid for this model; measured at batch size 1 only, no per-page result.
- Accuracy columns use batch-size-1 outputs. Under per-page batching, composite scores change by at most 0.09.
- Speed was measured on all 3,522 crops (main set and SFX set).
- `bN`: batch size at maximum throughput.
- Params from the published weight files; mangaOCR estimated from its fp32 file size.
- Breakdowns by subset, length and role, and scores on the SFX set: [appendix](APPENDIX.md#a1-accuracy-by-subset).

### Accuracy vs. speed

Click a chart to open the interactive version (subsets: all / printed / non-printed / gold / hard / SFX set).

[![Composite score vs. per-page latency](figures/pareto_page.png)](https://muscgab.github.io/JMangaBench_Read/)

[![Composite score vs. per-image latency](figures/pareto_image.png)](https://muscgab.github.io/JMangaBench_Read/)

From per-image to per-page inference, time per box drops from 51.1 to 9.8 ms for Preview (NAR) and from 91.3 to 24.2 ms for Hayai v2.1 (AR).

## Data

### Source

Black-and-white Japanese comic pages posted publicly online by independent artists, collected for research use. Source type and license follow [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText).

| Rule | Value |
|---|---|
| Posting date | 2025-10-01 to 2026-03-10; artwork first published October 2025 or later (estimated from the original post ID) |
| Artists | one page per artist, 732 artists in the main set |
| Color | black-and-white |
| Content rating (main set) | general (2,514 boxes), sensitive (628 boxes) |
| Language | Japanese |
| Excluded artists | those who publicly prohibit reposting or AI use |

### Overlap with AnimeText

All pages of both sets were checked (739 pages).

- [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText): 0 pages. All 735,060 image IDs (train, valid, test) were checked. Its newest image was posted on 2024-11-23.
- [animetext-ocr](https://huggingface.co/datasets/JustANormalTinkerer/animetext-ocr): 0 pages. All 496,601 source image IDs were checked.

### Box selection and labeling

**1. Detection.** AnimeText YOLO12x detector, confidence ≥ 0.425. For nested boxes the smaller box is kept. General pages keep all boxes; sensitive pages keep up to 8 random boxes. Result: about 21,500 candidate boxes on 2,524 pages.

**2. LLM readers.** Each reader worked independently and did not see the other readers' outputs. Total usage: about 66 M input tokens and 5.3 M output tokens.

| Reader | Task | Boxes read |
|---|---|---|
| GPT-6.1 Sol | OCR of the full pool; font class (printed / handwritten / artistic); text role; first screening | 21,305 |
| GPT-6 Astra | OCR; admission decision; text role; language label | about 11,900 |
| Claude Opus 5.5 | final review: OCR from the crop only; text role; flags for boxes cut by the frame, mixed with other text, or not body text | 9,083 |

**3. Exclusions** (Sol screening and Astra admission):

- Scene text: shop names, station names, street signs, signboards, posters.
- Non-story text: ads, watermarks, signatures and credits, large titles.
- Large decorative sound effects (e.g. a giant ドドド).
- Damaged text: occluded, smeared, faded, blacked out, or heavily cut off.
- Non-Japanese text.

Sol excluded 866 boxes and marked 634 for review (reasons, non-exclusive: scene text 309, large sound effects 220, cut off 115, signatures 107, large titles 42, ads 36). Astra rejected about 100 more. 284 non-Japanese boxes were removed. Hard-to-read, rare or deformed characters, long text, artistic lettering and low reader confidence are not exclusion criteria. Prompts: [appendix](APPENDIX.md#a3-llm-readers).

**4. Labels.**

| Case | Label | Boxes (main set) |
|---|---|---|
| Three readings identical after normalization, no Opus flag | agreed reading | 2,595 |
| Readings differ (259); readings agree but Opus flagged the box (101); readings differed under an earlier normalization rule (4) | human decision: choose a reading, enter a new one, or drop the box | 364 (hard) |
| Uniform random sample of agreed boxes, re-checked by a human | 200/200 correct (183 in the main set) | 183 |

**5. Page cutoff.** Pages were processed in a fixed order. The release contains all remaining boxes on the 739 pages processed before human review stopped. Boxes whose readings differed only in small kana (e.g. ぁ / あ) were removed automatically.

**6. Main set and SFX set.**

| Set | Content | Boxes |
|---|---|---|
| Main | all text inside speech balloons and caption boxes, including interjections and cries (えっ, うわっ, わんわん); text outside balloons with lexical meaning: a called name, a spoken phrase, an author's aside, a bracketed description such as （歓声） | 3,142 |
| SFX | sound effects and mimetic words drawn on the artwork outside balloons (ズズッ, ぷいっ, わなわな), including screams, panting and whisper marks (ギャア, ゼェゼェ, ひそ) | 380 |

Assignment: the role label (majority of the three readers) marked 381 boxes as sound effects. After checking the page, 6 of them were kept in the main set (lexical text outside balloons) and 5 boxes labeled dialogue or other were moved to the SFX set (effect text outside balloons). The SFX set is scored separately and is not part of the composite.

**Label quality.** 0 errors in 200 audited agreed boxes gives a one-sided 95% upper bound of 1.49% on the agreed-label error rate (Clopper–Pearson), or about 1.2% over all 3,142 main-set labels. A separate check of 100 agreed boxes, stratified by reader confidence, found 0 errors (confirmed verbally, not recorded per box).

### Subsets

| Subset | Definition | Boxes |
|---|---|---|
| all | all main-set boxes | 3,142 |
| hard | readers disagreed or Opus flagged the box; human-decided label | 364 |
| gold | all human-confirmed boxes (hard + audit) | 547 |
| printed | majority font label of the three readers is printed | 2,328 |
| non-printed | handwritten, artistic or mixed | 814 |
| SFX set | separate set, not in the composite | 380 |

Box selection used font quotas with a 40% non-printed target (printed 6,000 / handwritten 3,000 / artistic 1,000). By Sol's font label, the non-printed share is 31.4% in the screened candidate pool (15,877 boxes) and 26.6% in the main set.

## Scoring

Predictions and labels are normalized with the same rules (`r7`):

| Rule | Example |
|---|---|
| width folding (full-width ASCII → half-width, half-width kana → full-width) | `！` → `!`, `ﾃｽﾄ` → `テスト` |
| remove whitespace | `あ い` → `あい` |
| pause-dot runs → `…` | `・・・`, `...`, `……` → `…` |
| long dashes → `ー`; `ー` runs → one `ー` | `──` → `ー` |
| wave marks → `〜`; `〜` runs → one `〜` | `～～` → `〜` |
| quote forms → `"` / `'` | `〝 〟` → `"` |
| voicing marks unified | `う゛` → `ゔ`, `あ゙` → `あ゛` |

Corner brackets 「」『』 and small kana are kept. Labels use `♡`; `♥` is not mapped.

**Metrics**

- CER: total edit distance / total label characters.
- EM: fraction of boxes with an exact match.
- Composite (ranking metric), 1 − normalized edit distance as in ICDAR 2019 ReCTS, averaged equally over printed and non-printed main-set boxes:

$$s_i = 1 - \frac{\mathrm{ED}(p_i, g_i)}{\max(|p_i|, |g_i|)}$$

$$\text{Composite} = 100 \times \tfrac{1}{2}\left(\overline{s}_{\text{printed}} + \overline{s}_{\text{non-printed}}\right)$$

## Speed

One RTX 3080 Ti (12 GB). Each model uses the default precision of its README or code. Images are pre-decoded in memory. Timings include the model's preprocessing and decoding and are GPU-synchronized. All 3,522 crops were used.

| Measure | Method |
|---|---|
| Per-image latency | batch size 1, single process; mean over all crops after warm-up |
| Per-page latency | 403 batches with sizes drawn from the real per-page box counts (mean 8.7, median 8, p90 15, max 33); single process, preprocessing included; p50 of batch time |
| Max throughput | 512 crops; preprocessing in 6 worker processes in parallel with the GPU; batch size searched up to 512; median of 3 runs at the best batch size |

## Models

| Model | Weights | Settings |
|---|---|---|
| Preview † | [muscgab/manga-ocr-nar-preview](https://huggingface.co/muscgab/manga-ocr-nar-preview) | bf16 |
| LoopNAR-α † | not released | bf16; 1/2/3 decoder loops |
| Hayai v2.1 | [JustANormalTinkerer/hayai-ocr-v2](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2) (main branch = v2.1) | 256 patches; greedy; fp16 autocast in model code |
| Hayai v2.5 Nova | [JustANormalTinkerer/hayai-ocr-v2.5-nova](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova) | 256 / 384 / 512 patches; otherwise as above |
| PaddleOCR-VL-For-Manga | [jzhang533/PaddleOCR-VL-For-Manga](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga) | bf16; greedy; prompt `OCR:` |
| baberuOCR | [genshiai-daichi/baberu-ocr](https://huggingface.co/genshiai-daichi/baberu-ocr) | bf16 (CUDA default); README generation defaults |
| mangaOCR | [kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base) | fp32; package defaults |

LLM reader scores are listed in the appendix for reference and are not ranked.

## Conflict of interest

Preview and LoopNAR-α are made by the authors of this benchmark.

- Labels come from three third-party LLMs and human review. The review interface showed LLM readings only, no OCR model outputs.
- The box set was fixed before any OCR model was scored. Later changes: v1.1 corrected five labels saved empty by mistake (three relabeled, two removed). v1.2 moved sound effects to a separate set after scores were known; the split uses only box content and position, and the score change of every model is listed in [appendix A6](APPENDIX.md#a6-version-history).
- All model predictions, the scoring script and the speed scripts are released.

## Limitations

- 2,595 main-set labels are agreed LLM readings verified by sampling only.
- During human review the majority reading was pre-filled.
- The hard subset is defined by LLM disagreement and flags.
- The main/SFX split relies on LLM role labels. Boxes labeled dialogue were screened for sound effects by a text-pattern scan (124 flagged, 17 checked on the page), not one by one.
- Boxes were screened by LLMs; boxes judged unreadable are not included.
- One source type, recent fan and original works, one GPU.
- At the max-throughput batch size, outputs match batch-size-1 outputs for 96.9–100% of boxes.

## Usage

```bash
pip install regex
python eval/score.py --pred my_preds.jsonl --name my_model --out results/my_model.json
python eval/score.py --pred my_preds.jsonl --gt data/gt_sfx.jsonl --name my_model   # SFX set
```

`my_preds.jsonl`: one line per box, `{"key": "10053471_0", "pred": "作戦を続行する"}`. Missing keys count as empty predictions. One prediction file can cover both sets.

| Location | Content |
|---|---|
| `data/gt.jsonl` | main set: labels and metadata, 3,142 boxes |
| `data/gt_sfx.jsonl` | SFX set, 380 boxes |
| `data/llm_readings.jsonl` | three LLM readings per box, both sets |
| `data/predictions/` | outputs of all listed models on both sets (batch size 1 and per-page) |
| `eval/` | scoring script and normalization code |
| [Hugging Face](https://huggingface.co/datasets/muscgab/JMangaBench_Read) | crop images at original resolution: `main/<key>.png` (split `test`), `sfx/<key>.png` (split `sfx`) |

`gt.jsonl` fields: `key`, `file`, `text`, `text_r7`, `n_chars`, `gold`, `gold_hard`, `gold_random_audit`, `printed`, `non_printed`, `font`, `role`, `orientation`, `crop_wh`, `page_id`, `box`, `rating`.

For evaluation only. Do not use for training.

## Corrections

If you find any error (a wrong label, a box that should be in the other set, a scoring or speed problem), please [open an issue](https://github.com/muscgab/JMangaBench_Read/issues). Fixes go into the next version and are listed in [appendix A6](APPENDIX.md#a6-version-history).

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) for data and code.

## Citation

```bibtex
@misc{jmangabench_read,
  title  = {JMangaBench\_Read: A Japanese Manga OCR Benchmark},
  year   = {2026},
  url    = {https://github.com/muscgab/JMangaBench_Read}
}
```
