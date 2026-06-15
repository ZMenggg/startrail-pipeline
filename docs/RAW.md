# RAW 处理与故障排查

## 推荐后端

最容易复现的安装方式：

```bash
python -m pip install -e '.[raw]'
startrail doctor --require-raw
```

自动模式只会选择通过可执行检查的 darktable；否则回退到 rawpy。要锁定后端：

```bash
startrail develop PROJECT --raw-backend rawpy
startrail develop PROJECT --raw-backend darktable --style STYLE_NAME
```

rawpy 提供一致的 16 位技术中间文件，但不会应用 darktable 样式。正式审美调色可在
堆栈后进行，或先修复 darktable 后端并使用统一样式。

## darktable 被找到但超时

如果 `doctor` 显示 `darktable-cli unusable: timed out`：

1. 直接启动一次 darktable，完成首次启动和权限确认。
2. 退出所有 darktable 进程后重新运行 `startrail doctor --require-raw`。
3. 仍然超时时使用 rawpy，或在 `project.toml` 指定另一份可工作的 CLI。

不要把 darktable 应用包中的单个二进制复制到项目目录。它依赖应用包内的动态库，
脱离原目录通常无法启动。

## RAW 代理图失败

代理图按以下顺序生成：

1. ExifTool 提取 `PreviewImage`；
2. 提取 `JpgFromRaw`；
3. 提取 `ThumbnailImage`；
4. rawpy 半尺寸解码。

全部失败时，分析记录写入 `proxy_missing`，完整流程会停止，避免使用全零指标伪装成
有效筛片结果。

## 中断与损坏 TIFF

显影写入隐藏的临时 TIFF，验证成功后才替换正式文件。恢复时：

- 完整 TIFF 直接复用；
- 不完整 TIFF 移入相邻的 `quarantine/`；
- 同一 RAW 会重新显影；
- `manifests/development.json` 记录复用或新生成状态。

不要手工删除 `quarantine/`，直到成品和备份均已确认。
