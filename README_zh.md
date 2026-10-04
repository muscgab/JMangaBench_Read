# JMangaBench_Read v1.2：日文漫画 OCR 评测集

[English](README.md) | [中文](README_zh.md) · [附录](APPENDIX_zh.md) · [交互式榜单](https://muscgab.github.io/JMangaBench_Read/) · [数据集（图片）](https://huggingface.co/datasets/muscgab/JMangaBench_Read)

JMangaBench_Read 评测 OCR 模型在日文漫画文字框裁图上的准确率和速度。主集收录读者要读、翻译流程要翻译的文字：台词、旁白和旁注。拟声词单独成集。

- 主集 3,142 个文字框，来自 732 页、732 位画师（每位画师一页）。拟声词集 380 框。
- 全部页面首次发布于 2025-10-01 至 2026-03-10。
- 标签来自三个 LLM 识别器和人工审核，主集中 547 框经人工确认。
- 在一张 RTX 3080 Ti 上测逐张延迟、整页延迟和最大吞吐。

发现标签、分数或文档有错误，欢迎[提 issue](https://github.com/muscgab/JMangaBench_Read/issues) 联系我们。

## 排行榜

按综合分排序（定义见[评分](#评分)）。主集 3,142 框，RTX 3080 Ti。

| # | 模型 | 架构 | 参数量 | 综合分 ↑ | CER % ↓ | EM % ↑ | 逐张延迟 ms ↓ | 整页延迟 ms（p50）↓ | 最大吞吐 张/秒 ↑ |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Hayai v2.5 Nova p512 | AR | 157M | **96.54** | 2.71 | 87.40 | 102.3 | 205.2 | 84（b192） |
| 2 | Hayai v2.5 Nova p384 | AR | 157M | **96.51** | 2.63 | 87.36 | 94.7 | 212.8 | 130（b192） |
| 3 | Hayai v2.5 Nova p256 | AR | 157M | **96.49** | 3.08 | 86.28 | 92.0 | 189.3 | 163（b256） |
| 4 | Hayai v2.1 | AR | 156M | **95.83** | 2.67 | 86.25 | 91.3 | 189.6 | 143（b320） |
| 5 | Preview † | NAR | 196M | **95.55** | 3.21 | 85.30 | 51.1 | 81.5 | 167（b20） |
| 6 | PaddleOCR-VL-For-Manga | AR（VLM） | 959M | **94.64** | 2.13 | 87.08 | 253.9 | — | 4.0（b1）§ |
| 7 | LoopNAR-α L2 † ‡ | NAR | 50M | **94.24** | 3.55 | 82.78 | 27.5 | 56.8 | — |
| 8 | LoopNAR-α L3 † ‡ | NAR | 50M | **94.13** | 3.50 | 82.46 | 32.5 | 62.6 | 239（b28） |
| 9 | LoopNAR-α L1 † ‡ | NAR | 50M | **93.88** | 4.07 | 81.51 | 22.5 | 52.1 | 268（b24） |
| 10 | baberuOCR | AR | 113M | **93.54** | 3.89 | 82.65 | 100.9 | 216.2 | 160（b256） |
| 11 | mangaOCR | AR | 111M | **90.13** | 5.01 | 78.04 | 66.5 | 206.0 | 46（b24） |

- † 本评测集作者的模型（见[利益关联声明](#利益关联声明)）。
- ‡ 开发中的试验模型。L1/L2/L3 为解码器循环圈数，权重相同。
- § 该模型批量推理输出无效，只测 batch = 1，无整页结果。
- 准确率各列用 batch = 1 的输出。整页批量推理下综合分变化不超过 0.09。
- 速度在全部 3,522 张裁图（主集和拟声词集）上测得。
- `bN`：最大吞吐对应的 batch 大小。
- 参数量取自公开权重文件；mangaOCR 按 fp32 权重文件大小估算。
- 按板块、长度、文字类型的明细，以及拟声词集上的分数，见[附录](APPENDIX_zh.md#a1-各板块准确率)。

### 准确率与速度

点击图片打开交互版（可切换板块：全部 / 印刷 / 非印刷 / gold / hard / 拟声词集）。

[![综合分与整页延迟](figures/pareto_page.png)](https://muscgab.github.io/JMangaBench_Read/)

[![综合分与逐张延迟](figures/pareto_image.png)](https://muscgab.github.io/JMangaBench_Read/)

从逐张推理改为整页推理，每框耗时：Preview（NAR）51.1 → 9.8 ms，Hayai v2.1（AR）91.3 → 24.2 ms。

## 数据

### 来源

独立画师在网上公开发布的黑白日文漫画页，为研究用途收集。来源类型与许可证与 [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText) 一致。

| 规则 | 内容 |
|---|---|
| 发布时间 | 2025-10-01 至 2026-03-10；作品首次发表于 2025 年 10 月或之后（按原帖编号估计） |
| 画师 | 每位画师一页，主集共 732 位 |
| 颜色 | 黑白 |
| 内容分级（主集） | 全年龄（2,514 框）、轻度敏感（628 框） |
| 语言 | 日文 |
| 排除画师 | 公开声明禁止转载或禁止 AI 使用的画师 |

### 与 AnimeText 的重合

两个集合的全部页面（739 页）均已核对。

- [AnimeText](https://huggingface.co/datasets/deepghs/AnimeText)：0 页。已核对全部 735,060 个图片 ID（train、valid、test），其中最新的图片发布于 2024-11-23。
- [animetext-ocr](https://huggingface.co/datasets/JustANormalTinkerer/animetext-ocr)：0 页。已核对全部 496,601 个来源图片 ID。

### 选框与标注

**1. 检测**：AnimeText YOLO12x 检测器，置信度 ≥ 0.425。嵌套框保留小框。全年龄页保留全部框；轻度敏感页随机保留最多 8 框。共得到约 21,500 个候选框，分布在 2,524 页。

**2. LLM 识别**：各识别器独立工作，看不到其他识别器的输出。合计用量约 6,600 万输入 token、530 万输出 token。

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

Sol 剔除 866 框、标记待审 634 框（原因可重叠：场景文字 309、超大拟声字 220、裁断 115、署名 107、大标题 42、广告 36）。Astra 另剔除约 100 框。非日文框去除 284 个。难认、生僻、变形的字，长文本，艺术字，以及识别器把握低，均不作为排除条件。提示词见[附录](APPENDIX_zh.md#a3-三个-llm-识别器)。

**4. 标签**

| 情况 | 标签 | 框数（主集） |
|---|---|---|
| 三家读法归一化后相同，Opus 未标记 | 一致读法 | 2,595 |
| 读法不同（259）；读法相同但被 Opus 标记（101）；早期归一化规则下读法不同（4） | 人工决定：选一家读法、手动输入或丢弃 | 364（hard） |
| 从一致框中均匀随机抽样，人工复核 | 200/200 正确（其中 183 框在主集） | 183 |

**5. 截止页**：页面按固定顺序处理。发布内容包含人工审核截止前已处理的 739 页上剩余的全部框。读法只差在小写假名上的框（如 ぁ / あ）被自动去除。

**6. 主集与拟声词集**

| 集合 | 内容 | 框数 |
|---|---|---|
| 主集 | 对话气泡和旁白框里的全部文字，包括感叹和叫声（えっ、うわっ、わんわん）；气泡外有词义的文字：喊名字、口头短句、作者旁注、（歓声）这类括号说明 | 3,142 |
| 拟声词集 | 画在画面上、气泡外的拟声词和拟态词（ズズッ、ぷいっ、わなわな），包括尖叫、喘息和悄悄话标记（ギャア、ゼェゼェ、ひそ） | 380 |

划分方法：三家文字类型标签的多数票把 381 框标为拟声词。对照原页后，其中 6 框留在主集（气泡外有词义的文字）；另有 5 个标为对白或其他的框移入拟声词集（气泡外的效果字）。拟声词集单独计分，不计入综合分。

**标签质量**：一致框抽检 200 个、0 错，一致框标签错误率的单侧 95% 上界为 1.49%（Clopper–Pearson），折合主集全部 3,142 个标签约 1.2%。另按识别器置信度分层抽检一致框 100 个，0 错（口头确认，未逐条记录）。

### 板块

| 板块 | 定义 | 框数 |
|---|---|---|
| all | 主集全部框 | 3,142 |
| hard | 读法不一致或被 Opus 标记、由人工定标签 | 364 |
| gold | 全部人工确认的框（hard + 抽检） | 547 |
| printed | 三家字体标签多数为印刷体 | 2,328 |
| non-printed | 手写、艺术字或混合 | 814 |
| 拟声词集 | 单独集合，不计入综合分 | 380 |

选框时按字体配额，非印刷体目标占 40%（印刷 6,000 / 手写 3,000 / 艺术字 1,000）。按 Sol 字体标签，筛选后候选池（15,877 框）中非印刷占 31.4%，主集中占 26.6%。

## 评分

预测和标签使用同一套归一化规则（`r7`）：

| 规则 | 示例 |
|---|---|
| 宽度统一（全角 ASCII 转半角，半角假名转全角） | `！` → `!`，`ﾃｽﾄ` → `テスト` |
| 删除空白 | `あ い` → `あい` |
| 连续省略点 → `…` | `・・・`、`...`、`……` → `…` |
| 长横线 → `ー`；连续 `ー` → 一个 `ー` | `──` → `ー` |
| 波浪号 → `〜`；连续 `〜` → 一个 `〜` | `～～` → `〜` |
| 引号统一为 `"` / `'` | `〝 〟` → `"` |
| 浊点、半浊点写法统一 | `う゛` → `ゔ`，`あ゙` → `あ゛` |

直角引号「」『』和小写假名保持原样。标签使用 `♡`，`♥` 不做转换。

**指标**

- CER：编辑距离总和 / 标签总字数。
- EM：完全匹配的框所占比例。
- 综合分（排名指标）：1 − 归一化编辑距离（同 ICDAR 2019 ReCTS），主集印刷与非印刷等权平均：

$$s_i = 1 - \frac{\mathrm{ED}(p_i, g_i)}{\max(|p_i|, |g_i|)}$$

$$\text{综合分} = 100 \times \tfrac{1}{2}\left(\overline{s}_{\text{印刷}} + \overline{s}_{\text{非印刷}}\right)$$

## 测速

一张 RTX 3080 Ti（12 GB）。各模型使用其 README 或代码中的默认精度。图片预先解码到内存。计时包含模型自带的预处理和解码，并做 GPU 同步。使用全部 3,522 张裁图。

| 指标 | 测法 |
|---|---|
| 逐张延迟 | batch = 1，单进程；预热后对全部裁图取平均 |
| 整页延迟 | 403 批，批大小按真实每页框数分布（平均 8.7、中位数 8、p90 15、最大 33）；单进程，含预处理；取每批耗时 p50 |
| 最大吞吐 | 512 张裁图；6 个进程并行预处理；batch 最大搜到 512；最佳 batch 下 3 次取中位数 |

## 参评模型

| 模型 | 权重 | 设置 |
|---|---|---|
| Preview † | [muscgab/manga-ocr-nar-preview](https://huggingface.co/muscgab/manga-ocr-nar-preview) | bf16 |
| LoopNAR-α † | 未发布 | bf16；解码器循环 1/2/3 圈 |
| Hayai v2.1 | [JustANormalTinkerer/hayai-ocr-v2](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2)（main 分支 = v2.1） | 256 patch；贪心解码；模型代码内置 fp16 autocast |
| Hayai v2.5 Nova | [JustANormalTinkerer/hayai-ocr-v2.5-nova](https://huggingface.co/JustANormalTinkerer/hayai-ocr-v2.5-nova) | 256 / 384 / 512 patch；其余同上 |
| PaddleOCR-VL-For-Manga | [jzhang533/PaddleOCR-VL-For-Manga](https://huggingface.co/jzhang533/PaddleOCR-VL-For-Manga) | bf16；贪心解码；提示词 `OCR:` |
| baberuOCR | [genshiai-daichi/baberu-ocr](https://huggingface.co/genshiai-daichi/baberu-ocr) | bf16（CUDA 默认）；README 默认生成参数 |
| mangaOCR | [kha-white/manga-ocr-base](https://huggingface.co/kha-white/manga-ocr-base) | fp32；manga-ocr 包默认设置 |

三个 LLM 识别器的分数列于附录，仅供参考，不参与排名。

## 利益关联声明

Preview 和 LoopNAR-α 是本评测集作者的模型。

- 标签来自三个第三方 LLM 和人工审核。审核界面只显示 LLM 读法，不显示任何 OCR 模型的输出。
- 评测框在任何 OCR 模型打分之前确定。之后的改动：v1.1 修正 5 个误存为空的标签（3 个补字，2 个删除）；v1.2 在分数已知后把拟声词移入单独集合，划分只依据框的内容和位置，各模型分数变化列于[附录 A6](APPENDIX_zh.md#a6-版本记录)。
- 公开全部模型预测、评分脚本和测速脚本。

## 局限

- 主集中 2,595 个标签为三家一致的 LLM 读法，仅经抽检。
- 人工审核时预填了多数读法。
- hard 板块按 LLM 分歧和标记定义。
- 主集与拟声词集的划分依赖 LLM 文字类型标签。标为对白的框只用文字规则筛查过拟声词（标出 124 框，对照原页看了 17 框），未逐框核对。
- 评测框经 LLM 筛选，被判为无法辨认的框未收录。
- 单一来源类型，近期同人与原创作品，单一显卡。
- 在最大吞吐 batch 下，输出与 batch = 1 一致的框占 96.9%–100%。

## 使用方法

```bash
pip install regex
python eval/score.py --pred my_preds.jsonl --name my_model --out results/my_model.json
python eval/score.py --pred my_preds.jsonl --gt data/gt_sfx.jsonl --name my_model   # 拟声词集
```

`my_preds.jsonl`：每行一个框，`{"key": "10053471_0", "pred": "作戦を続行する"}`。缺少的 key 按空预测计。一个预测文件可同时覆盖两个集合。

| 位置 | 内容 |
|---|---|
| `data/gt.jsonl` | 主集 3,142 框的标签和元数据 |
| `data/gt_sfx.jsonl` | 拟声词集 380 框 |
| `data/llm_readings.jsonl` | 每框的三家 LLM 读法，两个集合 |
| `data/predictions/` | 榜单全部模型在两个集合上的输出（batch = 1 与整页） |
| `eval/` | 评分脚本与归一化代码 |
| [Hugging Face](https://huggingface.co/datasets/muscgab/JMangaBench_Read) | 原始分辨率裁图：`main/<key>.png`（split `test`），`sfx/<key>.png`（split `sfx`） |

`gt.jsonl` 字段：`key`、`file`、`text`、`text_r7`、`n_chars`、`gold`、`gold_hard`、`gold_random_audit`、`printed`、`non_printed`、`font`、`role`、`orientation`、`crop_wh`、`page_id`、`box`、`rating`。

仅用于评测，不得用于训练。

## 纠错

发现任何错误（标签错误、框该归入另一个集合、评分或测速问题），欢迎[提 issue](https://github.com/muscgab/JMangaBench_Read/issues)。修正会进入下一版，并记录在[附录 A6](APPENDIX_zh.md#a6-版本记录)。

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
