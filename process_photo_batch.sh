#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PHOTO_ROOT=${STARTRAIL_PHOTO_ROOT:-"$ROOT/photos"}
INPUT="$PHOTO_ROOT/input"
COMPLETED="$PHOTO_ROOT/completed"
MODE=new
ACCEPT_REVIEW=no
GROUP_NAME=
RESUME_TARGET=
OVERRIDE=

while [ "$#" -gt 0 ]; do
  case "$1" in
    --resume)
      MODE=resume
      shift
      RESUME_TARGET=${1:-}
      if [ -z "$RESUME_TARGET" ]; then
        echo "--resume 需要批次目录"
        exit 2
      fi
      ;;
    --accept-review)
      ACCEPT_REVIEW=yes
      ;;
    --override)
      shift
      OVERRIDE=${1:-}
      if [ -z "$OVERRIDE" ]; then
        echo "--override 需要 CSV 文件路径"
        exit 2
      fi
      ;;
    -*)
      echo "未知参数：$1"
      exit 2
      ;;
    *)
      if [ -n "$GROUP_NAME" ]; then
        echo "只能指定一个组名"
        exit 2
      fi
      GROUP_NAME=$1
      ;;
  esac
  shift
done

if [ "$MODE" = resume ]; then
  if [ -n "$GROUP_NAME" ]; then
    echo "恢复批次时不能再指定组名"
    exit 2
  fi
  case "$RESUME_TARGET" in
    /*) BATCH=$RESUME_TARGET ;;
    *) BATCH="$COMPLETED/$RESUME_TARGET" ;;
  esac
  WORK="$BATCH/_work"
else
  GROUP_NAME=${GROUP_NAME:-startrail}
  SAFE_NAME=$(printf '%s' "$GROUP_NAME" | tr ' /:*?"<>|' '_________')
  STAMP=$(date '+%Y%m%d-%H%M%S')
  BATCH="$COMPLETED/${STAMP}_${SAFE_NAME}"
  WORK="$BATCH/_work"
fi

mkdir -p "$INPUT" "$COMPLETED"

if [ "$MODE" = new ]; then
  if ! find "$INPUT" -type f ! -name '.gitkeep' -print -quit | grep -q .; then
    echo "没有找到照片。请把当前一组照片放入："
    echo "  $INPUT"
    exit 1
  fi
  if [ -e "$BATCH" ]; then
    echo "批次目录已存在：$BATCH"
    exit 1
  fi
else
  if [ ! -d "$BATCH/originals" ] || [ ! -d "$WORK" ]; then
    echo "不是可恢复的批次目录：$BATCH"
    exit 1
  fi
  if [ "$(cat "$BATCH/STATUS.txt" 2>/dev/null || true)" = complete ]; then
    echo "该批次已经完成：$BATCH"
    exit 1
  fi
fi

if [ -n "${STARTRAIL_PYTHON:-}" ]; then
  PYTHON="$STARTRAIL_PYTHON"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON=python3
fi

if ! "$PYTHON" -c "import numpy, PIL, tifffile" >/dev/null 2>&1; then
  echo "Python 图像依赖尚未安装。请先在项目目录运行："
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/python -m pip install -e ."
  exit 1
fi

if [ "$MODE" = new ]; then
  mkdir -p "$BATCH"
  mv "$INPUT" "$BATCH/originals"
  mkdir -p "$INPUT"
  : > "$INPUT/.gitkeep"
fi

echo "批次：$(basename "$BATCH")"
echo "原片已归档到：$BATCH/originals"

printf 'checking\n' > "$BATCH/STATUS.txt"
FINISHED=no
on_exit() {
  STATUS=$(cat "$BATCH/STATUS.txt" 2>/dev/null || true)
  if [ "$FINISHED" != yes ] && [ "$STATUS" = checking ]; then
    printf 'failed\n' > "$BATCH/STATUS.txt"
  elif [ "$FINISHED" != yes ] && [ "$STATUS" = running ]; then
    printf 'interrupted\n' > "$BATCH/STATUS.txt"
  fi
}
trap on_exit EXIT HUP INT TERM

if find "$BATCH/originals" -type f \
  \( -iname '*.cr2' -o -iname '*.cr3' -o -iname '*.nef' \
  -o -iname '*.arw' -o -iname '*.dng' -o -iname '*.orf' \
  -o -iname '*.rw2' -o -iname '*.raf' \) -print -quit | grep -q .; then
  "$PYTHON" -m startrail_pipeline doctor --project "$WORK" --require-raw
fi

printf 'running\n' > "$BATCH/STATUS.txt"

set +e
set -- "$PYTHON" -m startrail_pipeline run \
  "$WORK" \
  --source "$BATCH/originals"
if [ "$MODE" = resume ]; then
  set -- "$@" --resume
fi
if [ "$ACCEPT_REVIEW" = yes ]; then
  set -- "$@" --accept-review
fi
if [ -n "$OVERRIDE" ]; then
  set -- "$@" --override "$OVERRIDE"
fi
"$@"
RUN_STATUS=$?
set -e

if [ "$RUN_STATUS" -ne 0 ]; then
  printf 'failed\n' > "$BATCH/STATUS.txt"
  FINISHED=yes
  echo "处理失败，但本组原片已安全保存在：$BATCH/originals"
  echo "日志：$WORK/logs/pipeline.log"
  exit "$RUN_STATUS"
fi

if [ ! -f "$WORK/stacks/stack.tif" ]; then
  sed 's#\.\./proxies/#_work/proxies/#g' \
    "$WORK/manifests/contact_sheet.html" > "$BATCH/review.html"
  cp "$WORK/manifests/selection.csv" "$BATCH/selection.csv"
  printf 'needs-review\n' > "$BATCH/STATUS.txt"
  FINISHED=yes
  echo "本组尚未生成星轨，请查看：$BATCH/review.html"
  exit 1
fi

if [ -e "$BATCH/startrail.tif" ] || [ -e "$BATCH/preview.jpg" ]; then
  printf 'failed\n' > "$BATCH/STATUS.txt"
  FINISHED=yes
  echo "批次顶层输出已存在，拒绝覆盖：$BATCH"
  exit 1
fi
ln "$WORK/stacks/stack.tif" "$BATCH/startrail.tif"
ln "$WORK/stacks/preview.jpg" "$BATCH/preview.jpg"
sed 's#\.\./proxies/#_work/proxies/#g' \
  "$WORK/manifests/contact_sheet.html" > "$BATCH/review.html"
cp "$WORK/manifests/selection.csv" "$BATCH/selection.csv"
printf 'complete\n' > "$BATCH/STATUS.txt"
FINISHED=yes

echo
echo "处理完成："
echo "  星轨母版：$BATCH/startrail.tif"
echo "  快速预览：$BATCH/preview.jpg"
echo "  筛片报告：$BATCH/review.html"
echo
echo "导入目录已经清空，可以放入下一组照片："
echo "  $INPUT"
