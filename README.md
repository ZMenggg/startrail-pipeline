# 星轨摄影自动后期流程

面向 macOS 的安全、可恢复星轨批处理工具。它保护 RAW 原片，生成可审计的
JSON/CSV 清单，将选中的 RAW 统一显影为 16 位 TIFF，并逐帧进行最大值堆栈。

当前版本为 `0.2.0`，仍处于 Alpha 阶段。首次处理重要素材前，请保留独立备份。

## 核心原则

- 原片只读，不自动删除、改名或覆盖。
- 每组照片使用独立批次目录，不继承上一组的中间数据。
- RAW 代理图必须成功生成，否则禁止自动筛片和堆栈。
- 显影先写临时文件，验证为完整的 16 位 RGB TIFF 后再原子落盘。
- 损坏的中间 TIFF 会移入 `quarantine/`，不会静默跳过。
- 堆栈逐张读取，适合 Apple Silicon 16 GB 内存机器。
- manifest、检查点和最终 TIFF 均采用可恢复写入方式。

## 安装

需要 Python 3.11+。RAW 用户推荐安装 `rawpy` 可选依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[raw]'
```

建议安装 ExifTool，用于 EXIF 和 RAW 内嵌预览提取：

```bash
brew install exiftool
```

也支持 `darktable-cli`。程序依次检查：

1. `project.toml` 中的 `raw_developer.executable`
2. 环境变量 `STARTRAIL_DARKTABLE_CLI`
3. `PATH`
4. `/Applications/darktable.app/Contents/MacOS/darktable-cli`

运行发布前检查：

```bash
.venv/bin/startrail doctor --require-raw
```

## 每组照片的简单流程

把当前一组照片放入：

```text
photos/input/
```

然后运行：

```bash
./process_photo_batch.sh 山顶星轨
```

程序将原片归档到新的批次目录。出现异常帧时，默认状态为
`needs-review`，请查看 `review.html`。确认整组都可以使用后，可显式接受复核帧：

```bash
./process_photo_batch.sh --resume 20260615-220000_山顶星轨 --accept-review
```

更稳妥的方式是编辑 override CSV，只裁决需要人工检查的照片：

```csv
relative_path,decision
frame_0001.RAW,keep
frame_0002.RAW,reject_candidate
```

然后恢复：

```bash
./process_photo_batch.sh --resume 20260615-220000_山顶星轨 \
  --override /path/to/override.csv
```

普通中断也使用同一恢复命令，但不需要 `--accept-review`：

```bash
./process_photo_batch.sh --resume 20260615-220000_山顶星轨
```

恢复时会：

- 重用已经生成并验证通过的代理图和 TIFF；
- 隔离损坏或不完整的 TIFF 后重新显影；
- 使用兼容的堆栈检查点；
- 已有完整堆栈时直接进入批次成品发布步骤。

## RAW 处理流程

1. `inventory`：记录路径、EXIF、大小、修改时间和 SHA-256。
2. `preview`：优先提取 RAW 内嵌 JPEG；失败时使用 `rawpy`。
3. `analyze`：分析代理图亮度、高光裁切和清晰度。
4. `select`：生成 `keep/review/reject_candidate` 清单。
5. `develop`：优先选择可工作的 darktable，否则回退到 rawpy。
6. `stack`：验证 TIFF 后按清单顺序流式最大值堆栈。
7. 输出 16 位母版、JPEG 预览及完整处理报告。

`rawpy` 回退模式不支持 darktable 样式。如果需要固定的审美调色、镜头配置或
ICC 工作流，应先建立 darktable 样式，并明确使用 `--raw-backend darktable`。

## 命令

```text
startrail init PROJECT
startrail inventory PROJECT --source DIR
startrail preview PROJECT
startrail analyze PROJECT
startrail select PROJECT [--override CSV]
startrail develop PROJECT [--raw-backend auto|darktable|rawpy] [--style NAME]
startrail stack PROJECT [--mask FILE] [--resume]
startrail run PROJECT --source DIR [--override CSV] [--resume] [--accept-review]
startrail gap-fill INPUT OUTPUT
startrail doctor [--project PROJECT] [--require-raw]
```

所有命令支持 `--help`。覆盖已有有效输出必须显式使用 `--force`。

## 批次目录

```text
photos/completed/时间_组名/
  originals/             # 原片，只读使用
  startrail.tif          # 最终 16 位星轨母版
  preview.jpg            # 快速预览
  review.html            # 带缩略图的分析联系表
  selection.csv          # 最终选片结论
  STATUS.txt             # checking/running/interrupted/needs-review/failed/complete
  _work/
    project.toml
    proxies/
    developed/
      quarantine/
    manifests/
      inventory.json
      analysis.json
      selection.json
      development.json
      stack.json
    stacks/
    logs/pipeline.log
```

## 配置示例

```toml
[raw_developer]
backend = "auto"
executable = ""
style_name = ""
estimated_tiff_size_ratio = 6.5
disk_reserve_gb = 10

[analysis]
proxy_size = 1024
mad_multiplier_low = 3.0
mad_multiplier_high = 5.0

[checkpoint]
interval_frames = 50
```

显影前会根据 RAW 总大小估算剩余 TIFF 空间，并保留配置的磁盘余量。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q startrail_pipeline tests
sh -n process_photo_batch.sh run_photo_test.sh
```

测试只使用临时目录和合成图，不依赖仓库中的真实照片。

更完整的摄影处理原则见 [docs/WORKFLOW.md](docs/WORKFLOW.md)，RAW 后端问题见
[docs/RAW.md](docs/RAW.md)。
