# Startrail Pipeline

English | [简体中文](README.md)

Startrail Pipeline is a safe, resumable, RAW-first command-line workflow for
processing large star-trail photo sequences on macOS. It preserves source
photographs, records every automated decision in machine-readable manifests,
develops selected RAW frames into validated 16-bit TIFF files, and performs
memory-efficient maximum-value stacking one frame at a time.

> Current version: `0.2.0` (Alpha). Keep an independent backup before processing
> important photographs.

## Highlights

- Treats source photographs as read-only archival assets.
- Isolates every photo sequence in its own batch directory.
- Extracts embedded RAW previews with ExifTool and falls back to `rawpy`.
- Stops safely when RAW previews cannot be analyzed.
- Supports `darktable-cli` and `rawpy` RAW development backends.
- Writes TIFFs, manifests, checkpoints, and final stacks atomically.
- Validates existing 16-bit TIFF files before reusing them.
- Quarantines interrupted or corrupt intermediate files instead of deleting them.
- Provides conservative quality analysis with explicit human review.
- Resumes RAW development and stacking after interruption.
- Streams frames during stacking for practical use on 16 GB Apple Silicon Macs.

## Pipeline

```text
archive source frames
  -> inventory (EXIF, SHA-256, deterministic ordering)
  -> preview (embedded JPEG or rawpy)
  -> analyze (luminance, clipping, sharpness)
  -> select (keep / review / reject_candidate)
  -> develop (validated 16-bit TIFF)
  -> stack (streaming maximum blend)
  -> startrail.tif + preview.jpg + reports
```

## Installation

Python 3.11 or newer is required. The recommended setup for RAW processing is:

```bash
git clone https://github.com/ZMenggg/startrail-pipeline.git
cd startrail-pipeline
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[raw]'
brew install exiftool
```

Verify the environment:

```bash
.venv/bin/startrail doctor --require-raw
```

The RAW developer is selected in this order:

1. `raw_developer.executable` in `project.toml`
2. `STARTRAIL_DARKTABLE_CLI`
3. `darktable-cli` available on `PATH`
4. the standard macOS darktable application path
5. `rawpy` fallback

## Quick Start

Place exactly one photo sequence in:

```text
photos/input/
```

Run:

```bash
./process_photo_batch.sh mountain-trails
```

Each run creates an isolated directory:

```text
photos/completed/TIMESTAMP_NAME/
  originals/       archived source photographs
  startrail.tif    final 16-bit master
  preview.jpg      quick preview
  review.html      visual frame-analysis report
  selection.csv    frame decisions
  STATUS.txt       batch state
  _work/           manifests, proxies, TIFFs, checkpoints, and logs
```

If frames require review, the batch stops with `needs-review`. After checking
`review.html`, either accept every review frame:

```bash
./process_photo_batch.sh --resume BATCH_NAME --accept-review
```

or provide explicit decisions:

```csv
relative_path,decision
frame_0001.RAW,keep
frame_0002.RAW,reject_candidate
```

```bash
./process_photo_batch.sh --resume BATCH_NAME \
  --override /path/to/override.csv
```

Resume an interrupted batch with:

```bash
./process_photo_batch.sh --resume BATCH_NAME
```

## RAW Safety

RAW previews are extracted from embedded JPEG data when possible. If that
fails, `rawpy` performs a reduced-size decode. The pipeline refuses to continue
when neither method can produce an analyzable preview.

Developed frames are first written to hidden temporary files. A file becomes a
normal intermediate TIFF only after its bit depth, dimensions, and RGB channel
layout have been validated. Invalid files are moved to `quarantine/` and
rebuilt during the next run.

The `rawpy` backend provides a consistent technical development path but does
not apply darktable styles. Use a working darktable backend when a synchronized
style, lens profile, or color-managed development recipe is required.

## Commands

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

Every command supports `--help`. Existing valid outputs are never overwritten
unless `--force` is explicitly supplied.

## Scope

The CLI currently implements archival inventory, proxy generation, objective
frame analysis, reversible selection, RAW development, streaming maximum
stacking, checkpoints, masks, reports, and optional short-gap filling.

Subjective color grading, advanced aircraft removal, foreground blending,
master-dark calibration, and final print preparation remain intentional human
checkpoints or external editing tasks.

## Documentation

- [Project Wiki](https://github.com/ZMenggg/startrail-pipeline/wiki)
- [RAW troubleshooting](docs/RAW.md)
- [Complete photography workflow](docs/WORKFLOW.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)

## Testing

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q startrail_pipeline tests
sh -n process_photo_batch.sh run_photo_test.sh
```

Tests use generated images and temporary directories. They do not require
private photographs, GUI applications, or network access.

## License

MIT
