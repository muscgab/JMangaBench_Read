# JMangaBench_Read v1.3.1：日文漫画 OCR 评测集

[English](README.md) | [中文](README_zh.md) · [附录](APPENDIX_zh.md) · [交互式榜单](https://muscgab.github.io/JMangaBench_Read/) · [数据集（图片）](https://huggingface.co/datasets/muscgab/JMangaBench_Read)

JMangaBench_Read 评测 OCR 模型在日文漫画文字框裁图上的准确率和速度。评测集收录读者要读、翻译流程要翻译的文字：台词、旁白和旁注。拟声词不收录。

- 7,789 个文字框，来自 1,847 页、1,847 位画师（每位画师一页）。
- 全部页面首次发布于 2025-10-01 至 2026-10-01。
- 标签来自三个 LLM 识别器和人工审核，其中 1,266 框经人工确认。
- 在一张 RTX 2080 Ti 上测逐张延迟、整页延迟和最大吞吐。

发现标签、分数或文档有错误，欢迎[提 issue](https://github.com/muscgab/JMangaBench_Read/issues) 联系我们。

**v1.3 的变化**：新增 1,116 页上的 4,660 框；删除 v1.2 中的 13 框（规则见[选框与标注](#选框与标注)）；评分归一化更名为 RIN v1，并增加两条符号规则；全部模型在 RTX 2080 Ti 上以 fp16 重新测速。作者在模型开发中使用过 Read v1.2 和 1,021 个新框（见[开发用途说明](#开发用途说明)）；4,660 个新框上的分数单独列在[附录](APPENDIX_zh.md#a1-各板块准确率)。完整记录见[附录 A6](APPENDIX_zh.md#a6-版本记录)。

**v1.3.1 的变化（2026-10-17）**：评分归一化由 RIN v1 改为 RIN v1.1，实心心号 `♥`、`❤` 按 `♡` 计（标签本来就全用 `♡`）。框、标签和预测都不变，全部分数重新计算。各模型 EM 上升 0.17–0.37 个百分点，排名不变。

## 排行榜

按综合分排序（定义见[评分](#评分)）。7,789 框，RTX 2080 Ti，fp16。

| # | 模型 | 架构 | 参数量 | 综合分 ↑ | CER % ↓ | EM % ↑ | EM NFKC % ↑ | 逐张延迟 ms ↓ | 整页延迟 ms（p50）↓ | 最大吞吐 张/秒 ↑ |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | manga-ocr-base-CPT-flex † ¶ | AR | 111M | **97.47** | 1.50 | 91.71 | 80.60 | 11.0 | 43.0 | 260（b32） |
| 2 | manga-ocr-nar-small † | NAR | 54M | **97.29** | 1.71 | 91.36 | 80.34 | 9.1 | 35.5 | 299（b48） |
| 3 | Hayai v2.5 Nova p384 | AR | 157M | **96.64** | 2.38 | 88.18 | 75.59 | 54.0 | 252.0 | 175（b48） |
| 4 | Hayai v2.5 Nova p256 | AR | 157M | **96.60** | 2.95 | 87.16 | 74.84 | 53.0 | 249.1 | 194（b40） |
| 5 | Hayai v2.5 Nova p512 | AR | 157M | **96.57** | 2.35 | 88.10 | 75.27 | 55.4 | 264.4 | 111（b40） |
| 6 | manga-ocr-nar-small-distil † ∥ | NAR | 30M | **96.40** | 2.29 | 89.09 | 78.57 | 8.4 | 35.0 | 287（b48） |
| 7 | Preview † | NAR | 196M | **95.84** | 2.92 | 85.68 | 78.51 | 31.9 | 103.0 | 91（b16） |
| 8 | Hayai v2.1 | AR | 156M | **95.46** | 2.67 | 84.70 | 77.99 | 141.7 | 300.6 | 87（b128） |
| 9 | PaddleOCR-VL-For-Manga | AR（VLM） | 959M | **95.04** | 1.99 | 87.89 | 53.15 | 366.6 | 1024.4 | 6.6（b10） |
| 10 | LoopNAR-α L2 † ‡ | NAR | 50M | **94.75** | 3.30 | 83.93 | 74.09 | 35.6 | 70.8 | 243（b48） |
| 11 | LoopNAR-α L3 † ‡ | NAR | 50M | **94.73** | 3.20 | 83.93 | 74.21 | 42.7 | 76.9 | 224（b48） |
| 12 | LoopNAR-α L1 † ‡ | NAR | 50M | **94.16** | 3.92 | 82.24 | 72.64 | 29.0 | 63.2 | 259（b56） |
| 13 | baberuOCR v1.1 | AR | 113M | **93.37** | 3.62 | 81.88 | 70.89 | 123.6 | 278.3 | 105（b256） |
| 14 | mangaOCR | AR | 111M | **90.27** | 4.81 | 78.51 | 67.90 | 84.9 | 242.4 | 42（b56） |
| – | GPT-6 Astra * | LLM | — | 99.47 | 0.24 | 98.04 | 93.40 | — | — | — |
| – | GPT-6.1 Sol * | LLM | — | 99.35 | 0.28 | 97.75 | 97.71 | — | — | — |
| – | Claude Opus 5.5 * | LLM | — | 98.05 | 0.59 | 95.58 | 88.33 | — | — | — |

<details><summary>更多模型</summary>

| # | 模型 | 架构 | 参数量 | 综合分 ↑ | CER % ↓ | EM % ↑ | EM NFKC % ↑ | 逐张延迟 ms ↓ | 整页延迟 ms（p50）↓ | 最大吞吐 张/秒 ↑ |
|---|---|---|---|---|---|---|---|---|---|---|
| – | e4 L3 † § | NAR | 54M | **97.31** | 1.70 | 91.23 | 80.07 | 42.8 | 71.9 | 227（b32） |
| – | e4 L2 † § | NAR | 54M | **97.30** | 1.72 | 91.17 | 80.06 | 35.5 | 64.3 | 267（b48） |
| – | e4 L1 † § | NAR | 54M | **97.15** | 1.94 | 90.64 | 79.66 | 28.3 | 58.1 | 282（b24） |

</details>

- † 本评测集作者的模型（见[利益关联声明](#利益关联声明)）。
- ‡ 试验模型，未发布。L1/L2/L3 为解码器循环圈数，权重相同。
- § e4：作者此前的主线检查点（与 manga-ocr-nar-small 同一结构系列，按 3 圈训练），已作为参照模型发布（[muscgab/mangaocr-nar-looped-e4-exp](https://huggingface.co/muscgab/mangaocr-nar-looped-e4-exp)）。L1/L2/L3 为推理时的解码器圈数。
- ¶ manga-ocr-base-CPT-flex：mangaOCR（[kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base)）由作者在 manga-ocr-nar-small 的训练数据上继续预训练；结构不变，换用 6,817 字的新词表，输入保持长宽比（最多 196 个 patch）。速度用其发布包的 CUDA 路径（CUDA 图 + GPU 预处理）测得，该路径在全部 7,789 框上与普通路径输出一致；编码器 fp16、解码器 fp32。224 × 224 的版本（manga-ocr-base-CPT）不列入。
- ∥ manga-ocr-nar-small-distil：由 manga-ocr-nar-small 蒸馏得到（保留 12 层编码器中的 6 层，解码器宽度 384，参数 30M），以 int8 量化训练。GPU 各列使用其发布的 CUDA 后端，在 fp16 中模拟 int8 运算（CUDA 图）。CPU 上以 int8 ONNX 运行（EM 按 RIN v1 计）：全部 7,789 框，Xeon Gold 6148 上 EM 88.92、每框 37.3 ms（p50，8 线程，含预处理，u8u8）；M1 Pro 上 EM 88.91、每框 21.0 ms（u8s8）。
- \* LLM 识别器。hard 以外的 7,005 个标签就是三家一致的读法，因此这几行仅供参考，不参与排名（[附录 A4](APPENDIX_zh.md#a4-llm-参考分数不参与排名)）。
- 准确率各列用 batch = 1 的输出。整页批量推理下综合分变化不超过 0.02。
- EM NFKC：只做 Unicode NFKC 后的完全匹配，供参考。它与 EM 的差距主要来自 RIN 合并的写法差异（见[评分](#评分)）。
- `bN`：最大吞吐对应的 batch 大小。
- 参数量取自公开权重文件；mangaOCR 按 fp32 权重文件大小估算。
- 按板块、长度、文字类型的明细，测速明细，以及 NFKC 结果，见[附录](APPENDIX_zh.md)。独立的拟声词集（380 框）上的分数见[附录 A7](APPENDIX_zh.md#a7-拟声词集)。

### 准确率与速度

点击图片打开交互版（可切换板块：全部 / 新增 / 印刷 / 非印刷 / gold / hard；e4 在“更多模型”中）。

[![综合分与整页延迟](figures/pareto_page.png)](https://muscgab.github.io/JMangaBench_Read/)

[![综合分与逐张延迟](figures/pareto_image.png)](https://muscgab.github.io/JMangaBench_Read/)

一次读一页、页与页之间不停顿时，每页耗时中位数：manga-ocr-nar-small-distil 35 ms，manga-ocr-nar-small 37 ms，manga-ocr-base-CPT-flex 50 ms，Hayai v2.5 Nova p384 245 ms，Hayai v2.1 345 ms（[附录 A2](APPENDIX_zh.md#a2-测速明细)）。

## 数据

### 来源

独立画师在网上公开发布的黑白日文漫画页，为研究用途收集。来源类型与许可证与 [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText) 一致。

| 规则 | 内容 |
|---|---|
| 发布时间 | 2025-10-01 至 2026-10-01（v1.2 的页面到 2026-03-10，新页面从 2026-03-10 起） |
| 画师 | 每位画师一页，共 1,847 位 |
| 颜色 | 黑白 |
| 内容分级 | 全年龄（6,229 框）、轻度敏感（1,560 框） |
| 语言 | 日文 |
| 排除画师 | 公开声明禁止转载或禁止 AI 使用的画师 |

### 与 AnimeText 的重合

全部 1,847 页均按图片 ID 核对（数据集版本取 2026-10-04）。

- [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText)：0 页。其 735,060 个图片 ID（train、valid、test）最大为 8,475,567，发布于 2024-11-23。本评测集最小的页面 ID 为 10,053,471。
- [animetext-ocr](https://huggingface.co/datasets/JustANormalTinkerer/animetext-ocr)：0 页。其 496,601 个来源图片 ID 最大为 8,475,560。

### 选框与标注

全部框来自同一个候选池。页面按固定顺序处理；v1.2 覆盖截止页之前的页面，v1.3 加入截止页之后的页面。

**1. 检测**：AnimeText YOLO12x 检测器，置信度 ≥ 0.425。嵌套框保留小框。全年龄页保留全部框；轻度敏感页随机保留最多 8 框。共得到约 21,500 个候选框，分布在 2,524 页。

**2. LLM 识别**：各识别器独立工作，看不到其他识别器的输出。提示词见[附录 A3](APPENDIX_zh.md#a3-三个-llm-识别器)。

| 识别器 | 任务 | 识别框数 |
|---|---|---|
| GPT-6.1 Sol | 全量 OCR；字体分类（印刷 / 手写 / 艺术字）；文字类型；初筛 | 21,305 |
| GPT-6 Astra | OCR；入库审核；文字类型；语言标注 | 约 11,900 |
| Claude Opus 5.5 | 最后复审：只看裁图做 OCR；文字类型；标记被框边裁断、混入其他文字或非正文的框 | 9,083 |

**3. 排除内容**（Sol 初筛与 Astra 入库审核）：

- 场景文字：店名、站名、路牌、招牌、海报。
- 正文以外的文字：广告、水印、署名、大标题。
- 超大装饰拟声字（例如巨大的「ドドド」）。
- 残缺文字：被遮挡、涂抹、褪色、涂黑或严重裁断。
- 非日文文字。

难认、生僻、变形的字，长文本，艺术字，以及识别器把握低，均不作为排除条件。

**4. 评测集规则**（适用于 v1.3 全部框）：

| 规则 | 删除 |
|---|---|
| 画在气泡外的拟声词和拟态词（三家文字类型标签多数票；保留 v1.2 对照原页做出的个别调整） | 不进入候选 |
| 标签含加在没有浊音形式的字上的浊点（如 あ゛、ん゛） | 16 框（v1.2 中 8 框，新增中 8 框） |
| 只有呻吟或加重、没有词义的框。候选：不含汉字，且含 ♡、小写元音、ゔ 或同一字符连写之一的框；逐框人工判断 | 8 框（v1.2 中 5 框，新增中 3 框） |

**5. 新增框的标签**

| 情况 | 标签 | 框数 |
|---|---|---|
| 三家读法归一化后相同，Opus 未标记 | 一致读法（取 Sol 的写法） | 4,232 |
| 读法不同（保留 232）；读法相同但被 Opus 标记（保留 151）；两者都有（保留 45） | 人工决定：选一家读法、手动输入或丢弃（丢弃 63） | 428（hard） |
| 从一致框中均匀随机抽样，人工复核 | 300/300 正确 | （含在 4,232 中） |

v1.2 的标签没有改动。审核界面只显示三家 LLM 读法，不显示任何 OCR 模型的输出。

**标签质量**：新增一致框抽检 300 个、0 错，其错误率的单侧 95% 上界为 0.99%（Clopper–Pearson）；v1.2 的抽检为 200 个、0 错（上界 1.49%）。未经人工逐框确认的 6,523 个标签仅经抽检。

### 板块

| 板块 | 定义 | 框数 |
|---|---|---|
| all | 全部框 | 7,789 |
| new | v1.3 新增的框 | 4,660 |
| v1.2 kept | 从 v1.2 保留下来的框 | 3,129 |
| hard | 读法不一致或被 Opus 标记、由人工定标签 | 784 |
| gold | 全部人工确认的框（hard + v1.2 与 v1.3 的随机抽检） | 1,266 |
| printed | 三家字体标签多数为印刷体 | 5,877 |
| non-printed | 手写、艺术字或混合 | 1,912 |

### 开发用途说明

作者把 Read v1.2（3,142 框）用作 manga-ocr-nar-small 及其前代模型的开发集，用于模型选择、对照实验和错误分析。第二个开发集“Sol 手写”（同一候选池中被 GPT-6.1 Sol 判为手写的 2,248 框，标签为 LLM 读法）自 2026-10-09 起用于训练中验证、数据与结构对照和错误分析；它与 v1.3 新增框重合 1,021 框，即 1,110 个新增非印刷框中的 1,004 框，另有 17 个印刷框。合成训练数据的设计参考了在候选池上测得的汇总统计（不含 v1.2 的页面）；这些页面包含 4,660 个新框所在的页面。相关统计公开在 [`docs/pool_stats/`](docs/pool_stats/)。候选池和评测集的图片均未用于训练。新框上的分数见[附录 A1](APPENDIX_zh.md#a1-各板块准确率)，其中非印刷部分大多与 Sol 手写集重合。manga-ocr-base-CPT-flex 使用与 manga-ocr-nar-small 相同的训练数据；训练期间有两个中间检查点在 Read v1.3 上评测过，仅用于监控，发布的权重是训练最后一步的权重。

## 评分

预测和标签使用同一套归一化规则 **RIN v1.1**（Reading-Invariant Normalization，阅读等价归一化）。RIN 合并不影响阅读内容的写法差异。

| 规则 | 示例 |
|---|---|
| 宽度统一（全角 ASCII 转半角，半角假名转全角） | `！` → `!`，`ﾃｽﾄ` → `テスト` |
| 删除空白 | `あ い` → `あい` |
| 连续省略点 → `…` | `・・・`、`...`、`……` → `…` |
| 长横线 → `ー`；连续 `ー` → 一个 `ー` | `──` → `ー` |
| 波浪号 → `〜`；连续 `〜` → 一个 `〜` | `～～` → `〜` |
| 引号统一为 `"` / `'` | `〝 〟` → `"` |
| 浊点、半浊点写法统一 | `う゛` → `ゔ`，`あ゙` → `あ゛` |
| 兼容符号（v1.3 新增 `⁇`、`⊠`） | `⁉` → `!?`，`⁇` → `??`，`⊠` → `☒` |
| 实心心号 → `♡`（v1.3.1 新增） | `♥`、`❤` → `♡` |

字符本身、小写假名、直角引号「」『』、`〇` 与 `○`、以及有无浊点均保持区分。标签使用 `♡`。RIN v1.1 等于 Read v1.2 的 `r7` 加上 v1.3 的两条符号规则和 v1.3.1 的心号规则；全部标签在 `r7`、RIN v1、RIN v1.1 下完全相同，规则只会改变预测一侧。`eval/normalize/rin.py` 保留 RIN v1（`normalize_rin_v1`），用于复现 v1.3 的数字。

**为什么用 RIN**：标签沿用识别器的写法，同一字形的写法并不统一，例如 `～` 有 326 框、`〜` 有 112 框，`…` 有 1,832 框、`・・` 连写有 260 框，`！` 有 868 框、`!` 有 560 框。一个对每个符号只用一种写法的模型，不做归一化就无法与全部标签一致。只做 NFKC 的完全匹配作为参考列出。

**指标**

- CER：编辑距离总和 / 标签总字数。
- EM：完全匹配的框所占比例。
- 综合分（排名指标）：1 − 归一化编辑距离（同 ICDAR 2019 ReCTS），印刷与非印刷等权平均：

$$s_i = 1 - \frac{\mathrm{ED}(p_i, g_i)}{\max(|p_i|, |g_i|)}$$

$$\text{综合分} = 100 \times \tfrac{1}{2}\left(\overline{s}_{\text{印刷}} + \overline{s}_{\text{非印刷}}\right)$$

## 测速

每个模型使用一张 RTX 2080 Ti（11 GB），全部模型使用 fp16（该卡没有高速 bf16）。每次运行绑定在 2× Xeon Gold 6148 主机的 8–10 个 CPU 核上，计算库线程数上限为 8；最多 4 个模型同时运行，每张卡一个。图片预先解码到内存。计时包含模型自带的预处理和解码，并做 GPU 同步。

| 指标 | 测法 |
|---|---|
| 逐张延迟 | batch = 1，单进程；预热后对全部 7,789 张裁图取平均 |
| 整页延迟 | 896 批，批大小按真实每页框数分布（平均 8.7、最大 45）；单进程，含预处理；取每批耗时 p50 |
| 最大吞吐 | 512 张裁图；4 个进程与 GPU 并行做预处理（主进程 3 个线程）；batch 搜到显存上限；最佳 batch 下 3 次取中位数 |
| 一次一页、第一框 | 见[附录 A2](APPENDIX_zh.md#a2-测速明细) |

Read v1.2 在 RTX 3080 Ti 上、按各模型默认精度测速，两个版本的速度不能直接比较。

GPU 空闲几秒后，驱动会降低频率，下一次请求会变慢（Hayai v2.5 Nova p384 空闲 20 s 后第一框由 51.5 ms 变为 81.7 ms）。所有模型都有这种情况，见[附录 A2](APPENDIX_zh.md#a2-测速明细)。

## 参评模型

| 模型 | 权重 | 设置 |
|---|---|---|
| manga-ocr-base-CPT-flex † | [muscgab/manga-ocr-base-CPT-flex](https://huggingface.co/muscgab/manga-ocr-base-CPT-flex) | 编码器 fp16、解码器 fp32；随模型发布的推理包的 CUDA 路径（CUDA 图） |
| manga-ocr-nar-small † | [muscgab/manga-ocr-nar-small](https://huggingface.co/muscgab/manga-ocr-nar-small) | fp16；随模型发布的推理代码 |
| manga-ocr-nar-small-distil † | [muscgab/manga-ocr-nar-small-distil](https://huggingface.co/muscgab/manga-ocr-nar-small-distil) | fp16 模拟 int8；随模型发布的推理代码 |
| e4 † | [muscgab/mangaocr-nar-looped-e4-exp](https://huggingface.co/muscgab/mangaocr-nar-looped-e4-exp) | fp16（训练代码）；解码器 1/2/3 圈 |
| LoopNAR-α † | 未发布 | fp16；解码器 1/2/3 圈 |
| Preview † | [muscgab/manga-ocr-nar-preview](https://huggingface.co/muscgab/manga-ocr-nar-preview) | fp16 |
| Hayai v2.1 | [JustANormalTinkerer/hayai-ocr-v2](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2)（main 分支 = v2.1） | 256 patch；贪心解码；fp16 |
| Hayai v2.5 Nova | [JustANormalTinkerer/hayai-ocr-v2.5-nova](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova) | 256 / 384 / 512 patch；其余同上 |
| PaddleOCR-VL-For-Manga | [jzhang533/PaddleOCR-VL-For-Manga](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga) | fp16；贪心解码；提示词 `OCR:`；批量推理使用逐图视觉注意力，每批最多 16 张 |
| baberuOCR v1.1 | [genshiai-daichi/baberu-ocr](https://huggingface.co/genshiai-daichi/baberu-ocr)（权重 = tag v1.1） | fp16；README 默认生成参数（最多 256 token） |
| mangaOCR | [kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base) | fp16；其余为 manga-ocr 包默认设置 |

同一输入下 fp16 与 fp32 的对比：Preview（260/260）、PaddleOCR-VL-For-Manga（65/65）、manga-ocr-nar-small（7,788/7,789）输出一致；LoopNAR-α L3 的 EM 为 83.61（fp16）与 83.62（fp32）（按 RIN v1 计）。其余模型未做对比。

## 利益关联声明

manga-ocr-nar-small、manga-ocr-nar-small-distil、manga-ocr-base-CPT-flex、e4、LoopNAR-α 和 Preview 是本评测集作者的模型。

- 标签来自三个第三方 LLM 和人工审核。审核界面只显示 LLM 读法，不显示任何 OCR 模型的输出。
- Read v1.2 在作者模型的开发中使用过（见[开发用途说明](#开发用途说明)）。v1.3 成形之前，有 1,021 个新框已在开发集中。选框和标签不使用任何 OCR 模型的输出。
- 公开全部模型预测、评分脚本和测速脚本。

## 局限

- 6,523 个标签为三家一致的 LLM 读法，仅经抽检。
- 人工审核时预填了多数读法。
- hard 板块按 LLM 分歧和标记定义。
- 拟声词按 LLM 文字类型标签排除；标为对白的框未逐框核对。
- 评测框经 LLM 筛选，被判为无法辨认的框未收录。
- 所有框都由同一个检测器（AnimeText YOLO12x）裁出，是紧贴文字的文字块。成绩不一定适用于其他裁法：整个气泡（气泡检测器）或单行文字。用 AnimeText 系裁图训练的模型（包括我们的模型和 Hayai）在训练中见过类似的裁法。
- 单一来源类型（近期同人与原创作品），单一显卡型号。
- 在最大吞吐 batch 下，输出与 batch = 1 一致的框占 99.6%–100%。

## 使用方法

```bash
pip install regex
python eval/score.py --pred my_preds.jsonl --name my_model --out results/my_model.json
```

`my_preds.jsonl`：每行一个框，`{"key": "10053471_0", "pred": "作戦を続行する"}`。缺少的 key 按空预测计。

| 位置 | 内容 |
|---|---|
| `data/gt.jsonl` | 7,789 框的标签和元数据 |
| `data/llm_readings.jsonl` | 每框的三家 LLM 读法 |
| `data/predictions/` | 榜单全部模型的输出（batch = 1 与整页；拟声词集在 `sfx_batch1/`） |
| `data/gt_sfx.jsonl` | v1.2 拟声词集（380 框），标签未改动；按 v1.3 设置的分数见[附录 A7](APPENDIX_zh.md#a7-拟声词集) |
| `eval/` | 评分脚本与 RIN 归一化代码 |
| `speed/` | 测速脚本 |
| [Hugging Face](https://huggingface.co/datasets/muscgab/JMangaBench_Read) | 原始分辨率裁图：`main/<key>.png`（split `test`） |

`gt.jsonl` 字段：`key`、`file`、`text`、`text_rin`、`n_chars`、`gold`、`gold_hard`、`gold_random_audit`、`printed`、`non_printed`、`font`、`role`、`orientation`、`crop_wh`、`page_id`、`box`、`rating`、`origin`（`v1.2` / `new`）、`review`。

仅用于评测，不得用于训练。

## 纠错

发现任何错误（标签错误、不该收录的框、评分或测速问题），欢迎[提 issue](https://github.com/muscgab/JMangaBench_Read/issues)。修正会进入下一版，并记录在[附录 A6](APPENDIX_zh.md#a6-版本记录)。

## 许可证

数据与代码均为 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)。

## 引用

```bibtex
@misc{jmangabench_read,
  title  = {JMangaBench\_Read: A Japanese Manga OCR Benchmark},
  year   = {2026},
  url    = {https://github.com/muscgab/JMangaBench_Read}
}
```
