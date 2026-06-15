# AI Agent 专用操作手册

本手册用于指导推理能力有限的 AI Agent 安全使用本项目。执行任务时，优先遵守
本文件和 `AGENTS.md`。不要凭经验省略步骤，不要猜测文件路径，不要自行删除文件。

## 1. 任务目标

本项目把一组星轨照片处理成：

- `startrail.tif`：16 位星轨母版，主要成品；
- `preview.jpg`：快速查看用 JPEG，不是母版；
- `review.html`：人工检查照片质量的页面；
- `selection.csv`：每张照片的筛选结果；
- `STATUS.txt`：批次状态。

每组照片必须使用独立批次。新批次不会使用上一批的中间文件。

普通照片处理只使用 `process_photo_batch.sh`。不要直接使用
`startrail run`、`inventory`、`develop` 或 `stack`，因为入口脚本还负责创建独立批次、
维护 `STATUS.txt` 和发布成品。只有开发、测试或用户明确要求分步执行时才使用底层命令。

## 2. 固定路径

先找到同时包含 `pyproject.toml`、`process_photo_batch.sh` 和
`startrail_pipeline/` 的目录。这个目录就是项目根目录。

进入项目根目录后执行：

```bash
cd "/实际的项目根目录"
test -f pyproject.toml
test -f process_photo_batch.sh
test -d startrail_pipeline
```

三个 `test` 命令都必须成功。不要照抄示例中的占位路径。

重要目录：

```text
photos/input/       当前待处理的一组照片
photos/completed/   每组照片的独立批次和成品
.venv/              Python 虚拟环境
```

不要把照片放入项目源码目录、`.venv/` 或其他批次的 `_work/`。

## 3. 绝对安全规则

AI Agent 必须遵守以下规则：

1. 不删除、修改或原地重命名 RAW、TIFF、PNG、JPEG 原片。
2. 不运行 `rm`、`find -delete`、`git clean`、`git reset --hard`。
3. 不清空 `photos/input/` 或 `photos/completed/`。
4. 不手工移动 `photos/completed/*/originals/` 中的文件。
5. 不同时把多组拍摄序列放进 `photos/input/`。
6. 不默认使用 `--force`。只有用户明确要求覆盖时才能使用。
7. 不默认使用 `--accept-review`。必须先让用户查看异常帧，或得到用户明确同意。
8. 不手工删除 `_work/developed/quarantine/`、manifest 或 checkpoint。
9. 不调用 Lightroom、Photoshop、darktable GUI 等图形程序。
10. 不把照片、日志、EXIF、用户名、绝对路径或批次数据提交到 Git。
11. 命令失败后先读取状态和日志，不要反复创建新批次。
12. 不确定时停止操作，报告已知信息并询问用户。

注意：新批次启动时，入口脚本会把整个 `photos/input/` 移动到新批次的
`originals/`。这不是删除，但用户仍应在其他磁盘保留原片备份。

## 4. 每次任务的固定检查

如果 `.venv/bin/startrail` 不存在，这是未安装状态。先报告需要安装依赖；得到用户
同意后执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[raw]'
```

安装完成后再继续。不要把 `.venv/` 提交到 Git。

先执行：

```bash
pwd
git status --short
df -h .
.venv/bin/startrail doctor
find photos/input -type f ! -name '.gitkeep' -print | head -20
find photos/completed -mindepth 1 -maxdepth 1 -type d -print | sort
find photos/completed -mindepth 2 -maxdepth 2 -name STATUS.txt -exec \
  sh -c 's=$(cat "$1"); case "$s" in checking|running) echo "$1: $s";; esac' _ {} \;
```

检查结果：

- `pwd` 必须是项目根目录。
- `photos/input/` 没有照片：不能启动新批次。
- `photos/input/` 有照片：询问或确认这些照片只属于同一组。
- Git 有用户未提交修改：不得覆盖或还原这些修改。
- 磁盘剩余空间不足或无法判断是否充足：不要开始处理。
- 其他批次状态为 `checking` 或 `running`：不要启动新批次。
- RAW 处理前还要执行 `.venv/bin/startrail doctor --require-raw`。

常见 RAW 扩展名：

```text
CR2 CR3 NEF ARW DNG ORF RW2 RAF
```

## 5. 决策流程

严格按以下顺序选择一个分支，不要同时执行多个分支。

### 分支 A：处理一组新照片

条件：

- 用户要求处理新照片；
- `photos/input/` 中有且只有一组照片；
- 用户给出了组名，或允许使用简单组名。

先检查文件数量和扩展名：

```bash
find photos/input -type f ! -name '.gitkeep' | wc -l
find photos/input -type f ! -name '.gitkeep' -print | \
  sed 's/.*\.//' | tr '[:lower:]' '[:upper:]' | sort | uniq -c
```

如果包含 RAW：

```bash
.venv/bin/startrail doctor --require-raw
```

检查通过后，只运行一次：

```bash
./process_photo_batch.sh "用户提供的组名"
```

不要在命令运行期间启动第二个批次。

### 分支 B：恢复中断或失败的批次

先列出状态：

```bash
find photos/completed -mindepth 2 -maxdepth 2 -name STATUS.txt -exec \
  sh -c 'printf "%s: " "$(basename "$(dirname "$1")")"; cat "$1"' _ {} \;
```

用户必须指定准确批次名。恢复命令：

```bash
./process_photo_batch.sh --resume "准确的批次目录名"
```

示例：

```bash
./process_photo_batch.sh --resume "20260615-220000_山顶星轨"
```

不要用最新目录代替用户指定的目录，不要恢复状态为 `complete` 的批次。

### 分支 C：批次需要人工复核

当 `STATUS.txt` 为 `needs-review` 时：

1. 不要立即接受全部异常帧。
2. 告诉用户打开该批次的 `review.html`。
3. 读取 `selection.csv`，统计 `keep`、`review` 和 `reject_candidate`。
4. 等待用户决定。

统计命令：

```bash
.venv/bin/python -c '
import csv, sys
from collections import Counter
with open(sys.argv[1], newline="", encoding="utf-8") as f:
    print(Counter(row["decision"] for row in csv.DictReader(f)))
' "photos/completed/批次名/selection.csv"
```

推荐方式是创建人工 override CSV：

```csv
relative_path,decision
frame_0001.CR3,keep
frame_0002.CR3,reject_candidate
```

然后恢复：

```bash
./process_photo_batch.sh --resume "批次名" \
  --override "/绝对路径/override.csv"
```

只有用户明确要求“接受所有待复核照片”时，才运行：

```bash
./process_photo_batch.sh --resume "批次名" --accept-review
```

### 分支 D：处理星轨短断点

`gap-fill` 是可选修饰，不是默认堆栈步骤。必须保留原始 `startrail.tif`。

仅在用户确认断点短且规律后执行，并使用新的输出文件名：

```bash
.venv/bin/startrail gap-fill \
  "photos/completed/批次名/startrail.tif" \
  "photos/completed/批次名/startrail-gap-filled.tif"
```

禁止让输入和输出使用同一路径。当前项目没有针对 Gap Fill 输出的独立 JPEG
预览命令，因此只报告新 TIFF 路径，不要临时发明图像转换命令。如果断点很长、
方向不确定或包含云层和地景边缘，不要自动填补。

### 分支 E：只检查项目，不处理照片

执行：

```bash
.venv/bin/startrail doctor
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
sh -n process_photo_batch.sh
sh -n run_photo_test.sh
git status --short
```

测试使用合成图片，不会处理真实照片。

## 6. 状态解释

读取：

```bash
cat "photos/completed/批次名/STATUS.txt"
```

状态含义：

| 状态 | 含义 | AI 下一步 |
| --- | --- | --- |
| `checking` | 正在环境检查 | 等待当前命令完成 |
| `running` | 正在处理 | 不启动其他批次 |
| `interrupted` | 处理被中断 | 使用 `--resume` |
| `needs-review` | 有照片需人工判断 | 查看报告，等待用户决定 |
| `failed` | 处理失败 | 读取日志，修复原因后恢复 |
| `complete` | 已完成 | 验证成品，不再恢复或覆盖 |

没有 `STATUS.txt` 的目录不能自动当成完成批次，也不能自动删除。

## 7. 成功验证

命令结束后执行：

```bash
BATCH="photos/completed/准确的批次目录名"
cat "$BATCH/STATUS.txt"
ls -lh "$BATCH"
test -s "$BATCH/startrail.tif"
test -s "$BATCH/preview.jpg"
test -s "$BATCH/review.html"
test -s "$BATCH/selection.csv"
```

只有同时满足以下条件，才能向用户报告“处理完成”：

- `STATUS.txt` 内容为 `complete`；
- `startrail.tif` 存在且非空；
- `preview.jpg` 存在且非空；
- `review.html` 和 `selection.csv` 存在且非空。

`preview.jpg` 只是预览。最终高位深成品是 `startrail.tif`。

完成后，`photos/input/` 应只剩 `.gitkeep`，可以放入下一组照片。

## 8. 失败排查

先读取最后 100 行日志：

```bash
tail -100 "photos/completed/批次名/_work/logs/pipeline.log"
```

然后按错误类型处理：

### 找不到照片

- 检查照片是否在 `photos/input/`；
- 检查是否误放在子项目或其他批次；
- 不要自行从旧批次复制照片。

### RAW 后端不可用

执行：

```bash
.venv/bin/startrail doctor --require-raw
```

优先修复 `rawpy` 或正确安装的 `darktable-cli`。不要把 darktable 应用包中的单个
二进制复制到项目根目录。

### RAW 代理图失败

自动分析没有可靠图像数据，流程会停止。不要绕过检查或伪造分析结果。检查
ExifTool、rawpy、文件完整性和日志。

### 磁盘空间不足

停止处理并通知用户释放空间。不要删除原片、隔离文件、旧批次或母版来腾空间。

### TIFF 损坏

使用原批次的 `--resume`。程序会把损坏中间文件移入 `quarantine/` 并重新显影。
不要手工删除或替换中间 TIFF。

### 输出已存在

默认拒绝覆盖是正常保护行为。不要自行添加 `--force`。先确认是否选错批次，
然后请用户决定是否覆盖。

## 9. 低智能 Agent 的输出模板

开始处理前：

```text
已确认项目目录、输入照片数量和文件类型。本次将创建一个新的独立批次：
<批次组名>。不会删除或覆盖原片。
```

需要复核时：

```text
流程已暂停，批次状态为 needs-review。
请查看：<review.html 的路径>
待复核照片：<数量>
我没有自动接受或删除这些照片。
```

处理完成时：

```text
批次状态：complete
16 位母版：<startrail.tif 的路径>
快速预览：<preview.jpg 的路径>
筛片报告：<review.html 的路径>
输入目录已可用于下一组照片。
```

处理失败时：

```text
批次状态：failed
原片位置：<originals 目录>
日志位置：<pipeline.log 路径>
失败原因：<日志中的具体错误>
未删除、覆盖或重新创建批次。
```

## 10. Agent 最小检查清单

每次结束前逐项确认：

- [ ] 我在正确的项目根目录执行命令。
- [ ] 我没有删除、覆盖或修改原片。
- [ ] 我没有混合两组照片。
- [ ] 我没有擅自使用 `--force`。
- [ ] 我没有擅自使用 `--accept-review`。
- [ ] 我读取了 `STATUS.txt`，没有仅凭命令退出码判断成功。
- [ ] 我验证了最终文件存在且非空。
- [ ] 我向用户报告了准确批次名、状态、母版和日志路径。
