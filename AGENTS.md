# Star Trail Pipeline Agent Guide

## Goal

Build a safe, resumable, command-line workflow for processing hundreds of
star-trail frames on macOS. The source RAW files are archival assets and must
never be modified, renamed in place, or deleted.

## Safety Rules

- Treat `input/` and any user-supplied source directory as read-only.
- Never auto-delete rejected frames. Write decisions to manifests and copy or
  symlink selected frames into project directories.
- Refuse to overwrite outputs unless the user passes an explicit force flag.
- Use deterministic ordering: EXIF capture time first, filename second.
- Write machine-readable JSON/CSV reports for every analysis step.
- Keep the pipeline resumable and idempotent.
- Do not invoke GUI applications from the automated path.

## Engineering Constraints

- Target macOS on Apple Silicon with 16 GB RAM.
- Stream frames one at a time during stacking. Do not load the entire sequence
  into RAM.
- Use Python standard library for orchestration and lightweight metadata work.
- Keep image dependencies explicit and minimal.
- RAW development is an external adapter (`darktable-cli` preferred). The core
  stacker accepts 16-bit TIFF/PNG inputs.
- Preserve 16-bit precision through the intermediate and archival stages.
- Separate objective analysis from subjective edits. Automatic rejection must
  be conservative and reversible.
- Tests must use generated synthetic images and temporary directories.

## Expected Commands

The executable is `startrail`:

- `startrail init PROJECT`
- `startrail inventory PROJECT --source DIR`
- `startrail analyze PROJECT`
- `startrail select PROJECT`
- `startrail develop PROJECT [--style FILE]`
- `startrail stack PROJECT [--mask FILE]`
- `startrail preview PROJECT`
- `startrail run PROJECT --source DIR`
- `startrail doctor`

Each command must support `--help`, provide actionable errors, and log its work.

