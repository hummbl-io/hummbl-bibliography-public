# Public bibliography reader kit source — 0.2 preview

This source directory contains the source for a small, offline reading path built from
four public research references. It turns a bibliography and bounded claim
assessments into a local HTML reader, guide and BibTeX file. BKI and IN2 appear
as design interpretations in the guide; they are not evidence that this kit
improves learning or decision quality. No human evaluation is claimed.

The reader processes notes in the open browser tab and exports Markdown or
editable JSON. It has no account, autosave, telemetry, browser storage or
submission service. The source bundle contains bibliography metadata and brief
assessment summaries, not paper text, PDFs, reader notes or private governance
material. Linked research remains subject to its own rights.

## Build and package

Requires Python 3.11 or newer. Node.js is only needed for the browser-code test.
From this source directory, choose new output paths outside it:

```text
python -B build.py --output ../reader-kit-built
python -B package.py --output ../reader-kit-release --archive ../reader-kit.zip
```

The builder is standard-library only and works offline. The package contains
exactly ten files and verifies its manifests before writing the requested new
directory and deterministic ZIP. Both commands refuse existing destinations.
The source manifests bind bytes and inventory; they do not authenticate a
publisher or establish the truth of research claims.

## Tests

```text
python -B -m unittest discover -s tests -v
node --test tests/reader.test.cjs
```

The public source files and original authored code/documentation are offered
under `MIT OR Apache-2.0`; see `LICENSE`, `LICENSE-MIT` and `LICENSE-APACHE`.
This 0.2 preview has not been evaluated with readers. Any future evaluation
would need separately reviewed tasks, consent and data-custody arrangements.
