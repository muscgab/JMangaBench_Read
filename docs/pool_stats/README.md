# Candidate-pool statistics used for synthetic data

[English](README.md) | [中文](README_zh.md) · [Back to README](../../README.md)

The synthetic training data of mangaocr-nar-small was designed with aggregate statistics measured on the benchmark's candidate pool. This page lists them. Values are in [`pool_stats.json`](pool_stats.json); no per-box data is included.

**Pool**: boxes that GPT-6.1 Sol kept in its first screening of the 2,524 candidate pages, minus the pages in Read v1.2, minus boxes labeled SFX. 8,887 printed and 2,516 non-printed boxes. The pages of the 4,660 Read v1.3 new boxes are part of this pool. Statistics were measured between 2026-10-07 and 2026-10-09.

**Generator configurations**: the parameter values below are those of the handwriting configuration used for the training data (identical in its V177f and V178 revisions) and of the printed generator's audit targets.

## Statistics that set generator parameters

| Statistic (pool subset) | Measured | Parameter set from it |
|---|---|---|
| Crop long edge, 10 bins (printed) | e.g. 160–223 px 18.25 %, 224–319 px 20.18 %, ≥ 640 px 9.45 % | audit targets for the printed generator's output (relative tolerance 10 %) |
| Crop aspect ratio, 7 bins (printed) | [1.5, 2.5) 34.95 %, [2.5, 4) 36.87 %, [4, 6) 13.94 % | same |
| Label length (non-printed) | 1–4 / 5–8 / 9–16 / 17–32 / > 32 = 43.1 / 29.0 / 19.7 / 7.5 / 0.7 % | handwriting length-bin weights (> 32 dropped, rest renormalized) |
| Crop scale $\sqrt{hw/n}$ (non-printed) | median 52.2 px, p10 26.4, p90 121.3 | handwriting font-height bin weights (scale divided by the generator's measured 1.563 scale-px per requested px) |
| Ink luma (non-printed) | 81.3 % of crops contain pure black (luma ≤ 2); median pure-black share 3.6 % | per-image dark-ink luma mixture |
| Page encoding (1,721 source pages) | JPEG 77 %, PNG 23 %; JPEG quality ~100 56 %, ~85 30 %, 90–95 11 %, ≤ 80 4 % | final encode: PNG probability 0.23 and JPEG quality mixture |
| Balloon outline (non-printed) | edge visible in 57.7 % of crops; dark-ring share ≥ 0.6 in 62.3 % | probability 0.75 of restricting balloon assets to outlined ones |
| Area outside the text region (non-printed) | < 1 % / 1–10 % / 10–30 % / ≥ 30 % = 43.7 / 32.0 / 13.4 / 10.9 % | probability 0.1 of fitting the balloon tightly around the text |

Synthetic distributions are set one statistic at a time (marginals). No joint distribution of the pool was imposed on the generators.

## Statistics used for comparison only

Measured on the same pool and compared with synthetic outputs during review, without setting any parameter: image-formation cues (pure-black, dark and pure-white pixel shares, paper noise, flat-region residual), text features (length, kanji share, kana-only and punctuation-only shares), a classifier two-sample test (real vs synthetic), within-image pen-width spread, text margins, and line-break positions. The first two are included in `pool_stats.json` under `reference_only`.
