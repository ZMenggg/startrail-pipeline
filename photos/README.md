# 照片批次目录

每次只把一组照片放进 `photos/input/`：

```bash
./process_photo_batch.sh 组名
```

程序会将原片整体移动到新的 `photos/completed/时间_组名/originals/`，随后重新
创建空的导入目录。不同批次不会共享代理图、显影结果或堆栈检查点。

默认不会自动接受异常帧。状态变为 `needs-review` 后查看批次中的
`review.html`，确认后运行：

```bash
./process_photo_batch.sh --resume 批次目录名 --accept-review
```

也可以通过 `--override /path/to/override.csv` 只接受或排除指定照片。

处理意外中断时直接恢复：

```bash
./process_photo_batch.sh --resume 批次目录名
```

`STATUS.txt` 可能包含：

- `checking`：正在检查依赖和 RAW 后端；
- `running`：处理进行中；
- `interrupted`：进程被中止，可以恢复；
- `needs-review`：等待人工确认异常帧；
- `failed`：发生错误，查看 `_work/logs/pipeline.log`；
- `complete`：成品已发布到批次顶层。

不要把真实照片提交到 Git。仓库的 `.gitignore` 已忽略 `photos/input/` 和
`photos/completed/` 中的内容。
