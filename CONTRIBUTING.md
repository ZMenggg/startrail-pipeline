# Contributing

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[raw]'
```

## Safety requirements

- Never modify, rename, or delete source photographs.
- Keep generated outputs outside source directories.
- Preserve deterministic EXIF-time and filename ordering.
- Write resumable, machine-readable reports for processing decisions.
- Do not add tests that depend on private photographs, GUI applications, or
  network access.

## Before opening a pull request

```bash
python -m unittest discover -s tests -v
python -m compileall -q startrail_pipeline tests
sh -n process_photo_batch.sh run_photo_test.sh
```

New RAW behavior should include synthetic or mocked regression tests.
